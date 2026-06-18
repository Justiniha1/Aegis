# A3 Audit — API Layer (routers, schemas, models, DB session, query helpers)

Read-only audit. No source files were modified. Scope: `dashboard_api/main.py`,
`models.py`, `database.py`, `schemas.py`, `queries.py`, and the seven routers under
`dashboard_api/routers/`. Auth internals (`auth.py`), the limiter, scheduler,
run_executor, and yaml_sync are referenced only where they affect router behavior.

## Summary

The API layer is small (~1,000 LOC across 12 files), consistently structured, and
mostly idiomatic FastAPI + SQLAlchemy. Tenant isolation is applied on every data
route via `client_id` filtering, and the 404-not-403 cross-tenant pattern is used
deliberately and consistently. The biggest correctness theme is **non-atomic
multi-step writes**: several handlers issue multiple `db.add`/`delete` calls and a
single `commit` without explicit transaction framing, and `submit_results` mutates a
counter in a way that is read-modify-write racy under concurrency. The biggest
modernization theme is the project-wide use of the deprecated `datetime.utcnow`
(both as Column defaults and in handlers). There is a real N+1-adjacent concern and a
mass-assignment foot-gun in the tests router (`**body.model_dump()` straight into the
ORM model). Security posture is solid; no authz route is missing a dependency, and no
secrets leak through response models. The router split is justified and should NOT be
consolidated — if anything `queries.py` is under-used and more shared helpers would
reduce duplication. Test coverage is good for profiles/schedules but absent for
results, runs, clients, auth, and the tests router; characterization tests are needed
before any refactor.

## Findings

### [High] Read-modify-write race on `Run.completed_tests` in submit_results
- Location: `dashboard_api/routers/results.py:73-74`
- What & why: `run.completed_tests = run.completed_tests + len(batch.results)` reads
  the ORM-loaded value and writes back a computed value. The engine can POST result
  batches for the same `run_id` concurrently (and the scheduler/run_executor also
  touch the row). Two overlapping batches can both read the same `completed_tests`
  and one increment is lost, leaving the run permanently short of `total_tests`
  (drives the "stuck in progress" UI state). A SQL-side atomic update
  (`UPDATE ... SET completed_tests = completed_tests + :n`) avoids the lost update.
- Recommendation: replace with an atomic in-DB increment, e.g.
  `db.query(models.Run).filter(models.Run.id == run.id).update({models.Run.completed_tests: models.Run.completed_tests + len(batch.results)}, synchronize_session=False)`.
  Note this changes the in-Python `run` object's value semantics — verify nothing
  downstream reads `run.completed_tests` from the same session expecting the new value
  without a refresh. Because behavior under concurrency changes, this is `ask-first`.
- Disposition: ask-first

### [High] Project-wide deprecated `datetime.utcnow`
- Location: `models.py:17,33,74,75,86,104,105` (Column defaults);
  `routers/results.py:32`; `routers/profiles.py:54`; `routers/tests.py:77,234`;
  `routers/schedules.py:216`; also `auth.py:66`.
- What & why: `datetime.utcnow()` is deprecated as of Python 3.12 and returns a
  naive datetime. Mixing naive UTC values with any timezone-aware comparison (e.g.
  scheduler `next_run_at` math) is a latent bug source, and the call will eventually
  warn/break. The schemas expose these as `datetime` with no tz info.
- Recommendation: migrate to `datetime.now(timezone.utc)`. CAUTION: this changes
  stored/serialized values from naive to tz-aware, which alters JSON output
  (`...Z`/offset suffix) and any naive-vs-aware comparison in the scheduler. A
  behavior-preserving refactor must either keep values naive (store
  `datetime.now(timezone.utc).replace(tzinfo=None)`) or migrate all comparison sites
  together. Not a safe blind swap.
- Disposition: ask-first

### [High] Mass-assignment: `TestDefinition(client_id=..., **body.model_dump())`
- Location: `dashboard_api/routers/tests.py:48` (create_test); same pattern via
  `setattr` loop at `tests.py:74-75` (update_test).
- What & why: `body.model_dump()` is splatted directly into the ORM constructor.
  Today `TestDefinitionIn` happens to mirror the safe subset of columns, so this is
  not currently exploitable — but it is a fragile coupling: any future field added to
  the Pydantic schema (or the model) silently becomes writable/assignable with no
  review gate. `update_test` is worse: it `setattr`s every key including `profile`
  and `enabled` unconditionally, and a PUT with a partial body is impossible (the
  schema requires `config`, `type`, `name`), so PUT is effectively full-replace —
  fine if intended, but undocumented.
