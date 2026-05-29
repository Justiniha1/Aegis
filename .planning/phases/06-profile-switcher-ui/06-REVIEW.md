---
phase: 06-profile-switcher-ui
reviewed: 2026-05-29T00:00:00Z
depth: standard
files_reviewed: 2
files_reviewed_list:
  - frontend/src/lib/run-context.tsx
  - frontend/src/app/dashboard/settings/page.tsx
findings:
  critical: 2
  warning: 4
  info: 1
  total: 7
status: issues_found
---

# Phase 6: Code Review Report

**Reviewed:** 2026-05-29
**Depth:** standard
**Files Reviewed:** 2
**Status:** issues_found

## Summary

Two files were reviewed: the shared `RunContext` provider and the Settings page component. The context provider contains two critical correctness bugs — one where a new run will never be polled if triggered while a previous run's terminal status is still cached, and one where an unvalidated API response is used as a typed array, causing silent badge miscounts or crashes. Four warnings address silent error swallowing, a stale-profile selection bug, a misleading "default" badge, and a broken `ToggleRow` component contract.

---

## Critical Issues

### CR-01: New run is never polled when triggered after a previous COMPLETE/FAILED run

**File:** `frontend/src/lib/run-context.tsx:89-108`

**Issue:** The polling `useEffect` guards against re-registering an interval when `runStatusRef.current` is already `"COMPLETE"` or `"FAILED"` (line 91). This guard fires every time `runId` changes, which is exactly when a new run is triggered. If the user clicks "Run All" a second time (after the first run reaches `COMPLETE`), `runId` changes, the effect re-runs, but `runStatusRef.current` is still `"COMPLETE"` from the prior run — so the guard exits immediately and no interval is created. The new run's status is set optimistically at line 118 but is never subsequently polled, leaving the UI frozen on the initial `QUEUED`/`RUNNING` status returned by the trigger endpoint.

**Fix:** Reset `runStatus` (and therefore `runStatusRef.current`) to `null` inside `trigger()` before setting `runId`, so the guard in the polling effect sees a non-terminal state:

```typescript
// In the trigger() callback, before setRunId:
setRunStatus(null);   // clears the terminal state so polling effect will run
setRunId(res.run_id);
setRunStatus(res.status);
```

Alternatively, restructure the guard to compare against the *previous* `runId` rather than the current status.

---

### CR-02: Unvalidated cast of API response to `TestResult[]` causes silent badge corruption

**File:** `frontend/src/lib/run-context.tsx:76-87`

**Issue:** `apiGet` returns `Promise<unknown>` (the underlying `res.json()` is untyped). The `.then((results: TestResult[]) => {...})` annotation is a TypeScript type assertion in the callback parameter position — it does not perform any runtime validation. If the backend returns a paginated envelope `{ items: [...], total: N }`, then `results.length` evaluates to `undefined`, `results[0]` is `undefined`, and `latestRunId` / the filter operations silently produce `NaN`/wrong values. The blanket `.catch(() => {})` ensures this failure is completely invisible.

**Fix:** Add a runtime array check before accessing `.length` or `[0]`:

```typescript
.then((raw: unknown) => {
  if (!Array.isArray(raw) || raw.length === 0) return;
  const results = raw as TestResult[];
  const latestRunId = results[0].run_id;
  // ... rest unchanged
})
.catch(() => {});
```

---

## Warnings

### WR-01: Stale selected profile after profile deletion or re-ordering

**File:** `frontend/src/lib/run-context.tsx:57-61`

**Issue:** After `listProfiles` resolves, the loaded profile list `p` is stored, but `selectedProfile` (which came from `localStorage`) is never validated against `p`. If the currently selected profile was deleted by another session, or if its name changed, `selectedProfile` remains set to a name that no longer exists in `profiles`. Any subsequent `trigger()` call will submit an invalid profile name to the API, producing a backend error at run time — with no user-facing indication that the selection is stale.

**Fix:** After setting profiles, check whether `selectedProfile` is still valid:

```typescript
listProfiles(token).then((p) => {
  setProfiles(p);
  const stored = localStorage.getItem(PROFILE_STORAGE_KEY);
  const stillValid = stored && p.some((prof) => prof.name === stored);
  if (!stillValid && p.length > 0) {
    setSelectedProfile(p[0].name);
  }
  setProfilesLoading(false);
})
```

---

### WR-02: Delete errors silently swallowed — no user feedback on failure

