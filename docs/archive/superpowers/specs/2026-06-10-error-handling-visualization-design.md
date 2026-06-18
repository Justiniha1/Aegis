# Error Handling & Visualization — Design

- **Date:** 2026-06-10
- **Status:** Approved (brainstorm) — ready for implementation plan
- **Scope:** Frontend visualization only. No backend capture changes.

## Problem

Comet already captures meaningful error detail at two levels, but the UI surfaces it
inconsistently and drops the most useful pieces entirely:

| Surface | Shows today | Gap |
|---|---|---|
| **Dashboard** (`/dashboard`) | Summary cards, drill-down chart, results table with **inline-accordion rows already showing a metrics grid + SQL** — for the **latest run only** | No run-level failure awareness (reads `/api/v1/results` only, so a FAILED/crashed run shows stale or empty); FAILED-vs-ERROR not visually distinguished |
| **History** (`/dashboard/history`) | A **flat** table: dot, name, type, status, severity, message | No expansion, no metrics, no run-level errors — the poor cousin |
| **TopBar** (every page) | In-progress run pill; a red "Run failed — {reason}" pill after a failure (truncated) | Not clickable; reason truncated; reverts to normal badges |
| **StatusFooter** (every page) | "Engine: failed" (red dot) | No detail, not clickable/expandable |
| **Toast** | — | Does not exist |

Two distinct failure dimensions exist in the data and must be made legible:

1. **Run-level failure** (`Run` row): `status=FAILED` with `error_reason` (sanitized, ≤500 chars)
   + `error_at_test`. Fires on bad profile, no enabled tests, or engine crash mid-run.
   **Currently invisible in the UI** — a run that fails before producing results shows as nothing.
2. **Test-level result** (`TestResult` row): `PASSED | FAILED | ERROR | SKIPPED`, with `severity`,
   a `metrics` dict, and a `message`.
   - `FAILED` = the **data** broke a rule (a quality finding).
   - `ERROR` = the **test couldn't run** (plumbing/config problem).
   - `SKIPPED` = profile/connector missing.

## Goal

Surface, in a clickable/expandable UI, **all** error detail Comet already stores — at both the run
level and the test level — consistently across the Dashboard, History, and the live-run chrome.

## Non-goals (explicitly out of scope)

- Persisting engine tracebacks (currently only `print()`ed to stdout — not stored, so no stack trace
  can be shown).
- Capturing **new** detail per failed test (sample offending rows, the executed SQL for builtin
  tests, row-level breakdown). This would require changes to all 8 builtin test modules and is
  deferred to a future "deep capture" milestone.
- Any backend/API change. The work uses only existing endpoints: `GET /api/v1/runs`,
  `GET /api/v1/runs/{id}`, `GET /api/v1/results`.

## Decisions (locked during brainstorm)

| # | Decision | Rationale |
|---|---|---|
| D1 | Visualization-only; show what we already store | Fastest, frontend-focused; deep capture deferred |
| D2 | Client-side merge of `GET /api/v1/runs` + `GET /api/v1/results` | Fixes invisible-failed-runs with zero backend change; merge is trivial |
| D3 | Apply to **both** Dashboard and History via one shared component | Consistency; History reaches parity, Dashboard gains run-level awareness |
| D4 | Inline accordion for per-test expansion | Most literal "clickable and expandable"; matches the pattern Dashboard already uses |
| D5 | Live = toast on `FAILED` + persistent **expandable** StatusFooter | User chose "both"; TopBar already covers the at-a-glance reason |
| D6 | Color-code the three failure kinds | Distinguish "your data is bad" (FAILED) from "the check is misconfigured" (ERROR) at a glance |

## Architecture

### Components

**`<ErrorDetail result={TestResult} sqlQuery?={string} />`** — one shared component.
Renders the expanded detail for a single test result: the `message`, a **metrics key/value table**
(filtering out non-metric keys: `table`, `column`, `columns`, `expected_columns`, `query`), the test
**config** (table/column/type), and for `custom_sql` the query block. Adds a kind-specific treatment:
- `FAILED` (red): emphasize the violated thresholds in the metrics table.
- `ERROR` (amber): a short "What this means — the test couldn't run; this is not a data failure" note.
- `SKIPPED` (grey) / `PASSED` (green): minimal.