- Recommendation: enumerate fields explicitly, or pin the schema with
  `model_config = {"extra": "forbid"}` (also closes unexpected-field injection on
  inbound bodies) and keep the model/schema field sets asserted in a test. Adding
  `extra="forbid"` changes behavior for clients currently sending extra keys (they'd
  get 422), so treat as ask-first; the explicit-field enumeration is behavior-
  preserving and safe.
- Disposition: ask-first

### [Medium] Non-atomic multi-statement writes without explicit transaction
- Location: `routers/clients.py:24-27` (delete_client: two bulk deletes + delete +
  commit); `routers/results.py:45-76` (auto-create Run, flush, loop add, commit);
  `routers/tests.py:159-163` and `:255-262` (import/sync: many add/delete then one
  commit, then `export_tests_to_yaml`).
- What & why: each is a single logical transaction relying on the implicit
  begin/commit. That is acceptable, but there is no `try/except: rollback` around the
  commits (except schedules.py create, which does it for IntegrityError). If the
  commit raises (constraint, DB hiccup), the session is left in a failed state for the
  request and the FastAPI 500 leaks a raw SQLAlchemy error unless a global handler
  catches it. `export_tests_to_yaml` runs AFTER commit in tests.py — if YAML export
  raises, the DB is already committed and the client gets a 500 even though the write
  succeeded (inconsistent observable state).
- Recommendation: wrap the YAML-export side effect so its failure cannot 500 a
  successful DB write (log + continue, or move before commit if it should be part of
  the transaction). Consider a single global exception handler for DB errors to avoid
  leaking SQLAlchemy internals. Wrapping export in try/except is behavior-changing
  (clients currently see 500); ask-first.
- Disposition: ask-first

### [Medium] `delete_client` ignores `ConnectionConfig` and `Schedule` rows
- Location: `routers/clients.py:24-27`
- What & why: delete_client manually deletes `TestResult` and `TestDefinition`, then
  `db.delete(current)`. It does NOT delete `Run`, `ConnectionConfig`, or `Schedule`
  rows for the client. `Client.results`/`test_definitions` relationships exist but
  `Run`, `ConnectionConfig`, `Schedule` have no cascade and no manual delete. On
  SQLite (default) FKs are not enforced by default, so the delete "succeeds" leaving
  orphan rows; on Postgres with FK enforcement the `db.delete(current)` would raise an
  IntegrityError (orphan Run/Schedule/ConnectionConfig reference the client). A
  lingering enabled Schedule for a deleted client would also keep firing in the
  scheduler.
- Recommendation: delete all child rows (runs, schedules, connection_config) in the
  same transaction, or declare ON DELETE CASCADE / relationship cascades on the model.
  Add a characterization test first to lock current behavior. Behavior-changing on
  Postgres; ask-first.
- Disposition: ask-first

### [Medium] `list_clients` returns a list to model a single resource
- Location: `routers/clients.py:13-16`
- What & why: `GET /api/v1/clients` returns `[current]` — the authenticated client's
  own record wrapped in a list. This is a semantic oddity (the route name implies a
  collection but it is single-tenant self-info) and forces the frontend to index `[0]`.
  Not a bug, but a readability/REST-shape smell. A `/clients/me` returning a single
  `ClientOut` would be clearer.
- Recommendation: leave as-is unless the frontend can be updated in lockstep — changing
  the response shape breaks the client. Document the intent. ask-first.
- Disposition: ask-first

### [Medium] Enrichment lookup keyed by `test_name` can collide / silently miss
- Location: `routers/results.py:107-129`
- What & why: results are enriched with table/column by matching `TestResult.test_name`
  to `TestDefinition.name`. `TestDefinition.name` is not unique per client (no
  UniqueConstraint on `(client_id, name)` in `models.py:61`), so two defs with the same
  name produce a last-writer-wins `def_lookup`. If a definition was renamed/deleted
  after the result was recorded, enrichment silently yields `None`. The query itself is
  a single batched `IN (...)` so it is NOT an N+1 — good — but correctness of the join
  key is fragile.
- Recommendation: prefer joining on a stable key (store table/column on TestResult at
  write time, or join via `test_id`). At minimum add `UniqueConstraint(client_id, name)`
  on TestDefinition. Schema/migration change; ask-first.
