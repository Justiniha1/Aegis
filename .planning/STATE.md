---
gsd_state_version: 1.0
milestone: v1.4
milestone_name: Hosted Airflow Sales Demo
status: milestone-complete
stopped_at: "v1.4 (Phase 10 — hosted Airflow sales demo) COMPLETE and merged to main; verified end-to-end (run #5 COMPLETE 5/5 on the hosted dashboard for demo client_id=2). v1.3 (Phase 9) also complete and on main. Only open item: a staged-but-uncommitted edit to docs/airflow-demo-runbook.md folding in Phase 10 lessons (Method A local Docker, Railway OOM caveat, aegis push env-var gotcha). No active development in flight."
last_updated: "2026-06-04T00:00:00.000Z"
last_activity: 2026-06-04 -- v1.4 Airflow demo complete + verified; runbook rewrite staged (uncommitted)
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
Last activity: 2026-06-04 -- v1.4 complete; airflow-demo-runbook.md rewrite staged (uncommitted)
Next: commit the staged runbook edit (no auto-commit per preference), then start a new milestone when there's new work.

## Milestone History

| Milestone | Phases | Shipped |
|-----------|--------|---------|
| v1.0 Demo Readiness | 1–2 | 2026-05-22 |
| v1.1 Airflow Integration | 3–4 | 2026-05-26 |
| v1.2 First Client Handoff | 5–8 | 2026-06-02 |
| v1.3 Multi-Runner Execution & Scheduling | 9 | 2026-06-03 (merged to main) |
| v1.4 Hosted Airflow Sales Demo | 10 | 2026-06-04 (merged to main, verified E2E) |

## Accumulated Context

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

Last session: 2026-06-04
Stopped at: v1.3 (Phase 9) and v1.4 (Phase 10 Airflow demo) both COMPLETE and merged to main; v1.4 verified end-to-end. Stale Phase 9 HANDOFF.json and phase-09 .continue-here.md removed during this session's state refresh. Working tree clean except one staged edit: `docs/airflow-demo-runbook.md` (+102/−38, Phase 10 lessons). **No auto-commit per preference** — commit pending user approval. No active development in flight.
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
