---
phase: 09-multi-runner-scheduling
reviewed: 2026-06-02T00:00:00Z
depth: standard
files_reviewed: 14
files_reviewed_list:
  - backend/core/database_connector.py
  - cli/config.py
  - cli/commands/init.py
  - dashboard_api/connection_source.py
  - dashboard_api/main.py
  - dashboard_api/models.py
  - dashboard_api/routers/profiles.py
  - dashboard_api/routers/schedules.py
  - dashboard_api/schedule_logic.py
  - dashboard_api/scheduler.py
  - dashboard_api/schemas.py
  - frontend/src/app/dashboard/settings/page.tsx
  - frontend/src/lib/api.ts
  - frontend/src/lib/types.ts
findings:
  critical: 2
  warning: 5
  info: 3
  total: 10
status: resolved
resolved: 2026-06-03
resolution_commits:
  - b29176d  # CR-01, CR-02, WR-01
  - 1f469c6  # WR-02..05, IN-01..03 + api_url pinned
---

> RESOLUTION (2026-06-03): All 10 findings addressed.
> - CR-01, CR-02, WR-01 fixed in commit b29176d with 3 regression tests.
> - WR-02 (cron dow), WR-03 (corrupt-YAML 400), WR-04 (schedules rate limit),
>   WR-05 (import hoist), IN-01 (minute picker), IN-02 (documented escape hatch),
>   IN-03 (updated_at on poll) fixed in commit 1f469c6.
> - Per product-owner decision, api_url is now a fixed hosted constant; aegis/config.yaml
>   can no longer override it (internal AEGIS_API_URL env override only).
> Full suite: 73 passed; frontend tsc clean.

# Phase 09: Code Review Report

**Reviewed:** 2026-06-02
**Depth:** standard
**Files Reviewed:** 14
**Status:** issues_found

## Summary

Reviewed the full Phase 9 multi-runner scheduling addition: Snowflake dialect support in the DB connector, a per-profile `Schedule` model with CRUD API, an in-process `AsyncIOScheduler` poller, and the Settings page UI for creating/managing schedules.

Tenant isolation is correctly applied in all schedule queries via `client_id` scoping. The `website_schedulable` write guard is re-derived server-side on `POST /schedules` (good). Credential leakage in error messages is not present in the new paths reviewed. The cron/next-run computation logic is correct for all three presets.

Two blockers were found: a stuck-run issue when the scheduler's thread dispatch raises, and a silent last_run_at poisoning when a run is skipped by the active-run guard. Five warnings cover a missing schedulability re-check on PATCH, a misleading cron string convention, an unguarded YAML-parse silent failure path, missing rate limiting on the schedules router, and a lazy import that hides errors until runtime.

---

## Critical Issues

### CR-01: Orphaned QUEUED run when `execute_run` raises inside `run_in_threadpool`

**File:** `dashboard_api/scheduler.py:82-119`

**Issue:** The scheduler creates and commits a `Run` row (status=QUEUED) at lines 82-92, then immediately calls `await run_in_threadpool(execute_run, ...)` at line 94. The `execute_run` contract says it never raises, but this is an internal contract with no enforcement at the call site. If `execute_run` does raise (e.g., import failure, DB connectivity loss opening the fresh session inside `execute_run`), the `except Exception` block at line 114 catches it, calls `db.rollback()` on the *scheduler's* session (which only rolls back the `next_run_at` update, not the already-committed Run row), prints a warning, and continues. The committed `Run` row is now permanently stuck in `QUEUED` status. On the next poll tick, the active-run guard (`models.Run.status.in_(["QUEUED", "RUNNING"])`) will block every future execution for that client indefinitely.

**Fix:** After catching the exception from `run_in_threadpool`, open a new session and mark the orphaned run as FAILED:

```python
except Exception as e:
    print(f"[warn] schedule id={sched_id} failed: {e}")
    try:
        db.rollback()
    except Exception:
        pass
    # Recover the orphaned QUEUED run so the active-run guard is not stuck.
    if 'run' in dir():  # run was created before the exception
        recovery_db = SessionLocal()
        try:
            orphan = recovery_db.query(models.Run).filter(
                models.Run.id == run.id,
                models.Run.status == "QUEUED",
            ).first()
            if orphan:
                orphan.status = "FAILED"
                orphan.error_reason = "Scheduler dispatch failed"
                orphan.completed_at = datetime.utcnow()
                recovery_db.commit()
        except Exception:
            pass
        finally:
            recovery_db.close()
```

Alternatively, structure the code so `next_run_at` is always advanced in a separate `finally` block that opens its own session, keeping the run-creation and the next_run advancement as two independent commits that cannot both be rolled back by a single exception path.