- Disposition: ask-first

### [Low] Inconsistent error status codes across YAML-ingesting routes
- Location: `routers/tests.py:119,123` (422 for invalid/empty YAML) vs
  `routers/schedules.py:63` (400 for unparseable connection config) vs
  `routers/profiles.py` (sync never validates YAML, always returns ok).
- What & why: invalid YAML is 422 in tests.py but 400 in schedules.py, and
  `profiles.sync_profiles` stores arbitrary text with no validation and returns
  `{"ok": True}` even for garbage. Inconsistent contracts for "bad input" make the
  frontend's error handling branchy.
- Recommendation: pick one code for malformed user-supplied YAML (422 is the more
  correct "well-formed request, semantically invalid content"; 400 is defensible).
  Validate in `sync_profiles` for parity. Changing a status code is behavior-visible;
  ask-first.
- Disposition: ask-first

### [Low] `sync_profiles` accepts unbounded YAML with no parse check (info/availability)
- Location: `routers/profiles.py:37-57`
- What & why: the body `yaml_content` is stored verbatim with no size cap and no parse
  validation; `profile_names` later swallows parse errors and returns `[]`. A client can
  push megabytes of text into `ConnectionConfig.yaml_text` (a `Text` column). Low risk
  (per-tenant, authenticated) but there is no upper bound anywhere on this or the
  `/tests/import` / `/tests/sync` bodies.
- Recommendation: add a `max_length` on the Pydantic field(s) for YAML payloads
  (e.g. `Field(..., max_length=200_000)`). Adding a cap rejects oversized bodies that
  previously succeeded; ask-first.
- Disposition: ask-first

### [Low] `create_test` / `update_test` do not validate `type` against the whitelist
- Location: `routers/tests.py:42-53`, `:56-81`; whitelist lives at
  `routers/results.py:14` and `routers/runs.py:16` (duplicated).
- What & why: `runs.trigger_run` and `results.get_results` validate test `type`
  against a frozenset of 8 builtins, but `create_test`/`update_test` accept any
  `type: str`. A test created with a bogus type is silently never selected by
  `enabled_tests_query` (type filter) and yields the confusing "no enabled tests"
  rejection at run time rather than at definition time. The 8-type whitelist is also
  duplicated in two routers (drift risk).
- Recommendation: centralize the allowed-types frozenset in `queries.py` (or a small
  `constants.py`) and validate on create/update. Validating on create rejects inputs
  that previously succeeded; ask-first. The de-duplication of the constant alone is
  `auto-fix-safe`.
- Disposition: ask-first (validation) / auto-fix-safe (constant de-dup)

### [Low] `models.Base.metadata.create_all` on startup instead of migrations
- Location: `main.py:28`
- What & why: tables are created via `create_all` at lifespan startup. This never
  applies column/constraint changes to an existing DB (e.g. the added `error_reason`,
  `next_run_at` columns) — only fresh creates. With SQLite default and no Alembic, a
  schema change silently does not migrate, producing runtime OperationalErrors.
- Recommendation: adopt Alembic for schema evolution; keep `create_all` only for tests/
  first boot. Out of scope to change here, but flag for the refactor. ask-first.
- Disposition: ask-first

### [Low] `import_from_yaml` raises KeyError on missing `name`/`type`
- Location: `routers/tests.py:142,150` (`t["name"]`, `t["type"]`)
- What & why: in the import path, `t["name"]` and `t["type"]` use bracket access; a
  YAML entry missing those keys raises KeyError -> uncaught 500 (vs the `sync` path
  which uses `.get(..., "")` and skips). Inconsistent robustness; a malformed-but-valid
  YAML produces a server error rather than a 422.
- Recommendation: use `.get` + explicit 422 for missing required keys, matching the
  sync path. Behavior-changing (500 -> 422); ask-first.
- Disposition: ask-first

### [Low] `RunCreate.type_filter` items are not length/element validated by Pydantic
- Location: `schemas.py:120-122`
- What & why: validation of `type_filter` element values happens manually in
  `runs.trigger_run:82-90` (whitelist) — fine — but elements have no max_length at the
  schema layer, and the manual check truncates to `[:5]`/`[:64]` only for the error
  message, not the stored value. Low impact because unknown types are rejected, but the
  schema should carry the constraint declaratively.
