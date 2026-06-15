---
gsd_state_version: 1.0
milestone: v1.4
milestone_name: Hosted Airflow Sales Demo
status: milestone-complete
stopped_at: "v1.4 (Phase 10) COMPLETE + merged + verified. Since then (2026-06-10 session): fixed a CLI .env-resolution bug in cli/config.py — load_dotenv now uses find_dotenv(usecwd=True) so .env resolves from the user's current dir (and the real-client pip-install case) instead of cli/config.py's install location. Tests updated, tests/test_cli green (14). Change is uncommitted. No milestone in progress."
last_updated: "2026-06-10T00:00:00.000Z"
last_activity: 2026-06-10 -- CLI .env resolution fix (usecwd=True); 3 deferred items surfaced during demo walkthrough
progress:
  total_phases: 1
  completed_phases: 1
  total_plans: 1
  completed_plans: 1
  percent: 100
---

# Project State

## Project Reference

See: `.planning/PROJECT.md` (updated 2026-06-02)

**Core value:** Operators can see — at a glance — whether their data is healthy, and act on what's broken.
**Current focus:** v1.4 complete (Phase 10 Airflow demo done + verified). No milestone in progress — ready for next via `/gsd-new-milestone`.

## Current Position

Phase: 10 — COMPLETE (only phase of v1.4); merged to main
Plan: complete
Status: v1.4 Hosted Airflow Sales Demo complete + verified end-to-end (run #5 COMPLETE 5/5, demo client_id=2). v1.3 also complete and on main.
Last activity: 2026-06-10 -- CLI .env resolution fix (cli/config.py + test_config.py), uncommitted
Next: commit the CLI .env fix + the staged runbook edit (no auto-commit per preference), then start a new milestone when there's new work. 3 deferred items below were surfaced during a demo walkthrough.

## Milestone History

| Milestone | Phases | Shipped |
|-----------|--------|---------|
| v1.0 Demo Readiness | 1–2 | 2026-05-22 |
| v1.1 Airflow Integration | 3–4 | 2026-05-26 |
| v1.2 First Client Handoff | 5–8 | 2026-06-02 |
| v1.3 Multi-Runner Execution & Scheduling | 9 | 2026-06-03 (merged to main) |
| v1.4 Hosted Airflow Sales Demo | 10 | 2026-06-04 (merged to main, verified E2E) |

## Accumulated Context

### Post-v1.4 session (2026-06-10) — CLI .env fix + demo walkthrough findings

- **CLI .env resolution bug (FIXED, uncommitted).** `aegis run` was 401-ing from `deploy/demo` because `cli/config.py` called bare `load_dotenv()`, which python-dotenv resolves relative to the **calling code file's** location (`cli/config.py`) — always landing on the repo-root `.env` (stale localhost key), ignoring the user's cwd. Fix: `load_dotenv(find_dotenv(usecwd=True))` so `.env` resolves from the directory the user runs `aegis` in (matching how `aegis/*.yaml` already resolves). Also fixes the real-client `pip install` case, where the old behavior would search `site-packages` and never find a project `.env`. Updated the `load_dotenv` stubs in `tests/test_cli/test_config.py`; `tests/test_cli` green (14 passed). Files changed: `cli/config.py`, `tests/test_cli/test_config.py`.
- **Confirmed (no action):** `DEMO_DB_HOST/NAME/USER/PASSWORD` in `deploy/demo/aegis/database_connection.yaml` are resolved **server-side** by `backend/core/config_loader.py:_resolve_env_vars` from the env of the process running the run (the hosted Railway api service) — NOT client-side. `aegis push` uploads `${ENV}` placeholders literally; secrets never leave the server. Missing var → loud-fail in `database_connector.py` naming the var (not its value).
- **Confirmed (no action):** Airflow operator (`aegis_dq/airflow/_operator.py`) reads `AEGIS_API_KEY` via constructor arg > Airflow Variable (`airflow_var_api_key`) > env var. NO `.env`/cwd logic — independent of the CLI fix. Demo container gets the key from `docker run -e`; real clients set it on the worker env or as an Airflow Variable.

### v1.4 artifacts (Phase 10 — Airflow demo)

- Design spec: `docs/superpowers/specs/2026-06-03-airflow-demo-hosted-run-design.md`
- Plan: `docs/superpowers/plans/2026-06-03-airflow-demo-hosted-run.md`
- Runbook: `docs/airflow-demo-runbook.md` (rewrite staged, uncommitted)
- Reuses existing `AegisDQOperator` → `trigger_run` → server-side `execute_run`; no new product capability.
- Key lesson: run demo Airflow **locally via Docker** (`docker build -f deploy/airflow/Dockerfile`). Railway 1 GB plan OOM-crash-loops `airflow standalone` (needs ~1.5–2 GB).

### v1.3 artifacts

- Design spec: `docs/superpowers/specs/2026-06-02-execution-scheduling-model-design.md`
- Research: `.planning/research/` (STACK / FEATURES / ARCHITECTURE / PITFALLS / SUMMARY)
- Requirements: `.planning/REQUIREMENTS.md` (11 reqs, all → Phase 9)
- Build order: Wave A drivers → B capability/UI → C scheduler → D CLI-config + docs

### Open-decision defaults (override during planning if needed)

Password auth (not key-pair); document Snowflake IP-allowlist limitation; cron presets (not raw); defer hosted MSSQL ODBC; skip missed runs (no catch-up); one schedule per (client, profile).

### Decisions

All decisions logged in `.planning/PROJECT.md` Key Decisions table.

### Blockers/Concerns (carried)

- No CI test suite — UAT is manual. `pytest` = 73 tests passing locally (was 35 pre-v1.3).
- No Alembic — new tables via `create_all` are safe; column changes on existing tables are not.

## Session Continuity

Last session: 2026-06-10
Stopped at: v1.4 complete + merged + verified. This session was a demo walkthrough + a CLI .env-resolution bugfix (cli/config.py now uses find_dotenv(usecwd=True); test stubs updated; tests/test_cli green). Uncommitted working tree: `cli/config.py`, `tests/test_cli/test_config.py` (this session's fix); plus pre-existing edits `deploy/demo/aegis/database_connection.yaml`, `deploy/demo/aegis/test_definitions.yaml`, `docs/snowflake-readiness.md`; plus the staged `docs/airflow-demo-runbook.md` Phase 10 edit. **No auto-commit per preference.** 3 deferred items added to the table (engine no-op doc, client API-key doc, commit the .env fix). No active development in flight.
Resume file: none

## Deferred Items

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| v1.3-defer | Email/Slack failure notifications | First likely follow-up | 2026-06-02 |
| v1.3-defer | Snowflake key-pair / SSO auth | If a client mandates it | 2026-06-02 |
| v1.3-defer | Hosted-image MSSQL ODBC | Until a client needs hosted MSSQL | 2026-06-02 |
| future | PyPI publish (PKG-02) | Backlog | 2026-05-26 |
| future | Per-row / per-table run triggers | Backlog | 2026-05-22 |
| Phase 7 | Live Railway deploy re-verification | Human gate | 2026-05-29 |
| docs | `engine: Simple` in test_definitions.yaml is a no-op forward-compat label (only one engine; never branched on, only stamped into result metadata at test_engine.py:146). Decide: document as no-op or leave. | Break down later | 2026-06-10 |
| docs | Add "Where the client sets AEGIS_API_KEY" section to airflow-demo-runbook / example DAG: worker env var vs Airflow Variable, plus the worker-vs-webserver gotcha (key must be on the worker that executes the task). | Break down later | 2026-06-10 |
| chore | Commit the CLI .env fix (`cli/config.py` + `tests/test_cli/test_config.py`) — clean tested bugfix, lands on its own. | Pending user | 2026-06-10 |