---

### CR-02: `last_run_at` is written even when the active-run guard suppresses execution

**File:** `dashboard_api/scheduler.py:103-111`

**Issue:** The comment at line 102 says "Always roll `next_run_at` forward — skip-missed, no catch-up burst." This is correct for `next_run_at`. However, `last_run_at` is also unconditionally set to `now` at line 104 regardless of whether the active-run guard fired. When the guard fires, no run is dispatched but the UI will display "Last run: [time]" for that timestamp, misleading the operator into thinking a run actually executed. In a monitoring context where the last-run timestamp is used to verify that data quality checks actually fired, this is an integrity violation.

**Fix:** Only set `last_run_at` when a run is actually dispatched:

```python
if active is None:
    run = models.Run(...)
    db.add(run)
    db.commit()
    db.refresh(run)
    await run_in_threadpool(execute_run, ...)
    sched.last_run_at = now  # Move here: only set when run was created

# Always advance next_run_at regardless (skip-missed)
sched.next_run_at = compute_next_run(...)
db.commit()
```

---

## Warnings

### WR-01: PATCH `/schedules/{id}` does not re-check `website_schedulable`

**File:** `dashboard_api/routers/schedules.py:143-190`

**Issue:** The `create_schedule` endpoint correctly re-derives `website_schedulable` server-side (T-09C-02). The `update_schedule` endpoint has no equivalent check. A client could: (1) have a postgres profile and create a valid schedule; (2) run `aegis push` with an updated YAML where that profile is changed to `sqlite`; (3) PATCH the schedule to change its preset. The PATCH will succeed without re-validating schedulability, and the scheduler will continue dispatching runs for a now-non-schedulable (local) profile. While `execute_run` will eventually fail gracefully, the schedule stays active and the failure is silent from the API perspective.

**Fix:** Add a schedulability re-check at the start of `update_schedule`, mirroring the check in `create_schedule`:

```python
def update_schedule(...):
    s = _get_schedule_or_404(schedule_id, client, db)

    # Re-derive schedulability (defense-in-depth, same as create)
    yaml_text = connection_source.get_yaml_text(db, client.id)
    types = connection_source.profile_types(yaml_text)
    db_type = types.get(s.profile, "")
    if not connection_source.is_website_schedulable(db_type):
        raise HTTPException(
            status_code=400,
            detail=f"Profile '{s.profile}' is no longer schedulable from the dashboard.",
        )
    # ... rest of update logic
```

---

### WR-02: Cron string stored in `Schedule.cron` uses non-standard weekday numbering

**File:** `dashboard_api/schedule_logic.py:23-28`

