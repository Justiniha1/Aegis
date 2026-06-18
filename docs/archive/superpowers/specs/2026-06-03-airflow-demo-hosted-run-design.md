# Airflow Demo — DAG-Triggered Run on the Hosted Website — Design Spec

**Date:** 2026-06-03
**Milestone:** v1.4 (proposed) — Phase 10
**Status:** Approved for planning

---

## Problem

We can already trigger an Comet run from a client's Airflow — `CometDQOperator` calls
`run_checks()` → `trigger_run()`, which POSTs to the hosted API and the website executes
the run server-side. But there is **no way to show this to a prospect**. There is no
running Airflow, no demo data source, and no script for driving the flow live. A sales
demo today would mean running Airflow on a laptop against ad-hoc data — fragile, and it
undercuts the "this is how it runs in production" story.

The goal is a **live sales demo** that shows a prospect exactly what they would set up:
an Airflow DAG that triggers a real run on the hosted Comet website, with both the DAG
*definition* and the DAG *execution* visible, and the result landing in the dashboard.

## Goals

1. A prospect can watch an Airflow DAG trigger a real run on the **hosted** website,
   end to end, with nothing running on the presenter's laptop.
2. The demo visibly shows **how the DAG is set up** (Airflow Code tab) and **the DAG
   running** (Graph/Grid view), then the run **appearing in the Comet dashboard**.
3. The demo is **repeatable and reliable** in the moment — always-on infra, a known
   admin login, a manual trigger, and a clean reset between runs.
4. The demo reuses the real product path (operator → `trigger_run` → server-side
   `execute_run`) — it is a demonstration of the actual integration, not a mock.

## Non-Goals / Honest Constraints (do not re-litigate)

- **No SQLite.** The website executes the run server-side and must *reach* the database.
  SQLite is a local file (client lane); the product explicitly cannot drive it from the
  website (Settings shows a locked notice). The demo data source is **Postgres**.
- **No failing-run variant in v1.** A single clean passing run only. The failing/blocked-
  downstream beat is a deferred follow-up.
- **No DAG scheduling.** The DAG is triggered manually by the presenter (`schedule=None`).
- **No custom demo UI.** Airflow's own UI (Code + Graph) and the existing Comet dashboard
  are the demo surfaces. We build no bespoke demo frontend.
- **No new product capability.** The operator, `run_checks`/`trigger_run`, server-side
  `execute_run`, and file-driven profiles all already exist and are reused as-is.

---

## Architecture

The demo adds three pieces of infrastructure on Railway, alongside the existing
dashboard project, and reuses the existing run path unchanged.

| Piece | What it is | New or reused |
|-------|-----------|---------------|
| **Hosted Airflow** | One Railway service, `apache/airflow` standalone, demo DAG baked in | New (infra) |
| **Demo Postgres** | A dedicated managed Railway Postgres, seeded with sample data | New (infra) |
| **`demo` profile** | A `database_connection.yaml` entry pointing at the demo Postgres, pushed via `comet push` | New (config) |
| Operator / run path | `CometDQOperator` → `trigger_run` → hosted `execute_run` | Reused |
| Comet dashboard | Shows the run in history like any other | Reused |

### Data flow

```
Airflow (Railway, standalone)
  └─ DAG: run_quality_checks  (CometDQOperator, profile="demo")
       └─ run_checks() → CometAPIClient.trigger_run(profile="demo")
            → POST hosted Comet API
                 → server-side execute_run() against the demo Postgres
                      → run + results stored, visible in the Comet dashboard
       └─ operator polls wait_for_run() until COMPLETE (green)
```

Credentials resolve exactly as the product already does them:
- The **Airflow service** holds `COMET_API_URL` (hosted api) + `COMET_API_KEY` (demo client).
- The **api service** holds the demo Postgres connection vars; the `demo` profile's
  `database_connection.yaml` references them via `${ENV}`, resolved at run time. No new
  secret storage.

---

## Components & Work

### A. Hosted Airflow service (Railway)