**File:** `frontend/src/app/dashboard/settings/page.tsx:44-55`

**Issue:** `handleDelete` catches all errors and does nothing (`// ignore`). If the API call fails (network error, 403 Forbidden, 409 Conflict because tests are associated with the profile), the UI silently resets `deletingId` to `null` and `refreshProfiles()` is not called. From the user's perspective, the "Removing…" button label flashes and then returns to "Remove" — with no indication that the delete failed. The profile is still present in the list, but the user may believe it was removed.

**Fix:** Surface delete errors to the user:

```typescript
const [deleteError, setDeleteError] = useState<string | null>(null);

async function handleDelete(id: number) {
  if (!token) return;
  setDeletingId(id);
  setDeleteError(null);
  try {
    await deleteProfile(id, token);
    refreshProfiles();
  } catch (err: unknown) {
    setDeleteError(err instanceof Error ? err.message : "Failed to remove profile.");
  } finally {
    setDeletingId(null);
  }
}
```

Then render `deleteError` near the profile list.

---

### WR-03: "default" badge identifies wrong profile after API reorders results

**File:** `frontend/src/app/dashboard/settings/page.tsx:152-163`

**Issue:** The "default" badge is shown when `profiles[0]?.name === p.name`. The auto-selection logic in `run-context.tsx` line 59 also selects `p[0].name` when nothing is stored — so these are initially consistent. However, if a new profile is added and the API returns profiles sorted alphabetically or by creation date, `profiles[0]` in the settings UI will point to a different profile than the one currently selected. The badge then marks a profile as "default" that is not actually the one that would be auto-selected. This is a display-level lie that can confuse users.

**Fix:** Derive "default" from the actual auto-selection logic rather than array position. The simplest fix is to mark the profile that `selectedProfile` references (or would fall back to) as default:

```typescript
// Badge condition: show "default" only when localStorage is empty and this
// is the profile that would be auto-selected.
const isDefault = !localStorage.getItem(PROFILE_STORAGE_KEY) && profiles[0]?.name === p.name;
```

Or more robustly, expose a `defaultProfile` value from the context that is set once during initial load.

---

### WR-04: `ToggleRow` component cannot correctly render `enabled=true` + `disabled=true`

**File:** `frontend/src/app/dashboard/settings/page.tsx:544-608`

**Issue:** The `ToggleRow` component accepts both `enabled` and `disabled` props but the toggle knob's `left` position is computed from `enabled` (line 597: `left: enabled ? "20px" : "4px"`). However when `disabled={true}`, the button element itself is disabled — but the visual state still correctly reflects `enabled`. The real defect is that the component is exported/callable with any combination of `enabled` and `disabled`, but when `disabled=true` and `onChange` is called externally (not through the button click), the internal state never changes because `enabled` is fully controlled from outside. Since no `onChange` is wired to any caller, the toggles are permanently stuck at `enabled=false` with no way to mutate them even if `disabled` is removed in future. The component interface offers `onChange?: (v: boolean) => void` but the three callers at lines 511-531 pass no `onChange`. Future callers adding `onChange` without also managing the `enabled` state externally will see a broken toggle.

**Fix:** Add a comment documenting that `enabled` is fully controlled and `onChange` is required for interactive use, or convert to an internally controlled component. At minimum, make `onChange` required when `disabled` is not true:

```typescript
// Document the contract:
// enabled and onChange must be provided together for interactive use.
// When disabled=true, the visual state is read-only and reflects `enabled` prop.
```

---

## Info

### IN-01: `localStorage` access in `loadProfiles` lacks SSR guard

**File:** `frontend/src/lib/run-context.tsx:59`

**Issue:** Line 59 calls `localStorage.getItem(PROFILE_STORAGE_KEY)` directly, without the `typeof window !== "undefined"` guard that is used at lines 33 and 50. While the `"use client"` directive and the fact that this runs inside a `.then()` callback (asynchronously, always client-side) make this safe in practice today, the pattern is inconsistent with the guards used elsewhere in the same file. If the code is ever refactored to run synchronously or in a server context, this will throw `ReferenceError: localStorage is not defined`.

**Fix:** Apply the same guard pattern used at line 50:

```typescript
if (typeof window !== "undefined" && !localStorage.getItem(PROFILE_STORAGE_KEY) && p.length > 0) {
  setSelectedProfile(p[0].name);
}
```

---

_Reviewed: 2026-05-29_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
