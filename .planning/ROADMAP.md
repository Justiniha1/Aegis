# Roadmap: Aegis

## Milestones

- **v1.0 Demo Readiness** — Phases 1–2 (shipped 2026-05-22)
- **v1.1 First Client: Airflow Integration** — Phases 3–4 (shipped 2026-05-26)
- **v1.2 First Client Handoff** — Phases 5–8 (shipped 2026-06-02) — see [milestones/v1.2-ROADMAP.md](milestones/v1.2-ROADMAP.md)
- **v1.3 Multi-Runner Execution & Per-Profile Scheduling** — Phase 9 (planned 2026-06-02)

## Phases

<details>
<summary>v1.0 Demo Readiness (Phases 1–2) — SHIPPED 2026-05-22</summary>

- [x] Phase 1: Demo Readiness (7/7 plans) — signed off 2026-05-17
- [x] Phase 1.1: Frontend Design Pass (INSERTED) (6/6 plans) — signed off 2026-05-17
- [x] Phase 2: Run-from-UI (2/2 plans) — substantially complete 2026-05-22; profile switcher + per-row triggers deferred

</details>

<details>
<summary>v1.1 First Client: Airflow Integration (Phases 3–4) — SHIPPED 2026-05-26</summary>

- [x] Phase 3: Package + Airflow (3/3 plans) — complete 2026-05-24
- [x] Phase 4: Production Hardening (2/2 plans) — complete 2026-05-26

</details>

<details>
<summary>v1.2 First Client Handoff (Phases 5–8) — SHIPPED 2026-06-02</summary>

- [x] Phase 5: SDK Reliability (3/3 plans) — complete 2026-05-27
- [x] Phase 6: Profile Switcher UI (1/1 plan) — complete 2026-05-29
- [x] Phase 7: Railway Deployment (2/2 plans) — complete 2026-05-29
- [x] Phase 8: Connection Profile Sync (file-driven; built on branch) — merged 2026-06-02 (PR #3)

Full details: [milestones/v1.2-ROADMAP.md](milestones/v1.2-ROADMAP.md)

</details>

### v1.3 Multi-Runner Execution & Per-Profile Scheduling

- [ ] **Phase 9: Multi-Runner Execution & Per-Profile Scheduling** — DB driver coverage (Snowflake/MySQL/MSSQL), per-profile scheduling capability + Settings UI gating, hosted scheduler for cloud profiles, CLI config simplification, client-lane docs

## Phase Details

### Phase 9: Multi-Runner Execution & Per-Profile Scheduling
**Goal**: A cloud-reachable profile (Snowflake/Postgres/etc.) can be scheduled to run automatically from the dashboard; profiles that can't be scheduled from the website say so honestly and point to the client lane; the client setup needed to self-run the engine is minimal.
**Depends on**: Phase 8 (file-driven profiles, `connection_source`), Phase 2 (`execute_run` server-side run path), Phase 7 (Railway hosted deploy)
**Requirements**: DB-01, DB-02, DB-03, UX-02, CLI-01, SCHED-01, SCHED-02, SCHED-03, SCHED-04, SCHED-05, DOC-01
**Design**: docs/superpowers/specs/2026-06-02-execution-scheduling-model-design.md
**Plans:** 5 plans (4 waves)

Plans:
- [ ] 09-01-PLAN.md — Wave A: Snowflake branch in build_connection_url + cloud drivers (hosted pinned + per-DB extras) + loud-fail on unset ${ENV} + Snowflake init template (DB-01, DB-02, DB-03)
- [ ] 09-02-PLAN.md — Wave B: shared website_schedulable predicate, ProfileOut db_type+capability, Settings schedule-control-vs-locked-notice gating (UX-02)
- [ ] 09-03-PLAN.md — Wave C.1: Schedule table + compute_next_run/cron presets + tenant-scoped schedules CRUD with 400 capability guardrail (SCHED-01, SCHED-02, SCHED-04)
- [ ] 09-04-PLAN.md — Wave C.2: in-process AsyncIOScheduler poller (run_in_threadpool + execute_run reuse, AEGIS_SCHEDULER_ENABLED, overlap/skip-missed safety) + Settings schedule control wiring (SCHED-03, SCHED-05)
- [ ] 09-05-PLAN.md — Wave D: optional aegis/config.yaml + hosted api_url default; client-lane runbook + scheduler/no-Alembic/Snowflake-IP-allowlist caveats (CLI-01, DOC-01)

**Success Criteria** (what must be TRUE):
  1. A `type: snowflake` profile (password via `${ENV}`) runs successfully from the hosted dashboard and a run appears in history
  2. From Settings, an operator creates a recurring (preset) schedule on a website-schedulable profile, and the hosted scheduler runs it on time with results in run history
  3. A SQLite/local profile shows an honest locked notice in Settings (no schedule control) with a working link to the client-lane docs, and its schedule API call is rejected
  4. The `aegis` CLI runs without an `aegis/config.yaml` present — `api_url` defaults to the hosted dashboard; only `AEGIS_API_KEY` + `database_connection.yaml` are needed to self-run
  5. The scheduler is safe by construction: single in-process scheduler gated by `AEGIS_SCHEDULER_ENABLED`, `Schedule` table survives restarts, no overlapping/duplicate runs, missed-during-downtime runs are skipped

**Waves** (internal; B's read-only half parallel with A):
- **Wave A — Drivers/dialects**: Snowflake branch in `build_connection_url` + drivers in engine & hosted image + per-DB extras (DB-01, DB-02, DB-03)
- **Wave B — Capability API + Settings UI**: `website_schedulable` derived from unresolved `db_type`; toggle vs locked-notice (UX-02)
- **Wave C — Schedule model + CRUD + hosted scheduler**: `Schedule` table, schedules router (guardrail + tenant scoping), APScheduler in lifespan via `execute_run`/`run_in_threadpool` (SCHED-01..05)
- **Wave D — CLI config simplification + client-lane docs**: `api_url` default + optional `config.yaml`; client-lane runbook + caveats (CLI-01, DOC-01)

**Cross-cutting constraints** (from design spec — locked):
- Laptop-local data = no website scheduler (client lane only)
- Hosted/website runs only reach cloud-reachable DBs
- The Airflow/client lane is client-owned (Aegis ships the operator + docs, not a scheduler)
- Open-decision defaults applied (password auth, document IP-allowlist limit, cron presets, defer hosted MSSQL, skip missed runs, one schedule per profile)

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Demo Readiness | v1.0 | 7/7 | Complete | 2026-05-17 |
| 1.1. Frontend Design Pass (INSERTED) | v1.0 | 6/6 | Complete | 2026-05-17 |
| 2. Run-from-UI | v1.0 | 2/2 | Substantially complete | 2026-05-22 |
| 3. Package + Airflow | v1.1 | 3/3 | Complete | 2026-05-24 |
| 4. Production Hardening | v1.1 | 2/2 | Complete | 2026-05-26 |
| 5. SDK Reliability | v1.2 | 3/3 | Complete | 2026-05-27 |
| 6. Profile Switcher UI | v1.2 | 1/1 | Complete | 2026-05-29 |
| 7. Railway Deployment | v1.2 | 2/2 | Complete | 2026-05-29 |
| 8. Connection Profile Sync | v1.2 | — | Complete | 2026-06-02 |
| 9. Multi-Runner Execution & Scheduling | v1.3 | 0/5 | Planned | - |

---
*Roadmap created: 2026-05-07*
*Last updated: 2026-06-02 — v1.3 milestone started; Phase 9 (Multi-Runner Execution & Per-Profile Scheduling) planned (5 plans, 4 waves)*