- Recommendation: type as `list[Literal[...the 8 types...]]` so Pydantic rejects bad
  values with a 422 before the handler, removing the manual loop. Changes the error
  code/shape (422 vs 400); ask-first.
- Disposition: ask-first

## Simplification & structure

Verdict: the router split is justified; do NOT consolidate. The codebase uses the
standard FastAPI "router-per-resource" layout (one `APIRouter` per resource under
`dashboard_api/routers/`, with shared `schemas.py`, `models.py`, `database.py`,
`queries.py`). For a project this size (~1,000 LOC, 7 resources) this is the
recommended structure for file-type organization and is well within idiomatic norms —
collapsing into one giant router file would reduce clarity, not increase it. The
"too many files" feeling is more about a few small files (`limiter.py`,
`profile_loader.py`, `connection_source.py`) than the routers themselves; those are
cohesive single-responsibility modules and are fine.

Real duplication worth removing (mostly `auto-fix-safe` constant moves):
- The 8-type test-type frozenset is duplicated in `results.py:14` and `runs.py:16`.
  Move to one module (e.g. `queries.py` already centralizes the enabled-tests filter,
  or a new `constants.py`). The defaults `"dev"`/`"MEDIUM"` are likewise repeated in
  `tests.py` import/sync.
- The tenant-404 fetch pattern is hand-written in `runs.py:163-170`, `tests.py:63-72`,
  `tests.py:90-99`; `schedules.py` already factored this into `_get_schedule_or_404`.
  A shared `get_owned_or_404(db, Model, id, client_id)` helper in `queries.py` would
  remove the repetition and guarantee the 404-not-403 invariant in one place.
- `_to_run_out` (runs.py) and the manual `RunOut` composition exist because
  `RunOut.model_config = {"from_attributes": False}`. This is intentional (composing
  `error` from two columns) but could be a Pydantic `@model_validator`/computed field
  on `RunOut`, removing the hand-written mapper. Optional.

Proposed minimal target (no big restructure): keep the 7 routers; add
`dashboard_api/constants.py` (allowed test types, default profile/severity) and extend
`queries.py` with `get_owned_or_404`. That removes the cross-router drift without
moving to a feature-package layout, which would be overkill here.

## Test gaps & proposed tests

Existing direct API tests cover only profiles and schedules
(`tests/test_api/test_profiles.py`, `test_schedules.py`). There are NO direct router
tests for results, runs, clients, auth, or the tests router (the CLI tests exercise
some endpoints indirectly). Before any refactor, add characterization tests that pin
CURRENT behavior:

- auth_routes: login success returns token + client_id + client_name; wrong password
  -> 401; unknown email -> 401; client with no `password_hash` -> 401.
- clients: create returns api_key once (and only on create); duplicate name -> 409;
  duplicate email -> 409; `GET /clients` returns a single-element list of self with no
  api_key; `DELETE /clients/{other_id}` -> 403; `DELETE` own id cascades TestResult +
  TestDefinition and (characterize current behavior) leaves Run/Schedule/ConnectionConfig.
- results.submit_results: with valid `run_id` increments `completed_tests` by batch
  size; cross-client `run_id` -> 404; no `run_id` auto-creates a COMPLETE Run; response
  shape `{stored, run_at, run_id}`. Add a CONCURRENCY test that posts two batches for the
  same run and asserts the final `completed_tests` (this will currently FAIL/flake and
  documents the race in Finding 1).
- results.get_results: status/test_type whitelist rejection (400); `limit` cap at 1000;
  ordering newest-first; enrichment of table/column from TestDefinition.config including
  the list-of-columns join and the `ref_table`/`columns` fallbacks; tenant isolation.
- runs.trigger_run: unknown profile -> 400; bad type_filter -> 400; zero matching tests
  -> 400; active run present -> 409; happy path -> 202 with run_id/total/status=QUEUED;
  rate-limit 429 after the configured quota. runs.get_run/list_runs tenant 404 + limit
  bounds (1..200).
- tests router: create via JWT only (API key -> 401/403 since `get_current_client_jwt`);
  PUT full-replace semantics; import skips disabled + existing names and returns
  counts; sync create/update/delete/unchanged accounting; invalid YAML codes (422 import
  vs current behavior); `**model_dump()` field set (guards mass-assignment regressions).

Add a shared `conftest` fixture for an isolated SQLite DB + TestClient with the
scheduler disabled (`COMET_SCHEDULER_ENABLED=0`) so these run hermetically.
