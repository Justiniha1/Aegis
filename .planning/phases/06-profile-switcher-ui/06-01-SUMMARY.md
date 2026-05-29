---
phase: 06-profile-switcher-ui
plan: "01"
subsystem: frontend
tags: [react, context, settings-ui, ux-polish]
dependency_graph:
  requires: []
  provides: [profilesLoading-in-RunContext, profilesError-in-RunContext, settings-page-state-branches]
  affects: [frontend/src/lib/run-context.tsx, frontend/src/app/dashboard/settings/page.tsx]
tech_stack:
  added: []
  patterns: [loading-boolean-in-context-provider, four-branch-conditional-render]
key_files:
  created: []
  modified:
    - frontend/src/lib/run-context.tsx
    - frontend/src/app/dashboard/settings/page.tsx
decisions:
  - "Use Option B (RunContext extension) for profilesLoading/profilesError to avoid stuck-loading landmine on API error"
  - "profilesError rendered as fixed copy string (not raw error message) to prevent credential leakage via UI (T-06-04 mitigation)"
  - "TypeScript compile verified locally via npm install + tsc --noEmit (Docker Desktop not running; functionally equivalent)"
metrics:
  duration: "5m"
  completed_date: "2026-05-29"
  tasks_completed: 3
  tasks_total: 4
  files_modified: 2
---

# Phase 6 Plan 1: Profile Switcher UI Summary

## One-liner

Settings page Active Environment section now has loading/error/empty/populated state branches via RunContext extension exposing `profilesLoading` and `profilesError`, with corrected opacity values (0.45→0.75), updated Save button labels, and actionable error copy.

## What Was Built

### Task 1 — Extend RunContext with profilesLoading and profilesError (commit: 67e7a5f)

Four targeted edits to `frontend/src/lib/run-context.tsx`:

1. Added `profilesLoading: boolean` and `profilesError: string | null` to the `RunCtx` type
2. Added `useState(true)` and `useState<string | null>(null)` declarations inside `RunProvider`
3. Replaced the silent `.catch(() => {})` in `loadProfiles` with full error exposure — `setProfilesLoading(false)` called in BOTH `.then()` and `.catch()` branches (following the auth.tsx analog exactly)
4. Added `profilesLoading, profilesError` to the provider value spread

This fixes the "stuck loading" landmine where API failures left the UI perpetually showing no profiles.

### Task 2 — Update settings/page.tsx (commit: 574f532)

Seven targeted edits to `frontend/src/app/dashboard/settings/page.tsx`:

1. Expanded `useRunContext()` destructure to include `profilesLoading` and `profilesError`
2. Updated form error fallback: `"Failed to add profile"` to `"Failed to add profile — check your connection URL and try again."`
3. Fixed inactive row base opacity: `0.45` to `0.75` (significantly more readable)
4. Fixed `onMouseEnter` hover opacity: `"0.75"` to `"0.90"`
5. Fixed `onMouseLeave` restore opacity: `"0.45"` to `"0.75"`
6. Replaced binary `profiles.length === 0` conditional with four-branch conditional: loading / error / empty / populated
7. Updated Save button labels: `"Save"` to `"Save Changes"`, `"Saving…"` to `"Saving changes…"`

### Task 3 — TypeScript compile gate (verification only, no commit)

`tsc --noEmit` ran against the worktree's frontend source with zero errors. Docker Desktop was not running; dependencies were installed locally (`npm install`) to enable the check — functionally equivalent to the Docker-based check since the same tsconfig.json and TypeScript version apply.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Docker Desktop not running for TypeScript compile gate**
- **Found during:** Task 3
- **Issue:** `docker-compose exec frontend npx tsc --noEmit` failed because Docker Desktop was not running on the host machine
- **Fix:** Ran `npm install` in the worktree's `frontend/` directory to install dependencies locally, then ran `node_modules/.bin/tsc --noEmit` directly against the same source files. Exit code 0, zero errors.
- **Files modified:** None (node_modules is gitignored; no tracked files changed)

## Task 4 — Browser Verification (PENDING HUMAN GATE)

Task 4 is a `checkpoint:human-verify` gate. Human browser testing is required before this plan can be marked complete.

**9-item verification checklist:** See Task 4 in the plan file for the full checklist (inactive row opacity, hover opacity, active row, TopBar persistence, Save button labels, loading state, error state, empty state, form error copy).

## Known Stubs

None. All state branches render real data from the API or deterministic UI copy strings. No hardcoded empty arrays or placeholder text flows to rendering paths.

## Threat Flags

No new threat surface introduced beyond what is documented in the plan's threat model.

Per the threat model (T-06-04): the error render in the Active Environment section uses the fixed copy string `"Could not load profiles — check your connection and reload."` — NOT `{profilesError}`. This prevents credential leakage from raw API error messages. Verified: the implementation matches the spec.

## Self-Check: Tasks 1-3 PASSED (Task 4 pending human verification)

### Files verified to exist:

- `frontend/src/lib/run-context.tsx` — modified, committed at 67e7a5f
- `frontend/src/app/dashboard/settings/page.tsx` — modified, committed at 574f532

### Commits verified:

- `67e7a5f` — feat(06-01): extend RunContext with profilesLoading and profilesError
- `574f532` — feat(06-01): update settings page — opacity, state branches, labels, error copy

### All grep acceptance criteria verified green:

- `profilesLoading: boolean` in RunCtx type: 1 match
- `profilesError: string | null` in RunCtx type: 1 match
- `useState(true)` in RunProvider: 1 match
- `setProfilesLoading(false)` in both branches: 2 matches
- `setProfilesError` calls: 3 matches
- `profilesLoading, profilesError` in provider value: 1 match
- `profilesLoading, profilesError` in settings destructure: 1 match
- `opacity: active ? 1 : 0.75`: 1 match
- `"0.90"` (onMouseEnter): 1 match
- `"0.75"` (onMouseLeave): 1 match
- `Loading profiles…`: 1 match
- `Could not load profiles`: 1 match
- `add a profile to get started`: 1 match
- `database_connection.yaml`: 0 matches
- `Save Changes`: 1 match
- `Saving changes…`: 1 match
- `check your connection URL and try again`: 1 match
- TypeScript compile: exit code 0, zero errors
