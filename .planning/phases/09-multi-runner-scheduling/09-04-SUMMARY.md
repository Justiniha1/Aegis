---
phase: 09-multi-runner-scheduling
plan: "04"
subsystem: scheduler-runtime-and-settings-ui
tags: [scheduler, apscheduler, lifespan, settings, schedule-control, tdd, run_in_threadpool, d09-guard]
dependency_graph:
  requires: [09-03, 09-02]
  provides: [in-process-scheduler, lifespan-wiring, settings-schedule-control]
  affects:
    - dashboard_api/scheduler.py
    - dashboard_api/main.py
    - dashboard_api/requirements.txt
    - frontend/src/lib/types.ts
    - frontend/src/lib/api.ts
    - frontend/src/app/dashboard/settings/page.tsx
    - tests/test_api/test_scheduler.py
tech_stack:
  added:
    - APScheduler==3.11.2
  patterns:
    - TDD-red-green
    - per-row-fresh-session
    - run_in_threadpool-dispatch
    - table-as-source-of-truth
    - skip-missed-no-catchup
    - D09-active-run-guard-replicated
    - AEGIS_SCHEDULER_ENABLED-env-gate
key_files:
  created:
    - dashboard_api/scheduler.py
    - tests/test_api/test_scheduler.py
  modified:
    - dashboard_api/main.py
    - dashboard_api/requirements.txt
    - frontend/src/lib/types.ts
    - frontend/src/lib/api.ts
    - frontend/src/app/dashboard/settings/page.tsx
decisions:
  - "Per-row fresh sessions: each schedule row gets its own SessionLocal() + close() so a rollback on one row never corrupts the next row's transaction state"
  - "Scan-then-process: a short-lived scan session fetches due IDs, then each ID is processed in its own session — avoids long-held sessions blocking writes"
  - "APScheduler max_instances=1 + coalesce=True prevents concurrent poll_due_schedules coroutines at the APScheduler level"
  - "D-09 guard replicated: active-run check (QUEUED/RUNNING per client) applied before creating a Run; skipped clients still advance next_run_at to prevent hot-loop"
  - "Skip-missed via compute_next_run: next_run_at is rolled forward exactly one interval from now, so any length of downtime results in exactly one run on recovery"
  - "AEGIS_SCHEDULER_ENABLED defaults to 1; set to 0 in test environments to avoid background threads"
  - "Settings ScheduleControl uses per-row fresh session pattern to avoid test isolation issues"
metrics:
  duration: "~55 minutes"
  completed: "2026-06-03"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 7
  tests_added: 6
  tests_total: 67
---

# Phase 09 Plan 04: Scheduler Runtime + Settings Schedule Control Summary

Wave C (part 2) — in-process APScheduler polling runtime and live Settings schedule control wired to the schedules CRUD API.

**One-liner:** Single in-process AsyncIOScheduler (60s interval, env-gated by AEGIS_SCHEDULER_ENABLED) polls the Schedule table for due rows and dispatches each via run_in_threadpool through the existing execute_run boundary, with per-row fresh sessions, D-09 active-run guard, and skip-missed roll-forward; Settings now renders a live preset picker + enable/pause + delete + last/next-run (UTC) control for schedulable profiles.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | scheduler.py poll_due_schedules + lifespan wiring (TDD) | 5cc53f5 (RED), bb2ceec (GREEN) | scheduler.py, main.py, requirements.txt, test_scheduler.py |
| 2 | Wire Settings schedule control to /api/v1/schedules | 17d17a9 | types.ts, api.ts, settings/page.tsx |

## What Was Built

### Task 1: scheduler.py + main.py lifespan (TDD)

**RED:** `tests/test_api/test_scheduler.py` written first — 6 tests covering all dispatch scenarios before `scheduler.py` existed:
- `test_poll_dispatches_due`: due+enabled+no-active-run -> QUEUED run + last/next_run_at advanced
- `test_poll_skips_not_due`: future next_run_at -> no dispatch
- `test_poll_skips_disabled`: enabled=False -> no dispatch
- `test_poll_respects_active_run_guard`: existing QUEUED/RUNNING run -> skip dispatch but still advance next_run_at
- `test_poll_skips_missed_no_catchup`: 7-day-overdue schedule -> exactly 1 run, next_run_at in the future
- `test_one_bad_schedule_does_not_kill_loop`: exception on client A -> client B's schedule still dispatched

**GREEN:**

1. `dashboard_api/scheduler.py` (new):
   - `AsyncIOScheduler(timezone="UTC")` with `poll_due_schedules` job (60s, max_instances=1, coalesce=True)
   - Scan-then-process pattern: short-lived scan session fetches due Schedule IDs; each ID processed in its own fresh `SessionLocal()` + `db.close()` so rollback on one row never corrupts the next
   - D-09 active-run guard replicated (QUEUED/RUNNING per client) before creating a Run
   - `run_in_threadpool(execute_run, ...)` dispatch — execute_run is synchronous, never runs on the event loop
   - Skip-missed: `compute_next_run(sched.preset, now=now, ...)` rolls next_run_at forward exactly once regardless of downtime duration; applied even when dispatch is skipped due to active run
   - `start_scheduler()` and `stop_scheduler()` — both idempotent via `_scheduler.running` check

2. `dashboard_api/main.py` refactored:
   - `asynccontextmanager lifespan(app)` replaces module-top `create_all`
   - On startup: `create_all`, then if `AEGIS_SCHEDULER_ENABLED == "1"` (default): start scheduler and log rehydrated enabled-schedule count
   - On shutdown: `stop_scheduler()`
   - All existing routers preserved: `schedules.router`, `profiles.router`, `runs.router`, etc.

3. `dashboard_api/requirements.txt`: added `APScheduler==3.11.2`

