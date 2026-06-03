---
phase: 09-multi-runner-scheduling
verified: 2026-06-02T00:00:00Z
status: human_needed
score: 5/5 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Open the Settings page in the dashboard for a postgres/snowflake profile and verify the schedule control renders with preset picker (hourly/daily/weekly), creates a schedule that shows last-run/next-run after creation, and the enable/pause toggle and Delete button function."
    expected: "Schedule control visible for website-schedulable profiles; locked notice with /docs/client-lane link visible for sqlite profiles; no emojis anywhere in the UI."
    why_human: "Frontend rendering and interactive schedule CRUD cannot be verified programmatically without a running browser + server. TypeScript compiles cleanly but real render and API round-trip require manual check."
  - test: "Deploy the api service to Railway and confirm that the scheduler starts, fires a daily schedule on time, and the run appears in run history."
    expected: "api boot log shows '[scheduler] enabled — single in-process poller (60s); rehydrated N enabled schedule(s)'; a due schedule results in a QUEUED->COMPLETE (or FAILED with error_reason) Run visible in the dashboard."
    why_human: "The scheduler dispatches execute_run via run_in_threadpool against a real DB. Integration can only be confirmed on the live Railway deploy."
---

# Phase 9: Multi-Runner Execution & Per-Profile Scheduling Verification Report

**Phase Goal:** A cloud-reachable profile (Snowflake/Postgres/etc.) can be scheduled to run automatically from the dashboard; profiles that can't be scheduled from the website say so honestly and point to the client lane; the client setup needed to self-run the engine is minimal.
**Verified:** 2026-06-02
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A `type: snowflake` profile (password via `${ENV}`) can run from the hosted dashboard — Snowflake branch exists in build_connection_url, drivers installed, unset ${ENV} fails loudly with scrubbed creds | VERIFIED | `build_connection_url` has snowflake branch (line 71-81); `_ENV_VAR_PATTERN` pre-check raises with var name only (lines 9, 27-35); `dashboard_api/requirements.txt` pins `snowflake-sqlalchemy==1.10.0`, `PyMySQL==1.2.0`; 7/7 unit tests pass |
| 2 | From Settings, an operator can create a recurring (preset) schedule on a website-schedulable profile; the hosted scheduler runs due rows on time via execute_run | VERIFIED (automated portion) | `routers/schedules.py` implements full CRUD with `is_website_schedulable` guard; `scheduler.py` dispatches via `run_in_threadpool(execute_run, ...)`; 7/7 schedules API tests pass; 6/6 scheduler tests pass; HUMAN check required for live dispatch |
| 3 | A SQLite/local profile shows an honest locked notice in Settings (no schedule control) with a working link to /docs/client-lane, and its schedule API create is rejected (400/guarded) | VERIFIED (automated portion) | `settings/page.tsx` branches on `p.website_schedulable`; locked branch renders "Not schedulable from the dashboard" with `href="/docs/client-lane"`; API guard at line 66 returns 400; `test_create_schedule_on_sqlite_rejected` passes; HUMAN check for browser render |
| 4 | The `aegis` CLI runs without an aegis/config.yaml present — api_url defaults to hosted dashboard; only AEGIS_API_KEY + database_connection.yaml needed | VERIFIED | `cli/config.py` `load_config` no longer calls `sys.exit` when config.yaml absent; `cfg = {}` then `setdefault("api_url", "https://api.aegis-dq.com")`; `test_load_config_without_file_uses_defaults` and `test_load_config_file_overrides_defaults` pass |
| 5 | Scheduler safe by construction: single in-process scheduler gated by AEGIS_SCHEDULER_ENABLED, Schedule table survives restarts (create_all), no overlapping/duplicate runs (active-run guard), missed-during-downtime runs skipped | VERIFIED | `main.py` lifespan gates on `os.getenv("AEGIS_SCHEDULER_ENABLED", "1") == "1"`; `create_all` called before scheduler start; `max_instances=1`, `coalesce=True` at the APScheduler job; D-09 active-run guard replicated in `poll_due_schedules`; `next_run_at` always rolled forward; all 6 scheduler tests pass |

