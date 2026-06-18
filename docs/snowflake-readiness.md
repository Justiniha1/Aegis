# Snowflake Client Readiness — "Finished State" Breakdown

Reference for what remains to make Comet genuinely usable by clients on Snowflake.
Captured 2026-06-07. Decision on record: **support both lanes (hosted website-lane and
client-lane/Airflow) equally**. Not yet formalized into a milestone.

## Where Snowflake stands today (shipped in v1.3)

Working:
- Connection builder (`backend/core/database_connector.py`): `snowflake://user:pass@account/db?warehouse=…&role=…`,
  account-locator normalization (strips `.snowflakecomputing.com`), `${ENV}` password
  references with loud-fail when unset.
- Hosted engine image includes `snowflake-sqlalchemy`; `comet init` ships a Snowflake
  template; `pip install "comet-dq[snowflake]"` extra exists.
- Two lanes documented in `docs/client-lane.md`: website-lane (hosted scheduler runs
  Snowflake if no IP allowlist) and client-lane (client's Airflow runs it, posts results).

The plumbing exists. The gaps below are what "finished" requires.

## Shared work (needed regardless of lane)

- **Snowflake key-pair + SSO/MFA auth.** Password-only today. Many enterprise Snowflake
  accounts mandate key-pair or enforce MFA / block plain password — likely hard blocker.
- **`schema` support** in the connection builder. Currently `database` is used but `schema`
  is never appended; clients are stuck with the role's default schema.
- **"Test connection" in the UI.** `DatabaseConnector.test_connection()` exists but isn't
  surfaced. A client adding a profile only discovers bad creds when a run fails.
- **Failure notifications** (email/Slack). Table stakes for a data-quality product; deferred.
- **CI** (pytest on push) and **Alembic migrations**. Reliability floor before scaling client
  count. Today: manual UAT only, and `create_all` makes column changes on existing tables unsafe.
- **Polish:** per-test pass/fail in `comet run`; fix the broken `--no-wait` dashboard link.
  (Done 2026-06-07: `COMET_API_URL` env var removed — the hosted URL is now baked-in and not
  client-configurable in the CLI or SDK.)

## Hosted website-lane (the heavy lift "both lanes" commits to)

- **Per-client secret store.** The website-lane resolves `${SNOWFLAKE_PASSWORD}` against the
  hosted api process's environment (worked for one demo client via `DEMO_DB_*`). Two Snowflake
  clients referencing the same `${VAR}` collide; the only workaround today is uniquely-named env
  vars per client set manually by the owner — which means the owner holds every client's
  credentials and it does not scale. Needs a real per-client secret store.
- **Static-egress solution** (proxy/NAT). Railway egress IPs are dynamic and cannot be added to
  a Snowflake network policy, so IP-allowlisted Snowflake accounts are unreachable from hosted.
- **Multi-replica story.** Scheduler is single-replica-gated today (`COMET_SCHEDULER_ENABLED`).

## Client-lane (Airflow)

- Roughly 80% there already. Each client holds their own creds in their own environment, which
  sidesteps the secret-store and IP-allowlist problems entirely.
- Remaining: harden + document the Snowflake-in-Airflow path; clean example DAG.

## Reality check on "both equally"

The client-lane is nearly done; the **hosted website-lane is where the real engineering lives**
(per-client secret store + static egress). So "both lanes equally" mostly means funding the
hosted-lane infra work — that is the long pole. Worth re-confirming the investment is wanted
there vs. leaning client-lane-first and treating hosted as best-effort.

## Known bugs (discovered during demo prep, 2026-06-07)

- **The quality gate does not block on failing checks.** `run_executor` marks a run `COMPLETE`
  whenever the engine finishes without crashing — it does not flip to `FAILED` when individual
  checks fail. `run_checks` only raises `CometDQChecksFailed` on run status `FAILED`
  (`comet_dq/_run.py:103`). Net effect: failing checks show red in the dashboard, but the
  `CometDQOperator` task stays GREEN and downstream is NOT blocked — contradicting the
  operator docstring and example DAG ("fails the task and blocks downstream when any check
  fails"). Fix: expose a failed-test count on the run (RunOut, computed — no migration) and
  have `run_checks` raise when it's > 0. This also feeds the "per-test pass/fail in `comet run`"
  item. HIGH priority — it's the core product promise.

## Independent of Snowflake

- Two open v1.3 UAT gates still want closing: Settings scheduling browser flow, and a live
  scheduled run firing on Railway.

## Suggested priority order

1. Snowflake key-pair/SSO auth + `schema` support (without these, Snowflake clients may not connect).
2. Per-client secret store (unblocks multi-tenant hosted Snowflake).
3. CI (cheap insurance before more clients).
4. Failure notifications + test-connection UX.
5. Static egress, migrations, multi-replica, polish.
