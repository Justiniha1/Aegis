# Requirements: Aegis v1.3 — Multi-Runner Execution & Per-Profile Scheduling

**Defined:** 2026-06-02
**Core Value:** Operators can see — at a glance — whether their data is healthy, and act on what's broken.
**Design:** docs/superpowers/specs/2026-06-02-execution-scheduling-model-design.md
**Research:** .planning/research/SUMMARY.md

All v1.3 requirements map to a single phase (Phase 9), delivered as internal waves A->B->C->D.

---

## Database Connectivity

- [ ] **DB-01**: A profile of `type: snowflake` connects and runs from both the engine and the hosted api (dialect + driver + `build_connection_url` branch with warehouse/role; password auth via `${ENV}`)
- [ ] **DB-02**: A profile of `type: mysql` connects and runs (PyMySQL driver installed in the engine and hosted api image)
- [ ] **DB-03**: A profile of `type: mssql` connects and runs from a client-run engine via the `aegis-dq[mssql]` extra (hosted-image ODBC system libs deferred; MSSQL documented as client-lane-only for now)

## Scheduling

- [ ] **SCHED-01**: From the dashboard, an operator can create a recurring schedule (preset interval — hourly / daily-at-time / weekly, timezone shown) for a website-schedulable profile
- [ ] **SCHED-02**: An operator can enable/pause and delete a schedule, and sees its last-run and next-run times
- [ ] **SCHED-03**: The hosted scheduler triggers runs server-side on schedule; results land in run history and failures surface a clear reason (reuses the existing `execute_run` path)
- [ ] **SCHED-04**: The schedules API rejects a schedule for a non-website-schedulable profile (e.g. SQLite/local) with a clear error — defense in depth behind the UI gate
- [ ] **SCHED-05**: Scheduler is safe by construction — single in-process scheduler gated by `AEGIS_SCHEDULER_ENABLED`, `Schedule` table is the source of truth (survives restarts), no overlapping runs of the same schedule, missed runs during downtime are skipped (not caught up), at most one schedule per (client, profile)

## Dashboard UX

- [ ] **UX-02**: The Settings page shows, per profile, either a schedule control (when website-schedulable) or an honest locked notice explaining why it can't be scheduled from the dashboard plus a working link to the client/Airflow lane (never a dead end)

## CLI / Client Setup

- [ ] **CLI-01**: `api_url` defaults to the hosted dashboard and the `aegis` CLI no longer requires `aegis/config.yaml` to exist — a self-running client provides only their `AEGIS_API_KEY` plus their `database_connection.yaml`; a dashboard-only client touches no config file

## Documentation

- [ ] **DOC-01**: A client-lane runbook documents pointing the engine at the hosted instance (API key only), scheduling via `AegisDQOperator`, the single-replica / `AEGIS_SCHEDULER_ENABLED` caveat, the no-Alembic new-table behavior, and the Snowflake IP-allowlist limitation (hosted egress IPs aren't static — restricted Snowflake points to the client lane)

---

## Future Requirements (deferred)

- Email / Slack failure notification on scheduled runs (highest-probability first follow-up)
- Raw-cron advanced field (beyond presets) for power users
- Hosted-image MSSQL ODBC support (when a client needs hosted MSSQL)
- Snowflake key-pair / SSO auth (if a client mandates it — doesn't fit the `${ENV}`-string model)
- PyPI publish (PKG-02, carried from prior milestones)
- Per-row / per-table run triggers from the dashboard

## Out of Scope

| Excluded | Why |
|----------|-----|
| Scheduling laptop-local / SQLite data from the website | Impossible — data on a possibly-off machine is unreachable by a hosted runner; client lane only |
| Hosted runner tunneling into a client's private network | Security/architecture boundary — on-prem stays in the client lane |
| A dedicated scheduler worker service / Railway cron | In-process APScheduler is sufficient for a single-client product; documented graduation path exists |
| Multi-channel alerting, ML thresholds, event-driven/freshness triggers | Enterprise bloat for a single-client product |
| Auto-deactivate-after-N-failures | Not needed at this scale |

---

## Traceability

| REQ-ID | Phase | Wave | Status |
|--------|-------|------|--------|
| DB-01 | Phase 9 | A | Pending |
| DB-02 | Phase 9 | A | Pending |
| DB-03 | Phase 9 | A | Pending |
| UX-02 | Phase 9 | B | Pending |
| CLI-01 | Phase 9 | D | Pending |
| SCHED-01 | Phase 9 | C | Pending |
| SCHED-02 | Phase 9 | C | Pending |
| SCHED-03 | Phase 9 | C | Pending |
| SCHED-04 | Phase 9 | C | Pending |
| SCHED-05 | Phase 9 | C | Pending |
| DOC-01 | Phase 9 | D | Pending |

**Coverage:**
- v1.3 requirements: 11 total
- Mapped to phases: 11
- Unmapped: 0

---
*Requirements defined: 2026-06-02*
*Open-decision defaults applied: password auth, document IP-allowlist limitation, cron presets, defer hosted MSSQL, skip missed runs, one schedule per profile — override any during planning.*