This is extracted from the logic currently inlined in the Dashboard's `ResultsTable` (the
`expandedRow` accordion + metrics grid) and `DetailCard`. Those call sites are refactored to use the
shared component so there is a single source of truth.

**`<RunFailureBanner run={Run} />`** — new. Rendered when `run.status === "FAILED"`. Shows
`error_reason`, the test it died on (`error_at_test`), the profile, timing, and how many of
`total_tests` completed before failure. Uses the existing palette/badges.

**`<Toast />` + a minimal toast controller** — new, small. A single transient, dismissible
notification surface mounted in the dashboard layout. Fires on a run's transition to `FAILED`:
"Run #N failed — {short reason}. View." Auto-dismisses; clicking routes to History for that run.
This is the only genuinely new UI primitive.

**`StatusFooter` (enhanced)** — the existing "Engine: failed" state becomes clickable and
**expands in place** (upward) to show the run-level error (reason + which test). Collapsed by default;
non-intrusive. Links to History for full per-test detail.

**`TopBar`** — already shows the failed pill with the (truncated) reason; no change required, optional
polish to make the pill click-through to the failed run in History.

### Data flow

- **History & Dashboard:** on load (and on `lastCompleted` change), fetch `GET /api/v1/runs` and
  `GET /api/v1/results` in parallel. Drive the run list / "latest run" from `runs` (so FAILED runs
  with zero results appear), and attach results to each run by `run_id`. A run with a `FAILED` status
  renders `<RunFailureBanner>`; its (possibly partial) results render as accordion rows below.
  Accordion expand/collapse and footer expand/collapse are pure client state.
- **Live:** `RunContext` already polls `getRun(runId)` every 2s and stores `runStatus` + `runError`.
  On transition to `FAILED`: fire the toast and flip the StatusFooter to its expandable failed-state.
  Run-level detail is available immediately; full per-test rows are viewed via History once results
  exist. (Open item below.)

## Error model presentation

Three failure kinds, surfaced distinctly on every surface:

1. **Run-level failure** → `<RunFailureBanner>` (Dashboard latest run + History selected run),
   live toast, expandable StatusFooter, TopBar pill.
2. **Test `FAILED`** (data) → red row/dot; metrics table highlights the violated threshold.
3. **Test `ERROR`** (plumbing) → amber row/dot; "what this means" note clarifying it is not a data
   problem.

## Testing

- **Component:** `<ErrorDetail>` renders correct content/color per status kind; metrics table handles
  empty, nested, and odd-typed dicts (reuse `formatMetricValue`). `<RunFailureBanner>` renders
  reason/at_test/progress.
- **History:** a FAILED run with zero results renders the banner (the regression we are fixing);
  accordion expand/collapse works; client-side `runs`×`results` merge attaches results to the right
  run.
- **Live:** StatusFooter flips to the expandable failed-state and the toast fires on the `FAILED`
  transition (mock `RunContext`).
- **Manual:** trigger a real failing run (e.g. a bad profile) against the demo and confirm the banner,
  toast, and expandable footer all show the same reason.

## Constraints

- `frontend/AGENTS.md`: this is a **modified Next.js** — read `node_modules/next/dist/docs/` before
  writing any frontend code; heed deprecation notices.
- **No emojis anywhere** — use existing dots/badges/text only.
- Reuse existing primitives: `StatusBadge`, `SeverityBadge`, `TypePill`, `StatusDot`,
  `STATUS_PALETTE`, `NEUTRAL_SCALE`, `RUN_STATUS_PALETTE`, `formatMetricValue`, `formatConfigKey`.
  Do not introduce a new visual language.

## Open item for the plan

- **Live per-test detail:** the live footer shows only run-level detail; full per-test expansion lives
  on History (reached via the footer/toast links). If live per-test expansion is later wanted, the
  live view would need to fetch `/api/v1/results` for the in-flight run — deferred unless requested.

## Future (deferred)

- Deep capture: persist engine tracebacks; capture sample offending rows and the executed SQL per
  builtin test; drill from "failed" down to the actual bad data. Requires backend + test-module work.
