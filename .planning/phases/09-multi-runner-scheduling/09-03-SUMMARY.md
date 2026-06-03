---
phase: 09-multi-runner-scheduling
plan: "03"
subsystem: schedule-model-crud-api
tags: [schedules, crud, schedule-model, schedule-logic, tdd, tenant-isolation, capability-guard]
dependency_graph:
  requires: [09-01, 09-02]
  provides: [schedule-table, compute-next-run, schedules-crud-api]
  affects:
    - dashboard_api/models.py
    - dashboard_api/schedule_logic.py
    - dashboard_api/schemas.py
    - dashboard_api/routers/schedules.py
    - dashboard_api/main.py
    - tests/test_api/test_schedule_logic.py
    - tests/test_api/test_schedules.py
tech_stack:
  added: []
  patterns:
    - TDD-red-green
    - tenant-404-not-403
    - capability-guard-server-side
    - one-schedule-per-profile-UniqueConstraint
    - stdlib-datetime-only-no-apscheduler
key_files:
  created:
    - dashboard_api/schedule_logic.py
    - dashboard_api/routers/schedules.py
    - tests/test_api/test_schedule_logic.py
    - tests/test_api/test_schedules.py
  modified:
    - dashboard_api/models.py
    - dashboard_api/schemas.py
    - dashboard_api/main.py
decisions:
  - "Schedule model uses create_all (safe new table); no existing tables altered"
  - "compute_next_run uses stdlib datetime/timedelta only — no APScheduler or croniter dependency in CRUD layer (plan 04 adds APScheduler)"
  - "is_website_schedulable re-derived server-side in router POST — single shared predicate from connection_source.py so UI and API can never disagree (locked in 09-CONTEXT)"
  - "Cross-client access returns 404 not 403 on all schedule endpoints (mirrors runs.py tenant-404 pattern)"
  - "One schedule per (client, profile): pre-check 409 before DB write + IntegrityError backstop on UniqueConstraint"
  - "ScheduleOut exposes id/client_id/profile/preset/cron/enabled/last_run_at/next_run_at only — no connection dict, no secrets"
metrics:
  duration: "~35 minutes"
  completed: "2026-06-02"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 7
  tests_added: 14
  tests_total: 61
---

# Phase 09 Plan 03: Schedule Model + CRUD API Summary

Wave C (part 1) — durable Schedule table, compute_next_run scheduling logic, and tenant-scoped schedules CRUD API.

**One-liner:** New Schedule table (UniqueConstraint client_id+profile) + stdlib-only compute_next_run for hourly/daily/weekly presets + tenant-scoped /api/v1/schedules CRUD that re-derives is_website_schedulable server-side and returns 400 for non-schedulable profiles.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Schedule model + schedule_logic compute_next_run + preset schema | 6b818ce | models.py, schedule_logic.py, test_schedule_logic.py |
| 2 | Schedules CRUD router + schemas + main.py wiring | 8cbb603 | schemas.py, routers/schedules.py, main.py, test_schedules.py |

## What Was Built

### Task 1: Schedule model + schedule_logic (TDD)

**RED:** `tests/test_api/test_schedule_logic.py` written first — 7 tests covering:
- `test_schedule_table_in_metadata` — "schedules" in Base.metadata with required columns + UniqueConstraint
- `test_hourly_next_run` — top of next hour (10:30 -> 11:00)
- `test_daily_next_run_after_time` — next day when now is after at_hour
- `test_daily_next_run_before_time` — today when now is before at_hour
- `test_weekly_next_run` — next Mon from Wed
- `test_invalid_preset_raises` — ValueError mentioning allowed presets
- `test_to_cron_canonical` — "0 * * * *", "0 6 * * *", "0 6 * * 1" for hourly/daily/weekly

**GREEN:**

1. `dashboard_api/models.py` — added `Schedule` model (new table only, no existing tables altered):
   - All required columns: id, client_id, profile, cron, interval_seconds, preset, at_hour, at_minute, weekday, enabled, last_run_at, next_run_at, created_at, updated_at
   - `Index("ix_schedules_due", "enabled", "next_run_at")` for scheduler polling
   - `UniqueConstraint("client_id", "profile", name="uq_schedule_client_profile")`
   - Added `UniqueConstraint` to the existing sqlalchemy import line

2. `dashboard_api/schedule_logic.py` (new) — pure functions, stdlib datetime/timedelta only:
   - `preset_to_cron(preset, at_hour, at_minute, weekday) -> str` — canonical UTC cron strings
   - `compute_next_run(preset, now, at_hour, at_minute, weekday) -> datetime` — UTC naive datetimes

### Task 2: Schedules CRUD router (TDD)

**RED:** `tests/test_api/test_schedules.py` written first — 7 tests covering all CRUD operations and security invariants.

**GREEN:**

1. `dashboard_api/schemas.py` — added `ScheduleCreate`, `ScheduleUpdate`, `ScheduleOut`

2. `dashboard_api/routers/schedules.py` (new) — prefix `/api/v1/schedules`:
   - `POST ""`: validates profile against client YAML, re-derives `is_website_schedulable` server-side (400 if non-schedulable), pre-checks duplicate (409), computes cron + next_run_at, creates row
   - `GET ""`: lists all schedules for authenticated client, ordered by created_at
   - `GET "/{id}"`: 404-not-403 for cross-client access
   - `PATCH "/{id}"`: enable/pause + optional preset/time update (recomputes next_run_at)
   - `DELETE "/{id}"`: 404-not-403 for cross-client access, 204 on success
   - `IntegrityError` caught as backstop -> 409

3. `dashboard_api/main.py` — `schedules.router` registered after `profiles.router`

## Verification Results

- `pytest tests/test_api/test_schedule_logic.py tests/test_api/test_schedules.py` — 14 passed
- `pytest tests/` — 61 passed (0 failures, +14 from 47 baseline)
- `grep "class Schedule" dashboard_api/models.py` — found
- `grep "def compute_next_run" dashboard_api/schedule_logic.py` — found
- `grep "is_website_schedulable" dashboard_api/routers/schedules.py` — found
- `grep "schedules.router" dashboard_api/main.py` — found
- No existing tables modified (only new schedules table added)

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None. The schedule table and CRUD API are fully functional. Plan 04 adds the APScheduler polling runtime that reads from this table; the table is ready.

## Threat Flags

No new surface beyond the plan's threat model. All five STRIDE threats (T-09C-01 through T-09C-05) mitigated:
- T-09C-01: every query scoped by client_id; cross-client returns 404
- T-09C-02: is_website_schedulable re-derived server-side on create
- T-09C-03: ScheduleOut exposes metadata only, test_response_has_no_secrets asserts
- T-09C-04: profile validated against requesting client's own YAML
- T-09C-05: pre-check 409 + UniqueConstraint backstop

## Self-Check: PASSED

- 6b818ce: git log confirms commit exists
- 8cbb603: git log confirms commit exists
- `dashboard_api/schedule_logic.py`: created and committed
- `dashboard_api/routers/schedules.py`: created and committed
- `tests/test_api/test_schedule_logic.py`: created and committed
- `tests/test_api/test_schedules.py`: created and committed
- `dashboard_api/models.py`: contains `class Schedule`
- `dashboard_api/schemas.py`: contains `ScheduleCreate`, `ScheduleOut`
- `dashboard_api/main.py`: contains `schedules.router`