**Score:** 5/5 truths verified (automated components); 2 items require human verification for live rendering and deployed behavior.

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/core/database_connector.py` | snowflake branch + unset-${ENV} loud-fail + credential scrubbing | VERIFIED | Lines 9, 27-35 (pre-check), 71-81 (snowflake branch); raises ValueError naming only the var, not its value |
| `dashboard_api/requirements.txt` | pinned hosted cloud drivers + APScheduler | VERIFIED | snowflake-sqlalchemy==1.10.0, PyMySQL==1.2.0, tzdata, APScheduler==3.11.2 all present |
| `pyproject.toml` | per-DB optional extras [snowflake][mysql][mssql][postgres][all-db] | VERIFIED | All 5 extras present; all-db excludes pyodbc (mssql is engine-only extra) |
| `tests/test_aegis_dq/test_build_connection_url.py` | 7 URL unit tests incl. snowflake + loud-fail | VERIFIED | 7/7 pass |
| `dashboard_api/connection_source.py` | `profile_types()` + `is_website_schedulable()` shared predicate | VERIFIED | Both functions present; `_WEBSITE_SCHEDULABLE_TYPES` set; no `_resolve_env_vars` call in type path |
| `dashboard_api/schemas.py` | ProfileOut extended + ScheduleCreate/ScheduleUpdate/ScheduleOut | VERIFIED | ProfileOut has `db_type`, `website_schedulable`; Schedule schemas complete with Literal preset and Field bounds |
| `frontend/src/app/dashboard/settings/page.tsx` | per-profile schedule control vs locked notice with client-lane link | VERIFIED | `website_schedulable` branch at line 504; ScheduleControl component; locked notice with `/docs/client-lane` href at line 582; `createSchedule`, `listSchedules`, `updateSchedule`, `deleteSchedule` wired |
| `tests/test_api/test_website_schedulable.py` | predicate + endpoint capability tests, secrets-never-leak | VERIFIED | 5/5 pass |
| `tests/test_api/test_profiles.py` | updated for new ProfileOut keys | VERIFIED | Keys-set assertion updated to 4 keys; sync tests preserved; 3/3 pass |
| `dashboard_api/models.py` | Schedule model (new table, no changes to existing tables) | VERIFIED | `class Schedule` with all 14 columns; `UniqueConstraint("client_id","profile")`; `Index("ix_schedules_due")`; existing tables untouched |
| `dashboard_api/schedule_logic.py` | `compute_next_run` + `preset_to_cron`, UTC, no APScheduler dep | VERIFIED | Pure stdlib datetime/timedelta; raises on unknown preset; 6/6 logic tests pass |
| `dashboard_api/routers/schedules.py` | tenant-scoped CRUD gated by is_website_schedulable | VERIFIED | 400 on non-schedulable; 404 not 403 cross-client; 409 duplicate; all 7 API tests pass |
| `dashboard_api/main.py` | lifespan wiring gated by AEGIS_SCHEDULER_ENABLED; schedules.router registered | VERIFIED | asynccontextmanager lifespan; `AEGIS_SCHEDULER_ENABLED` env gate; `app.include_router(schedules.router)` at line 90 |
| `dashboard_api/scheduler.py` | AsyncIOScheduler + poll_due_schedules via run_in_threadpool | VERIFIED | `run_in_threadpool` at line 94; D-09 guard replicated; skip-missed via next_run_at rollforward; max_instances=1, coalesce=True |
| `frontend/src/lib/types.ts` | Schedule, ScheduleCreate, ScheduleUpdate interfaces | VERIFIED | All 3 interfaces present with correct fields; ProfileOut has db_type + website_schedulable |
| `frontend/src/lib/api.ts` | listSchedules/createSchedule/updateSchedule/deleteSchedule wrappers | VERIFIED | All 4 wrappers present; PATCH uses `request("PATCH", ...)` directly |
| `cli/config.py` | load_config no longer exits when config.yaml absent | VERIFIED | `cfg = {}; if config_path.exists(): ...`; `setdefault` applies regardless |
| `docs/client-lane.md` | client-lane runbook (AegisDQOperator + AEGIS_API_KEY + Snowflake IP note) | VERIFIED | AegisDQOperator DAG example present; AEGIS_API_KEY instruction; allowlist section |
| `DEPLOY.md` | scheduler single-replica caveat + no-Alembic note + Snowflake IP limitation | VERIFIED | "Hosted scheduler" section added; AEGIS_SCHEDULER_ENABLED table; create_all documented; allowlist limitation with link to client-lane.md |
| `tests/test_cli/test_config.py` | no-config-yaml now returns defaults; api-key/401/config-present preserved | VERIFIED | Old SystemExit test replaced by `test_load_config_without_file_uses_defaults`; `test_load_config_file_overrides_defaults` added; 3 originals preserved; 5/5 pass |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `build_connection_url` | snowflake-sqlalchemy dialect | `snowflake://` URL with `?warehouse=&role=` | VERIFIED | Line 81: `return f"snowflake://{user}:{password}@{account}/{database}{query}"` |
| `routers/profiles.py::list_profiles` | `connection_source.profile_types + is_website_schedulable` | `ProfileOut(db_type=..., website_schedulable=...)` | VERIFIED | `is_website_schedulable` called in list_profiles; 5 website_schedulable tests confirm |
| `settings/page.tsx` | `ProfileOut.website_schedulable` | conditional render schedule control vs locked notice | VERIFIED | Branch at line 504 on `p.website_schedulable`; locked notice links `/docs/client-lane` |
| `routers/schedules.py` | `connection_source.is_website_schedulable` | 400 guardrail re-deriving capability | VERIFIED | Lines 64-73: server-side re-derivation |
| `routers/schedules.py` | `schedule_logic.compute_next_run` | next_run_at set on create/update | VERIFIED | Line 91 (create), line 180 (update) |
| `main.py` | `routers/schedules.py` | `app.include_router(schedules.router)` | VERIFIED | Line 90 in main.py |
| `scheduler.py::poll_due_schedules` | `run_executor.execute_run` | `run_in_threadpool(execute_run, ...)` | VERIFIED | Line 94-100 in scheduler.py |
| `main.py lifespan` | `scheduler._scheduler` | AEGIS_SCHEDULER_ENABLED gate + add_job (60s, max_instances=1, coalesce=True) | VERIFIED | Lines 30-43 in main.py; start_scheduler() registers the job |
| `settings/page.tsx` | `/api/v1/schedules` | `createSchedule/listSchedules/updateSchedule/deleteSchedule` | VERIFIED | All 4 wrappers imported and used |
| `cli/config.py::load_config` | hosted api_url default | no sys.exit when config.yaml missing; `setdefault` | VERIFIED | Confirmed in source; `test_load_config_without_file_uses_defaults` passes |
| `frontend Settings locked notice` | `docs/client-lane.md` | `/docs/client-lane` link target | VERIFIED | href="/docs/client-lane" at settings line 582; docs/client-lane.md exists |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `settings/page.tsx` | `schedules` (state) | `listSchedules(token)` -> `GET /api/v1/schedules` -> DB query scoped by client_id | Yes — `db.query(models.Schedule).filter(...)` | FLOWING |
| `settings/page.tsx` | `profiles` | `useRunContext()` -> `listProfiles(token)` -> `GET /api/v1/profiles` -> `profile_types(yaml_text)` | Yes — reads per-client YAML, derives types without ENV resolution | FLOWING |
| `scheduler.py::poll_due_schedules` | `due_ids` | `scan_db.query(models.Schedule.id).filter(enabled==True, next_run_at<=now)` | Yes — live DB query | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Snowflake URL construction | `python -m pytest tests/test_aegis_dq/test_build_connection_url.py -q` | 7 passed | PASS |
| website_schedulable predicate + profiles endpoint | `python -m pytest tests/test_api/test_website_schedulable.py -q` | 5 passed | PASS |
| Schedule CRUD + 400 guardrail + 404 tenant | `python -m pytest tests/test_api/test_schedules.py -q` | 7 passed | PASS |
| Scheduler dispatch/skip/overlap/missed | `python -m pytest tests/test_api/test_scheduler.py -q` | 6 passed | PASS |
| CLI config optional yaml | `python -m pytest tests/test_cli/test_config.py -q` | 5 passed | PASS |
| Full suite regression | `python -m pytest -q` | 68 passed, 0 failures | PASS |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| DB-01 | Plan 01 | Snowflake connects and runs (dialect + driver + build_connection_url branch, password via ${ENV}) | SATISFIED | snowflake branch in database_connector.py; snowflake-sqlalchemy==1.10.0 pinned; 7 unit tests pass |
| DB-02 | Plan 01 | MySQL connects and runs (PyMySQL driver installed) | SATISFIED | mysql+pymysql branch exists (pre-existing); PyMySQL==1.2.0 in dashboard_api/requirements.txt; mysql extra in pyproject.toml |
| DB-03 | Plan 01 | MSSQL connects from client-run engine via aegis-dq[mssql] extra; hosted-image ODBC deferred; documented as client-lane-only | SATISFIED | mssql+pyodbc branch exists; [mssql] extra in pyproject.toml; all-db excludes pyodbc; docs/client-lane.md documents MSSQL as client-lane-only |
| SCHED-01 | Plan 03 | From dashboard, create recurring schedule (preset interval — hourly/daily-at-time/weekly, timezone shown) for website-schedulable profile | SATISFIED | POST /api/v1/schedules with Literal["hourly","daily","weekly"] preset; at_hour/weekday params; Settings UI preset picker with "Times are UTC" label |
| SCHED-02 | Plan 03/04 | Enable/pause, delete a schedule; sees last-run and next-run | SATISFIED | PATCH /schedules/{id} {enabled:bool}; DELETE /schedules/{id}; ScheduleOut has last_run_at + next_run_at; Settings shows Last/Next run labels |
| SCHED-03 | Plan 04 | Hosted scheduler triggers runs server-side on schedule via execute_run; results in run history; failures surface error_reason | SATISFIED (automated) | poll_due_schedules dispatches run_in_threadpool(execute_run); run created with QUEUED status; execute_run uses existing fail-safe path; HUMAN confirmation on Railway needed |
| SCHED-04 | Plan 03 | Schedules API rejects schedule for non-website-schedulable profile (400) | SATISFIED | is_website_schedulable guard at router line 66; test_create_schedule_on_sqlite_rejected passes |
| SCHED-05 | Plan 04 | Scheduler safe by construction: single in-process, AEGIS_SCHEDULER_ENABLED gated, Schedule table source-of-truth, no overlap, missed runs skipped | SATISFIED | All 5 sub-requirements confirmed in source + tests |
| UX-02 | Plan 02 | Settings shows schedule control (website-schedulable) or honest locked notice with /docs/client-lane link | SATISFIED (automated) | website_schedulable conditional at settings line 504; locked notice text matches spec; href="/docs/client-lane"; HUMAN render check needed |
| CLI-01 | Plan 05 | api_url defaults to hosted; aegis CLI runs without config.yaml; only AEGIS_API_KEY + database_connection.yaml required | SATISFIED | cli/config.py confirmed; 5/5 test_config.py tests pass |
| DOC-01 | Plan 05 | Client-lane runbook (API key, AegisDQOperator, single-replica caveat, no-Alembic, Snowflake IP limitation) | SATISFIED | docs/client-lane.md; DEPLOY.md "Hosted scheduler" section; README has "client-lane" pointer |

