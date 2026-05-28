---
phase: 05-sdk-reliability
plan: "01"
subsystem: aegis_dq
tags: [sdk, timeout, exception, airflow]
dependency_graph:
  requires: []
  provides: [AegisDQRunTimeout, max_wait_seconds-parameter]
  affects: [aegis_dq/_run.py, aegis_dq/_client.py, aegis_dq/__init__.py]
tech_stack:
  added: []
  patterns: [monotonic-deadline, exception-translation, tdd-red-green]
key_files:
  created:
    - tests/test_aegis_dq/test_timeout.py
  modified:
    - aegis_dq/_run.py
    - aegis_dq/_client.py
    - aegis_dq/__init__.py
decisions:
  - "Use built-in TimeoutError in _client.py (avoids circular import); _run.py translates it to AegisDQRunTimeout with profile context"
  - "time.monotonic() for deadline tracking to prevent wall-clock skew (T-05-01 mitigation)"
  - "max_wait_seconds=None default preserves backward compatibility — no timeout by default"
metrics:
  duration: "203s"
  completed_date: "2026-05-28"
  tasks_completed: 2
  files_changed: 4
---

# Phase 5 Plan 01: SDK Reliability — max_wait_seconds Timeout Summary

**One-liner:** AegisDQRunTimeout exception with monotonic-clock deadline enforcement in wait_for_run() and run_checks() via TimeoutError translation pattern.

## What Was Built

Added hard-deadline timeout support to the `aegis_dq` SDK so Airflow DAG tasks can fail fast when the Aegis engine stalls, rather than blocking indefinitely.

### Changes

**`aegis_dq/_run.py`**
- Added `AegisDQRunTimeout(Exception)` class with `profile`, `run_id`, `max_wait_seconds` attributes and a human-readable message containing all three values
- Added `max_wait_seconds: int | None = None` keyword-only parameter to `run_checks()`
- `run_checks()` now wraps `client.wait_for_run()` in `try/except TimeoutError` and re-raises as `AegisDQRunTimeout` with the correct `profile` filled in (since `_client.py` has no access to the profile name)

**`aegis_dq/_client.py`**
- Added `max_wait_seconds: int | None = None` parameter to `wait_for_run()`
- Implemented deadline tracking using `time.monotonic()` (not `time.time()`) per T-05-01 threat mitigation
- Raises built-in `TimeoutError` when elapsed time exceeds `max_wait_seconds` and run has not reached a terminal state
- When `max_wait_seconds=None` (default), behavior is unchanged — polls indefinitely

**`aegis_dq/__init__.py`**
- Added `AegisDQRunTimeout` to `__all__` and import line
- Updated module docstring Public surface comment

**`tests/test_aegis_dq/test_timeout.py`** (new, TDD RED commit)
- 10 new unit tests covering: exception attributes, message content, `wait_for_run()` deadline enforcement, monotonic clock usage, `run_checks()` passthrough, `AegisDQRunTimeout` conversion

## TDD Gate Compliance

| Gate | Commit | Status |
|------|--------|--------|
| RED (failing tests) | d0222b4 | Passed — ImportError confirmed |
| GREEN (implementation) | 156f1fa | Passed — 17/17 tests pass |
| REFACTOR | n/a | Not required |

## Verification Results

```
$ python -c "from aegis_dq import AegisDQRunTimeout; print('OK')"
OK

$ python -c "import inspect, aegis_dq; print(inspect.signature(aegis_dq.run_checks))"
(profile: 'str' = 'default', *, type_filter: 'list[str] | None' = None, poll_interval: 'int' = 5, api_url: 'str | None' = None, api_key: 'str | None' = None, max_wait_seconds: 'int | None' = None) -> 'dict[str, Any]'

$ python -m pytest tests/test_aegis_dq/ -x -q
17 passed in 1.18s
```

## Decisions Made

1. **TimeoutError translation pattern**: `_client.py` raises the built-in `TimeoutError` to avoid a circular import (`_run.py` imports `_client.py`; importing `AegisDQRunTimeout` back into `_client.py` would create a cycle). `run_checks()` in `_run.py` catches `TimeoutError` and enriches it into `AegisDQRunTimeout` with the `profile` context.

2. **`time.monotonic()` for deadline**: Per T-05-01 in the threat model — wall-clock (`time.time()`) can jump backwards on NTP sync, which would falsely extend the deadline. `time.monotonic()` is guaranteed to only move forward.

3. **`max_wait_seconds=None` default**: Zero behavior change for existing callers. The original infinite-poll semantics are preserved unless the caller explicitly opts into a deadline.

## Deviations from Plan

None — plan executed exactly as written.

## Threat Flags

No new threat surface introduced. T-05-01 mitigation (`time.monotonic()`) implemented as specified.

## Known Stubs

None.

## Self-Check: PASSED

- tests/test_aegis_dq/test_timeout.py: FOUND
- aegis_dq/_run.py AegisDQRunTimeout: FOUND
- aegis_dq/_client.py monotonic: FOUND
- aegis_dq/__init__.py AegisDQRunTimeout in __all__: FOUND
- Commits d0222b4, 156f1fa, 04a36c5: FOUND