**Issue:** `preset_to_cron` for weekly produces `f"{at_minute} {at_hour} * * {weekday + 1}"` where `weekday=0` maps to cron weekday `1`. The inline comment claims "1=Monday" is standard, but the universally-used Vixie cron standard (and POSIX cron) treat weekday `0` and `7` as Sunday, with `1=Monday` — so the code produces valid output for Mon-Sat. However, `weekday=6` (Sunday in Python's 0=Mon convention) maps to cron `7`, which some cron parsers reject (they accept 0-7, others only 0-6). More critically, the `cron` column is described in the model as "human-inspectable" and could be extracted by an operator to recreate the schedule in an external cron system. An operator reading `0 6 * * 7` would get Sunday in most systems, which matches intent, but an operator reading `0 6 * * 1` expecting Monday may be surprised that this comes from `weekday=0`. The APScheduler itself does not use this cron string at all (it uses the interval trigger), so this is a misleading display artifact, not an execution bug.

**Fix:** Either use the standard `0=Sunday` convention (weekday field = `weekday % 7`) with a clear comment, or store the day name instead of the numeric cron field:

```python
if preset == "weekly":
    # cron weekday: 0=Sunday, 1=Monday ... 6=Saturday (POSIX standard)
    # Python weekday() is 0=Monday, so we map: Mon->1, Tue->2, ..., Sun->0
    cron_weekday = (weekday + 1) % 7  # maps Sun(6)->0, Mon(0)->1, ...
    return f"{at_minute} {at_hour} * * {cron_weekday}"
```

---

### WR-03: YAML parse errors silently return empty profile list, causing misleading 400 on schedule create

**File:** `dashboard_api/connection_source.py:29-34` and `dashboard_api/routers/schedules.py:56-62`

**Issue:** `_parse()` wraps `yaml.safe_load` in a try/except and returns `{}` on any `YAMLError`. If a client uploads malformed YAML via `/sync`, `profile_names()` returns `([], None)`, and `create_schedule` then raises `HTTP 400 "Profile '{name}' not found in connection config"`. This is factually wrong — the profile may exist in the YAML but the YAML is unparseable. The client gets a misleading error that suggests the profile name is wrong, not that their YAML file is corrupt.

**Fix:** Propagate parse errors rather than swallowing them. In `_parse`, raise a structured exception on `YAMLError`, and in `create_schedule` (and `sync_profiles`), catch it and return a 422 with a clear message:

```python
def _parse(yaml_text: str) -> dict:
    data = _yaml.safe_load(yaml_text) or {}
    return data if isinstance(data, dict) else {}
# Let YAMLError propagate; callers catch it.
```

Or at minimum, the schedule create endpoint should distinguish "no config uploaded" from "config is malformed."

---

### WR-04: Schedules router has no rate limiting

**File:** `dashboard_api/routers/schedules.py:1-203`

**Issue:** The `runs` router applies per-client rate limiting (via `slowapi`) on the run-trigger endpoint to prevent abuse. The `schedules` router has no equivalent protection. A client can call `POST /api/v1/schedules` repeatedly (cycling create/delete) or `PATCH` in a hot loop with no throttling. While the one-per-(client, profile) unique constraint limits persistent damage, the create+delete cycle could stress the database or be used to generate log noise.

**Fix:** Import the limiter and decorate the mutating endpoints:

```python
from dashboard_api.limiter import limiter
from fastapi import Request

@router.post("", ...)
@limiter.limit("20/minute")
def create_schedule(request: Request, body: schemas.ScheduleCreate, ...):
    ...
```

---

### WR-05: Lazy import of `_resolve_env_vars` inside `resolve_profile` hides import errors until runtime

**File:** `dashboard_api/connection_source.py:49`

**Issue:** `resolve_profile` contains `from backend.core.config_loader import _resolve_env_vars` inside the function body. If the `backend` package is unavailable (e.g., wrong working directory, missing PYTHONPATH, or the package is renamed), this raises an `ImportError` only when `resolve_profile` is first called — typically at run dispatch time, not at startup. The error would be caught by `execute_run`'s outer try/except and turned into a FAILED run, which is recoverable but makes the root cause harder to trace.

**Fix:** Move the import to the module level:

```python
from backend.core.config_loader import _resolve_env_vars
```

If circular import concerns exist, resolve them by extracting `_resolve_env_vars` into a shared utility module with no dashboard_api dependencies.

---

## Info

### IN-01: `at_minute` picker absent from the create schedule UI

**File:** `frontend/src/app/dashboard/settings/page.tsx:55-96`

**Issue:** `CreateState` has no `at_minute` field; the API call always sends `at_minute: 0`. The backend schema accepts `at_minute` (0-59) and `preset_to_cron` uses it. Users cannot schedule runs at, say, 06:30 UTC — only on the hour. This is a product completeness gap, not a bug, but it means the schema capability is unexposed and the UI comment "at_minute always 0 in v1.3" in `schedule_logic.py` implies this is a known limitation. No action required if it is intentional, but it should be noted.

---

### IN-02: `connection_url` direct override skips no validation in `database_connector.py`

**File:** `backend/core/database_connector.py:38-39`

**Issue:** The `connection_url` field allows any SQLAlchemy URL to be passed through directly. The ENV_VAR check at lines 27-35 scans `profile.values()`, so a `connection_url` containing a literal `${VAR}` reference will be caught. However, a `connection_url` containing a hardcoded password (no `${VAR}` pattern) passes through silently. The only defense is the upstream policy requiring `${ENV}` references in the YAML. No code-level guard enforces this for `connection_url`. Documenting that `connection_url` must also use `${ENV}` references would close this gap.

---

### IN-03: `Schedule` model `updated_at` column uses `default=datetime.utcnow`, not `onupdate`

**File:** `dashboard_api/models.py:105`

**Issue:** `updated_at = Column(DateTime, default=datetime.utcnow)` sets the initial value on insert but does not auto-update on subsequent writes (SQLAlchemy's `onupdate=` hook is not set). The router manually sets `s.updated_at = datetime.utcnow()` in `update_schedule`, which is correct. However, the scheduler's `poll_due_schedules` updates `sched.last_run_at` and `sched.next_run_at` without touching `updated_at`, meaning `updated_at` goes stale after the first scheduler tick. This is the same pattern used by `ConnectionConfig.updated_at` (line 86) and is consistent within the codebase, but it means `updated_at` is not a reliable "last modified" timestamp.

---

_Reviewed: 2026-06-02_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
