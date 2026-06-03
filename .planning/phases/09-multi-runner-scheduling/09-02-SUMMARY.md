---
phase: 09-multi-runner-scheduling
plan: "02"
subsystem: capability-api-and-settings-ui
tags: [profiles, scheduling, settings, website-schedulable, frontend, tdd]
dependency_graph:
  requires: [09-01]
  provides: [capability-aware-profiles-api, settings-ui-schedule-slot, locked-notice]
  affects: [dashboard_api/connection_source.py, dashboard_api/schemas.py, dashboard_api/routers/profiles.py, frontend/src/lib/types.ts, frontend/src/app/dashboard/settings/page.tsx]
tech_stack:
  added: []
  patterns: [Pattern-3-capability-from-unresolved-type, single-source-of-truth-predicate, TDD-red-green]
key_files:
  created:
    - tests/test_api/test_website_schedulable.py
  modified:
    - dashboard_api/connection_source.py
    - dashboard_api/schemas.py
    - dashboard_api/routers/profiles.py
    - tests/test_api/test_profiles.py
    - frontend/src/lib/types.ts
    - frontend/src/app/dashboard/settings/page.tsx
decisions:
  - "Capability derived from UNRESOLVED YAML type only — no _resolve_env_vars call, secrets never enter the path (Pattern 3, locked in 09-CONTEXT)"
  - "Single shared is_website_schedulable predicate in connection_source.py reused by both UI and (Wave C) write guard"
  - "Settings locked notice links to /docs/client-lane (DOC-01 target added in Wave D) — satisfies UX-02 no-dead-end requirement"
  - "Wave C schedule control slot uses data-schedule-slot={profile.name} attribute as the mount point"
metrics:
  duration: "~30 minutes"
  completed: "2026-06-03"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 6
  tests_added: 5
  tests_total: 47
---

# Phase 09 Plan 02: Per-Profile Capability API + Settings UI Gating Summary

Wave B — capability-aware profiles API and Settings UI locked notice with client-lane link.

**One-liner:** JWT-scoped profiles API extended with db_type + website_schedulable (from unresolved YAML type only), Settings renders a Wave-C-ready schedule slot for cloud DBs and an honest locked notice with /docs/client-lane link for local/SQLite profiles.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Shared predicate + ProfileOut fields + endpoint + regression update | f85b4df | connection_source.py, schemas.py, routers/profiles.py, test_profiles.py, test_website_schedulable.py |
| 2 | Settings UI — schedule slot vs locked notice | 32d7a4c | types.ts, settings/page.tsx |

## What Was Built

### Task 1: Backend capability predicate + API (TDD)

**RED:** `tests/test_api/test_website_schedulable.py` written first — 5 tests covering:
- `test_is_website_schedulable_true_types` — True for postgresql/postgres/mysql/mssql/snowflake (any case, trailing slash)
- `test_is_website_schedulable_false_types` — False for sqlite/""/unknown
- `test_profile_types_no_env_resolution` — profile_types works with unset ${ENV} vars
- `test_profiles_endpoint_includes_capability` — endpoint returns correct db_type + website_schedulable per profile
- `test_profiles_endpoint_never_leaks_secrets` — response has exactly {name, is_default, db_type, website_schedulable}, no "password" or "${"

**GREEN:** Three implementation changes:

1. `dashboard_api/connection_source.py` — added:
   - `_WEBSITE_SCHEDULABLE_TYPES = {"postgresql", "postgres", "mysql", "mssql", "snowflake"}`
   - `profile_types(yaml_text) -> dict` — returns name->lowercased-type using `_parse` only (no `_resolve_env_vars`)
   - `is_website_schedulable(db_type) -> bool` — pure function, single source of truth

2. `dashboard_api/schemas.py` — `ProfileOut` extended with `db_type: str = ""` and `website_schedulable: bool = False`

3. `dashboard_api/routers/profiles.py::list_profiles` — builds type map once via `profile_types`, populates both new `ProfileOut` fields

**Regression test update:** `test_profiles.py::test_list_profiles_returns_names_from_yaml` updated:
- Keys-set assertion now expects `{"name", "is_default", "db_type", "website_schedulable"}`
- Added fixture value assertions: dev=sqlite/False, staging=postgres/True
- Existing sync and trigger tests preserved unchanged

### Task 2: Settings UI

`frontend/src/lib/types.ts` — `ProfileOut` extended with `db_type: string` and `website_schedulable: boolean`.

`frontend/src/app/dashboard/settings/page.tsx` — capability indicator added below each profile select button row:
- `website_schedulable=true`: branded container (`data-schedule-slot={p.name}`) with "Schedulable from the dashboard" label and "Recurring schedule — configure below" placeholder. Wave C wires the real control into this slot.
- `website_schedulable=false`: locked notice with heading "Not schedulable from the dashboard", explanatory body text, and `<a href="/docs/client-lane">How to schedule from the client lane</a>` link (Wave D creates the route). Satisfies UX-02 no-dead-end requirement.

Phase 8 profile select behavior is fully preserved.

## Verification Results

- `pytest tests/test_api/test_website_schedulable.py tests/test_api/test_profiles.py` — 8 passed
- `pytest tests/` — 47 passed (0 failures, 0 regressions)
- `tsc --noEmit` — clean (no new errors)
- `grep "def is_website_schedulable"` — found in connection_source.py
- `grep "website_schedulable"` — found in schemas.py, routers/profiles.py, types.ts, settings/page.tsx, both test files

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

- Settings schedule control slot (`data-schedule-slot={p.name}`) renders placeholder text "Recurring schedule — configure below". This is intentional — Wave C (Plan 09-03/09-04) wires the real APScheduler-backed control into this mount point. The stub does not prevent the plan's goal (capability gating + locked notice) from being achieved.

## Threat Flags

No new security surface beyond what the plan's threat model covers. The `profile_types` helper was verified to use `_parse` only (no `_resolve_env_vars`); `test_profile_types_no_env_resolution` asserts this by running with the env vars explicitly unset.

## Self-Check: PASSED

- f85b4df: `git log --oneline --all` confirms commit exists
- 32d7a4c: `git log --oneline --all` confirms commit exists
- `tests/test_api/test_website_schedulable.py`: created and committed
- `dashboard_api/connection_source.py`: contains `def is_website_schedulable`
- `dashboard_api/schemas.py`: contains `website_schedulable`
- `frontend/src/lib/types.ts`: contains `website_schedulable`
- `frontend/src/app/dashboard/settings/page.tsx`: contains `website_schedulable` and `/docs/client-lane`