All 11 requirements: SATISFIED.

---

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| `frontend/src/app/dashboard/settings/page.tsx` line 761 | "Coming soon" text in Notifications section | Info | Pre-existing placeholder for deferred email/Slack alert feature (not part of Phase 9 scope — explicitly listed as a future requirement in REQUIREMENTS.md). Not a stub for scheduling functionality. |
| Multiple files | `datetime.utcnow()` deprecation warnings (79 warnings) | Info | Python 3.12 deprecation of naive UTC. All warnings are in test code and production scheduler/schedule_logic code. Functionality is unaffected; no broken behavior. Not a Phase 9 blocker (pre-existing convention throughout codebase). |

No blockers found.

---

### Human Verification Required

#### 1. Settings Page Live Render — Schedule Control and Locked Notice

**Test:** Log in to the dashboard, navigate to Settings. With a postgres or snowflake profile in your connection YAML: verify the schedule control renders (preset picker with "Hourly/Daily/Weekly" buttons, "Times are UTC" label). Create a daily schedule at hour 6 — verify next_run_at appears. Pause it via the toggle — verify status shows "Paused". Delete it — verify it disappears. Then verify a sqlite profile shows the locked notice "Not schedulable from the dashboard" and the "How to schedule from the client lane" link is clickable.
**Expected:** All interactions succeed with no console errors. No emojis in any displayed text. The /docs/client-lane link is reachable (may 404 on localhost — acceptable; the route path is correct).
**Why human:** Frontend React rendering, state transitions, and API round-trips cannot be verified programmatically. TypeScript compiles cleanly (`tsc --noEmit` passes) but real browser render and user interaction require a running dashboard.

#### 2. Scheduled Run Fires on Railway

**Test:** On the live Railway deploy: create a schedule for a cloud-reachable postgres profile with preset=hourly. Wait up to 60s for the scheduler to poll. Observe the api service logs for `[scheduler] enabled` at startup. Confirm a Run row appears in run history (dashboard run history tab).
**Expected:** Run status progresses QUEUED -> RUNNING -> COMPLETE (or FAILED with a descriptive error_reason if the DB is not reachable). The next_run_at is rolled forward by one hour after the dispatch.
**Why human:** The scheduler dispatches execute_run against a real database. This integration path requires a live Railway deployment and a reachable cloud database — not testable without the production environment.

---

### Gaps Summary

No gaps found. All 11 requirements (DB-01 through DOC-01) have verified implementation in the codebase. The 2 human verification items are functional confirmations of already-wired code paths, not missing implementations.

---

_Verified: 2026-06-02_
_Verifier: Claude (gsd-verifier)_