**Test implementation notes:**
- `patch.object(_scheduler_mod, ...)` used instead of string-based `patch()` to avoid module resolution issues before import
- `autocommit=False, autoflush=False` on the test sessionmaker to match production behavior
- Unique api_key_hash per client (counter-suffixed) to satisfy the unique constraint
- Two-client fixture for the error-resilience test (D-09 guard is per-client, not per-profile)

### Task 2: Settings schedule control (frontend)

1. `frontend/src/lib/types.ts`: added `Schedule`, `ScheduleCreate`, `ScheduleUpdate` interfaces

2. `frontend/src/lib/api.ts`: added schedule wrappers:
   - `listSchedules(token)` — GET /api/v1/schedules
   - `createSchedule(body, token)` — POST /api/v1/schedules
   - `updateSchedule(id, body, token)` — PATCH /api/v1/schedules/{id} (via existing `request()` helper)
   - `deleteSchedule(id, token)` — DELETE /api/v1/schedules/{id}

3. `frontend/src/app/dashboard/settings/page.tsx` rewritten:
   - Loads `listSchedules` on mount; matches schedule to profile by `s.profile === p.name`
   - `ScheduleControl` component per schedulable profile:
     - No schedule: "No active schedule. Times are UTC." + "Create schedule" button
     - Preset picker (Hourly / Daily / Weekly) with hour selector (daily+weekly) and weekday selector (weekly)
     - Existing schedule: preset summary, "Last run: ... (UTC)", "Next run: ... (UTC)", Active/Paused badge, Pause/Resume + Delete buttons
   - Locked notice for non-schedulable profiles unchanged (links to /docs/client-lane)
   - No emojis anywhere; all times labelled UTC; tsc --noEmit clean

## Verification Results

- `pytest tests/test_api/test_scheduler.py` — 6 passed
- `pytest tests/` — 67 passed (0 failures, +6 from 61 baseline)
- `grep "run_in_threadpool" dashboard_api/scheduler.py` — found (line 22 import, line 94 call)
- `grep "AEGIS_SCHEDULER_ENABLED" dashboard_api/main.py` — found (lines 22, 23, 30, 45)
- `grep "lifespan" dashboard_api/main.py` — found (lines 18, 19, 65)
- `grep "schedules.router" dashboard_api/main.py` — found (line 90)
- `grep "APScheduler" dashboard_api/requirements.txt` — found (APScheduler==3.11.2)
- `npx tsc --noEmit -p tsconfig.json` — clean (no errors)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Design] Per-row fresh sessions instead of single shared session**
- **Found during:** Task 1 (test_one_bad_schedule_does_not_kill_loop failing)
- **Issue:** A single shared `db` session for the entire poll loop caused SQLAlchemy identity-map corruption after rollback — the session tried to re-insert already-committed Client rows on the next iteration, triggering IntegrityError
- **Fix:** Scan-then-process: a short-lived session fetches due IDs; each ID gets its own `SessionLocal()` + `db.close()` in a finally block. This matches the spirit of execute_run's own fresh-session contract and is more robust than expunge_all()
- **Files modified:** `dashboard_api/scheduler.py`
- **Commit:** bb2ceec

**2. [Rule 2 - Test quality] Two-client fixture for error-resilience test**
- **Found during:** Task 1 (test_one_bad_schedule_does_not_kill_loop)
- **Issue:** The plan's test behavior description assumed same-client multi-profile dispatch, but D-09 active-run guard is per-client (not per-profile) — so after "bad" profile creates a QUEUED run, "good" profile in the same client is blocked by the guard
- **Fix:** Test uses two different clients (bad-client, good-client) to correctly isolate the error-resilience scenario from the active-run guard behavior
- **Files modified:** `tests/test_api/test_scheduler.py`
- **Commit:** bb2ceec

## Known Stubs

None. The schedule control is fully functional with create/pause/delete/last-next-run. Wave D UAT will confirm end-to-end on Railway.

## Threat Flags

No new surface beyond the plan's threat model. All six STRIDE threats (T-09D-01 through T-09D-06) mitigated:
- T-09D-01: AEGIS_SCHEDULER_ENABLED gate prevents double-fire on multi-replica
- T-09D-02: max_instances=1 + coalesce=True + D-09 guard prevents overlap (test_poll_respects_active_run_guard asserts)
- T-09D-03: run_in_threadpool dispatch (test_poll_dispatches_due asserts mock is called)
- T-09D-04: table-as-truth + per-row scan on every tick; startup logs rehydrated count
- T-09D-05: reuses execute_run's _sanitize_error; no new logging of connection dict
- T-09D-06: ScheduleOut carries no secrets; UI consumes only last_run_at/next_run_at/enabled/preset

## Self-Check: PASSED

- 5cc53f5: git log confirms RED test commit exists
- bb2ceec: git log confirms GREEN implementation commit exists
- 17d17a9: git log confirms Task 2 frontend commit exists
- `dashboard_api/scheduler.py`: created (contains poll_due_schedules, run_in_threadpool, start_scheduler)
- `dashboard_api/main.py`: contains lifespan, AEGIS_SCHEDULER_ENABLED, schedules.router
- `dashboard_api/requirements.txt`: contains APScheduler==3.11.2
- `frontend/src/lib/types.ts`: contains Schedule, ScheduleCreate, ScheduleUpdate
- `frontend/src/lib/api.ts`: contains listSchedules, createSchedule, updateSchedule, deleteSchedule
- `frontend/src/app/dashboard/settings/page.tsx`: contains createSchedule, ScheduleControl, UTC labels
- `pytest tests/test_api/test_scheduler.py` — 6 passed
- `pytest tests/` — 67 passed
- `tsc --noEmit` — clean