- New Railway service from an `apache/airflow` standalone image (webserver + scheduler +
  triggerer in one), with `comet-dq[airflow]` installed so the operator imports.
- The demo DAG is **baked into the image** (copied into the DAGs folder), adapted from
  `examples/airflow_example_dag.py`: `profile="demo"`, `schedule=None` (manual trigger),
  downstream task kept simple or removed for v1.
- Env vars: `COMET_API_URL`, `COMET_API_KEY`, and pinned admin login
  (`_AIRFLOW_WWW_USER_USERNAME` / `_AIRFLOW_WWW_USER_PASSWORD` or equivalent) so the UI
  login is **stable across restarts** — Railway has no persistent disk, so the standalone
  metadata DB (and any auto-generated password) resets on redeploy.
- `railway.toml` / Dockerfile wiring consistent with the existing per-service config pattern.

### B. Demo Postgres service (Railway)

- A dedicated **+ New → Database → PostgreSQL** service, separate from the operational
  app Postgres. Demo data never touches operational tables.
- A `seed_demo.sql` (or small Python seeder) creates a few sample tables with clean data
  that pass the demo's checks. Idempotent so it can be re-run to reset the demo.
- Its connection details are set as env vars on the **api** service (where profiles resolve).

### C. `demo` connection profile + test definitions

- A `demo` entry in `database_connection.yaml` (`type: postgres`) using `${ENV}` references
  to the demo Postgres vars set on the api service.
- Demo test definitions scoped to the `demo` profile that pass cleanly against the seeded
  data (e.g. not-null / row-count / schema checks on the seeded tables).
- Pushed to the hosted account with `comet push` (file-driven profiles, Phase 8).

### D. Demo runbook (docs)

- A `docs/` runbook: one-time setup (the two Railway services + env + seed + push), the
  click-by-click live script (Code tab → trigger → Graph green → dashboard), and a reset
  procedure (re-run the seeder; re-trigger). This is what makes the demo repeatable.

---

## Error Handling / Reliability

- Airflow standalone metadata is **ephemeral** on Railway — acceptable: the DAG reloads
  from the baked-in file and run history resetting between sessions does not matter for a
  demo. Admin creds are pinned so login never breaks.
- If the api cannot reach the demo Postgres, the run fails with an explicit reason
  (existing `execute_run` error path) — surfaced in the dashboard, not a silent hang.
- The seeder is idempotent so a botched demo can be reset in one command.
- Manual trigger (`schedule=None`) avoids surprise runs and keeps the live moment controlled.

## Testing

- The underlying path (operator → `trigger_run` → `execute_run`) is already covered by
  existing tests; no new unit tests are required for reused code.
- Verification is primarily a **manual dry run** of the runbook against the deployed demo:
  trigger the DAG, confirm it goes green, confirm the run appears in the dashboard with all
  checks passing. This dry run is the acceptance gate for the phase.
- Optional: a smoke check that the seeded demo data satisfies the demo test definitions
  before a live demo.

---

## Open Setup Details (resolve during planning, not blocking)

1. Exact `apache/airflow` image tag / standalone vs. a minimal custom Dockerfile.
2. How the api service reaches the demo Postgres on Railway (internal reference variable
   vs. public URL) and which connection vars to expose.
3. Whether the downstream demo task is kept (to show "checks gate the pipeline") or removed
   for the simplest v1 single-run.

## Delivery

Delivered as **Phase 10** (proposed v1.4, "Airflow Demo — Hosted DAG-Triggered Run").
Builds on Phase 9 (server-side `execute_run`, file-driven profiles, hosted dashboard).
Route into a v1.4 milestone, or add Phase 10 to the roadmap directly, during planning.

> Note: Phase 9 (v1.3) is feature-complete but **not yet merged** (branch
> `phase-9-multi-runner-scheduling`, awaiting human UAT + PR). Phase 10 builds on that
> code, so branching/ordering vs. the unmerged Phase 9 work is a planning decision.
