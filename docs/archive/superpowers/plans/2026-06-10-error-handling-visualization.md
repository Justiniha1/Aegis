# Error Handling & Visualization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface all error detail Comet already stores — run-level failures and per-test FAILED/ERROR detail — in a consistent, clickable/expandable UI across the Dashboard, History, and live-run chrome, with no backend changes.

**Architecture:** Pure frontend. Introduce a Vitest + React Testing Library test runner (the frontend currently has none). Extract the Dashboard's existing inline accordion/metrics logic into a shared `<ErrorDetail>` component, reuse it on History (which lacks it), add a `<RunFailureBanner>` to both pages driven by a client-side merge of `GET /api/v1/runs` × `GET /api/v1/results`, and make the live `StatusFooter` failed-state expandable plus add a failure toast.

**Tech Stack:** Next 16.2.3, React 19.2.4, TypeScript 5, Vitest, @testing-library/react 16, jsdom, recharts (existing).

**Spec:** `docs/superpowers/specs/2026-06-10-error-handling-visualization-design.md`

---

## Pre-flight (read once before starting)

- `frontend/AGENTS.md`: this is a **modified Next.js** — read `node_modules/next/dist/docs/` before writing app/component code; heed deprecation notices. (Vitest runs independently of Next's bundler, so the test runner itself is unaffected.)
- **No emojis anywhere** (UI copy, code comments, commit messages). Use existing dots/badges/text.
- All frontend commands run from the `frontend/` directory.
- Reuse existing primitives — do not invent new colors/components: `StatusBadge`, `SeverityBadge`, `TypePill`, `StatusDot` (`src/components/StatusBadge.tsx`); `STATUS_PALETTE`, `RUN_STATUS_PALETTE`, `RUN_STATUS_LABELS`, `formatConfigKey`, `NEUTRAL_SCALE`, `BRAND_TEAL` (`src/lib/constants.ts`); `formatMetricValue`, `countByStatus` (`src/lib/format.ts`).
- Types already exist in `src/lib/types.ts`: `TestResult`, `Run`, `RunErrorDetail`, `RunStatus`, `RunSummary`, `StatusCounts`. API wrappers already exist in `src/lib/api.ts`: `listRuns(limit, token)`, `getRun(id, token)`, `apiGet(path, token)`.

**Branching note:** the repo is on `main` with pre-existing uncommitted changes (the CLI `.env` fix + demo edits). Before starting, create a feature branch so this work is isolated (do not commit on `main`):
```bash
git checkout -b feature/error-visualization
```

---

## File map

**Create:**
- `frontend/vitest.config.mts` — Vitest config (jsdom, React plugin, `@` alias).
- `frontend/vitest.setup.ts` — registers jest-dom matchers at test time.
- `frontend/src/vitest.d.ts` — loads jest-dom matcher type augmentation for `next build` type-check.
- `frontend/src/lib/error-model.ts` — pure helpers: `failureKind`, `NON_METRIC_KEYS`, `metricEntriesOf`.
- `frontend/src/lib/error-model.test.ts` — unit tests for the above.
- `frontend/src/lib/run-views.ts` — pure helper `buildRunViews` (merge runs × results) + `RunView` type.
- `frontend/src/lib/run-views.test.ts` — unit tests.
- `frontend/src/components/ErrorDetail.tsx` — shared expandable per-test detail.
- `frontend/src/components/ErrorDetail.test.tsx` — component tests.
- `frontend/src/components/RunFailureBanner.tsx` — run-level failure banner.
- `frontend/src/components/RunFailureBanner.test.tsx` — component tests.
- `frontend/src/components/Toast.tsx` — toast primitive + `useToast` controller context.
- `frontend/src/components/Toast.test.tsx` — component test.

**Modify:**
- `frontend/package.json` — add devDeps + `test`/`test:run` scripts.
- `frontend/src/lib/run-context.tsx` — expose full `runError` detail (reason + at_test) and a `runErrorAtTest`; nothing else changes.
- `frontend/src/components/StatusFooter.tsx` — make the FAILED state clickable/expandable.
- `frontend/src/app/dashboard/layout.tsx` — mount `<ToastProvider>` + fire toast on FAILED transition.
- `frontend/src/app/dashboard/history/page.tsx` — fetch runs+results, drive list from runs, add banner + `<ErrorDetail>` accordion.
- `frontend/src/app/dashboard/page.tsx` — use shared `<ErrorDetail>`; add `<RunFailureBanner>` for the latest run.

---

## Task 1: Set up Vitest + React Testing Library

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/vitest.config.mts`, `frontend/vitest.setup.ts`, `frontend/src/vitest.d.ts`

- [ ] **Step 1: Install dev dependencies**

Run (from `frontend/`):
```bash
npm install -D vitest@^3 @vitejs/plugin-react@^4 jsdom@^25 @testing-library/react@^16 @testing-library/dom@^10 @testing-library/jest-dom@^6 @testing-library/user-event@^14
```
Expected: installs without peer-dependency errors (these versions support React 19).

- [ ] **Step 2: Add test scripts to `package.json`**

In `frontend/package.json`, set the `scripts` block to:
```json
"scripts": {
  "dev": "next dev",
  "build": "next build",
  "start": "next start",
  "lint": "eslint",
  "test": "vitest",
  "test:run": "vitest run"
}
```

- [ ] **Step 3: Create `frontend/vitest.config.mts`**

```ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: false,
    setupFiles: ["./vitest.setup.ts"],
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
  },
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
});
```

- [ ] **Step 4: Create `frontend/vitest.setup.ts`**

```ts
// Registers jest-dom matchers (toBeInTheDocument, toHaveTextContent, ...) on Vitest's expect.
import "@testing-library/jest-dom/vitest";
```

- [ ] **Step 5: Create `frontend/src/vitest.d.ts`**

This makes the jest-dom matcher types visible to `next build`'s type-checker (which compiles `*.test.tsx`). It is a declaration file — no runtime emit.
```ts
import "@testing-library/jest-dom/vitest";
```

- [ ] **Step 6: Write a smoke test to prove the runner works**

Create `frontend/src/lib/__smoke__.test.ts`:
```ts
import { describe, it, expect } from "vitest";

describe("vitest smoke", () => {
  it("runs", () => {
    expect(1 + 1).toBe(2);
  });
});
```

- [ ] **Step 7: Run the smoke test**

Run: `npm run test:run`
Expected: 1 passing test. If jsdom/react errors appear, fix config before continuing.

- [ ] **Step 8: Verify the production build still type-checks**

Run: `npm run build`
Expected: build succeeds (confirms the test deps + `vitest.d.ts` don't break `next build`).

- [ ] **Step 9: Delete the smoke test and commit the harness**

```bash
rm src/lib/__smoke__.test.ts
git add package.json package-lock.json vitest.config.mts vitest.setup.ts src/vitest.d.ts
git commit -m "test: add Vitest + React Testing Library harness for frontend"
```

---

## Task 2: Pure helper — failure-kind classifier + metric filtering

This centralizes (a) the FAILED/ERROR/SKIPPED distinction used for color + copy, and (b) the non-metric key filter currently duplicated inline twice in `dashboard/page.tsx`.

**Files:**
- Create: `frontend/src/lib/error-model.ts`, `frontend/src/lib/error-model.test.ts`

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/lib/error-model.test.ts`:
```ts
import { describe, it, expect } from "vitest";
import { failureKind, metricEntriesOf, NON_METRIC_KEYS } from "./error-model";
import type { TestResult } from "./types";

function result(partial: Partial<TestResult>): TestResult {
  return {
    id: 1, test_id: "t", test_name: "T", test_type: "row_count",
    status: "PASSED", severity: "MEDIUM", metrics: {}, message: "",
    run_at: "2026-06-10T00:00:00Z", run_id: 1, table: null, column: null,
    ...partial,
  };
}

describe("failureKind", () => {
  it("maps FAILED to a data finding", () => {
    expect(failureKind(result({ status: "FAILED" }))).toBe("data");
  });
  it("maps ERROR to an execution problem", () => {
    expect(failureKind(result({ status: "ERROR" }))).toBe("execution");
  });
  it("maps SKIPPED to skipped", () => {
    expect(failureKind(result({ status: "SKIPPED" }))).toBe("skipped");
  });
  it("maps PASSED (and anything else) to ok", () => {
    expect(failureKind(result({ status: "PASSED" }))).toBe("ok");
    expect(failureKind(result({ status: "PENDING" }))).toBe("ok");
  });
});

describe("metricEntriesOf", () => {
  it("drops config-ish keys, keeps real metrics", () => {
    const r = result({
      metrics: { row_count: 42, min_rows: 60, table: "orders", column: "id", query: "SELECT 1" },
    });
    const keys = metricEntriesOf(r).map(([k]) => k);
    expect(keys).toContain("row_count");
    expect(keys).toContain("min_rows");
    expect(keys).not.toContain("table");
    expect(keys).not.toContain("column");
    expect(keys).not.toContain("query");
  });
  it("returns [] for empty/missing metrics", () => {
    expect(metricEntriesOf(result({ metrics: {} }))).toEqual([]);
  });
  it("exposes the shared NON_METRIC_KEYS set", () => {
    expect(NON_METRIC_KEYS.has("expected_columns")).toBe(true);
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm run test:run -- src/lib/error-model.test.ts`
Expected: FAIL — cannot resolve `./error-model`.

- [ ] **Step 3: Implement `error-model.ts`**

Create `frontend/src/lib/error-model.ts`:
```ts
import type { TestResult } from "./types";

/** Keys that live in a result's `metrics` dict but describe the test target,
 *  not a measured value — excluded from the metrics display. Mirrors the filter
 *  previously inlined in dashboard/page.tsx. */
export const NON_METRIC_KEYS: ReadonlySet<string> = new Set([
  "table", "column", "columns", "expected_columns", "query",
]);

/** The kind of outcome, used to choose color + explanatory copy.
 *  - "data"      : FAILED — the data broke a rule (a quality finding)
 *  - "execution" : ERROR  — the test itself could not run (plumbing/config)
 *  - "skipped"   : SKIPPED — profile/connector missing
 *  - "ok"        : PASSED or anything else */
export type FailureKind = "data" | "execution" | "skipped" | "ok";

export function failureKind(result: TestResult): FailureKind {
  switch (result.status) {
    case "FAILED": return "data";
    case "ERROR": return "execution";
    case "SKIPPED": return "skipped";
    default: return "ok";
  }
}

/** Real metric key/value pairs for display (config-ish keys removed). */
export function metricEntriesOf(result: TestResult): [string, unknown][] {
  return Object.entries(result.metrics || {}).filter(([k]) => !NON_METRIC_KEYS.has(k));
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `npm run test:run -- src/lib/error-model.test.ts`
Expected: PASS (8 assertions across 7 tests).

- [ ] **Step 5: Commit**

```bash
git add src/lib/error-model.ts src/lib/error-model.test.ts
git commit -m "feat: add failureKind classifier and shared metric-key filter"
```

---

## Task 3: Pure helper — merge runs × results (`buildRunViews`)

Drives the History list from the authoritative `runs` list so FAILED runs with zero results appear (the core gap), attaching results to each run.

**Files:**
- Create: `frontend/src/lib/run-views.ts`, `frontend/src/lib/run-views.test.ts`

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/lib/run-views.test.ts`:
```ts
import { describe, it, expect } from "vitest";
import { buildRunViews } from "./run-views";
import type { Run, TestResult } from "./types";

function run(partial: Partial<Run>): Run {
  return {
    id: 1, client_id: 1, profile: "demo", type_filter: null, status: "COMPLETE",
    total_tests: 0, completed_tests: 0, started_at: "2026-06-10T00:00:00Z",
    completed_at: null, error: null, ...partial,
  };
}
function res(id: number, run_id: number, status = "PASSED"): TestResult {
  return {
    id, test_id: `t${id}`, test_name: `T${id}`, test_type: "row_count",
    status, severity: "MEDIUM", metrics: {}, message: "",
    run_at: "2026-06-10T00:00:00Z", run_id, table: null, column: null,
  };
}

describe("buildRunViews", () => {
  it("includes a FAILED run that has zero results", () => {
    const runs = [run({ id: 5, status: "FAILED", error: { reason: "boom", at_test: 1 } })];
    const views = buildRunViews(runs, []);
    expect(views).toHaveLength(1);
    expect(views[0].run.id).toBe(5);
    expect(views[0].results).toEqual([]);
    expect(views[0].counts.total).toBe(0);
  });

  it("attaches results to their run by run_id", () => {
    const runs = [run({ id: 5 }), run({ id: 6 })];
    const results = [res(1, 5, "FAILED"), res(2, 5, "PASSED"), res(3, 6, "PASSED")];
    const views = buildRunViews(runs, results);
    const v5 = views.find((v) => v.run.id === 5)!;
    expect(v5.results.map((r) => r.id).sort()).toEqual([1, 2]);
    expect(v5.counts.failed).toBe(1);
    expect(v5.counts.passed).toBe(1);
  });

  it("sorts runs newest-first by id", () => {
    const views = buildRunViews([run({ id: 1 }), run({ id: 9 }), run({ id: 4 })], []);
    expect(views.map((v) => v.run.id)).toEqual([9, 4, 1]);
  });

  it("drops orphan results whose run_id is not in the runs list", () => {
    const views = buildRunViews([run({ id: 5 })], [res(1, 999)]);
    expect(views[0].results).toEqual([]);
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm run test:run -- src/lib/run-views.test.ts`
Expected: FAIL — cannot resolve `./run-views`.

- [ ] **Step 3: Implement `run-views.ts`**

Create `frontend/src/lib/run-views.ts`:
```ts
import type { Run, TestResult } from "./types";
import { countByStatus, type StatusCounts } from "./format";

/** A run paired with its (possibly empty) results and tallies. The run list and
 *  detail panels render from these so a FAILED run with no results is still shown. */
export interface RunView {
  run: Run;
  results: TestResult[];
  counts: StatusCounts;
}

/** Join authoritative runs with a flat result list. Runs drive the output
 *  (so zero-result failures appear); results are bucketed by run_id; runs are
 *  returned newest-first by id; results with no matching run are dropped. */
export function buildRunViews(runs: Run[], results: TestResult[]): RunView[] {
  const byRun = new Map<number, TestResult[]>();
  for (const r of results) {
    if (r.run_id == null) continue;
    const list = byRun.get(r.run_id) ?? [];
    list.push(r);
    byRun.set(r.run_id, list);
  }
  return [...runs]
    .sort((a, b) => b.id - a.id)
    .map((run) => {
      const rs = byRun.get(run.id) ?? [];
      return { run, results: rs, counts: countByStatus(rs) };
    });
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `npm run test:run -- src/lib/run-views.test.ts`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/lib/run-views.ts src/lib/run-views.test.ts
git commit -m "feat: add buildRunViews to merge runs with results"
```

---

## Task 4: Shared `<ErrorDetail>` component (+ refactor Dashboard to use it)

Extract the metrics-grid / SQL-block accordion body (currently inlined in `dashboard/page.tsx` `ResultsTable` and `DetailCard`) into one component, adding the failure-kind treatment.

**Files:**
- Create: `frontend/src/components/ErrorDetail.tsx`, `frontend/src/components/ErrorDetail.test.tsx`
- Modify: `frontend/src/app/dashboard/page.tsx` (use the shared component in both expand sites)

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/components/ErrorDetail.test.tsx`:
```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ErrorDetail } from "./ErrorDetail";
import type { TestResult } from "@/lib/types";

function result(p: Partial<TestResult>): TestResult {
  return {
    id: 1, test_id: "t", test_name: "T", test_type: "row_count",
    status: "FAILED", severity: "HIGH", metrics: {}, message: "msg",
    run_at: "2026-06-10T00:00:00Z", run_id: 1, table: null, column: null, ...p,
  };
}

describe("ErrorDetail", () => {
  it("renders the message and metric rows for a FAILED data finding", () => {
    render(<ErrorDetail result={result({ status: "FAILED", message: "row count 42 < 60", metrics: { row_count: 42, min_rows: 60 } })} />);
    expect(screen.getByText("row count 42 < 60")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.getByText("60")).toBeInTheDocument();
  });

  it("shows an execution-error explanation for ERROR results", () => {
    render(<ErrorDetail result={result({ status: "ERROR", message: "column missing" })} />);
    expect(screen.getByText(/could not run/i)).toBeInTheDocument();
  });

  it("renders the SQL block when a query is provided", () => {
    render(<ErrorDetail result={result({ test_type: "custom_sql" })} sqlQuery="SELECT 1" />);
    expect(screen.getByText("SELECT 1")).toBeInTheDocument();
  });

  it("does not show the execution note for a data failure", () => {
    render(<ErrorDetail result={result({ status: "FAILED" })} />);
    expect(screen.queryByText(/could not run/i)).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm run test:run -- src/components/ErrorDetail.test.tsx`
Expected: FAIL — cannot resolve `./ErrorDetail`.

- [ ] **Step 3: Implement `ErrorDetail.tsx`**

Create `frontend/src/components/ErrorDetail.tsx`:
```tsx
"use client";

import { useTheme } from "@/lib/theme";
import { NEUTRAL_SCALE, STATUS_PALETTE, formatConfigKey } from "@/lib/constants";
import { formatMetricValue } from "@/lib/format";
import { failureKind, metricEntriesOf } from "@/lib/error-model";
import type { TestResult } from "@/lib/types";

/** Expandable per-test detail body. Shared by the Dashboard results table,
 *  the Dashboard drill-down detail list, and the History run panel. */
export function ErrorDetail({ result, sqlQuery }: { result: TestResult; sqlQuery?: string }) {
  const { theme } = useTheme();
  const dark = theme === "dark";
  const palette = dark ? NEUTRAL_SCALE.dark : NEUTRAL_SCALE.light;
  const kind = failureKind(result);
  const metricEntries = metricEntriesOf(result);
  const isCustomSql = result.test_type === "custom_sql";

  const cardStyle: React.CSSProperties = {
    backgroundColor: palette.surfaceElevated,
    border: `1px solid ${palette.borderSubtle}`,
    borderRadius: "8px",
  };

  return (
    <div className="space-y-3">
      {result.message && (
        <p
          className="text-body"
          style={{ color: kind === "data" ? STATUS_PALETTE.FAILED : palette.textSecondary }}
        >
          {result.message}
        </p>
      )}

      {kind === "execution" && (
        <p className="text-caption" style={{ color: palette.textSecondary, textTransform: "none", letterSpacing: "0" }}>
          The test itself could not run — this is a configuration or connection problem, not a data
          failure. Fix the test setup and re-run.
        </p>
      )}

      {isCustomSql && sqlQuery && (
        <div className="overflow-hidden" style={cardStyle}>
          <div
            className="px-4 py-2 font-mono text-xs"
            style={{ borderBottom: `1px solid ${palette.borderSubtle}`, color: palette.textSecondary }}
          >
            query
          </div>
          <pre
            className="px-4 py-3 font-mono text-xs overflow-x-auto whitespace-pre max-h-64 overflow-y-auto"
            style={{ color: palette.textPrimary }}
          >
            <code>{sqlQuery}</code>
          </pre>
        </div>
      )}

      {metricEntries.length > 0 && (
        <div className="grid grid-cols-3 gap-3">
          {metricEntries.map(([key, val]) => (
            <div key={key} className="px-3 py-2" style={cardStyle}>
              <p className="text-caption" style={{ color: palette.textSecondary }}>{formatConfigKey(key)}</p>
              <p
                className="text-body font-medium mt-0.5 truncate"
                style={{ color: palette.textPrimary }}
                title={typeof val === "object" ? JSON.stringify(val) : String(val)}
              >
                {formatMetricValue(val)}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `npm run test:run -- src/components/ErrorDetail.test.tsx`
Expected: PASS (4 tests).

- [ ] **Step 5: Refactor `dashboard/page.tsx` `ResultsTable` to use `<ErrorDetail>`**

In `frontend/src/app/dashboard/page.tsx`, add the import near the other component imports:
```tsx
import { ErrorDetail } from "@/components/ErrorDetail";
```
Then, inside `ResultsTable`, replace the expanded-row body. The current expanded `<td colSpan={9} ...>` content (the `isCustomSql && sqlQuery` block plus the `metricEntries.length > 0` grid, lines ~893-942) becomes:
```tsx
<td colSpan={9} className="px-12 py-3" style={{ backgroundColor: palette.surfaceBg }}>
  <ErrorDetail result={r} sqlQuery={sqlQuery} />
</td>
```
Keep the existing `hasExpandContent` gate and the `expandedRow` toggle logic unchanged. You may remove the now-unused local `metricEntries`/`isCustomSql` computations in the row body **only if** they are no longer referenced after this change (the `hasExpandContent` check still needs them — keep what it uses).

- [ ] **Step 6: Refactor `DetailCard` (same file) to use `<ErrorDetail>`**

In `DetailCard`, replace the two `expanded && ...` blocks (the SQL block and the metrics grid, lines ~1019-1069) with a single block that reuses the component while keeping the message line above it:
```tsx
{expanded && (
  <div className="mt-3 ml-6">
    <ErrorDetail result={r} sqlQuery={sqlQuery} />
  </div>
)}
```
Note: `ErrorDetail` also renders `result.message`; to avoid showing the message twice, keep `DetailCard`'s own message `<p>` for the **collapsed** preview only — wrap it so it shows when `!expanded`:
```tsx
{r.message && !expanded && (
  <p className="text-body mt-1.5 ml-6 line-clamp-2" style={{ color: palette.textSecondary }} title={r.message}>
    {r.message}
  </p>
)}
```

- [ ] **Step 7: Verify build + existing behavior**

Run: `npm run build`
Expected: build succeeds with no type errors.
Run: `npm run test:run`
Expected: all tests pass.

- [ ] **Step 8: Manual check (Dashboard)**

Start the app per the project workflow (`make start` from repo root — do NOT use `npm run dev`). Trigger a run, open `/dashboard`, expand a failed row and a custom_sql row. Confirm metrics grid + SQL render identically to before, and an ERROR row now shows the "could not run" note.

- [ ] **Step 9: Commit**

```bash
git add src/components/ErrorDetail.tsx src/components/ErrorDetail.test.tsx src/app/dashboard/page.tsx
git commit -m "refactor: extract shared ErrorDetail component, use on Dashboard"
```

---

## Task 5: `<RunFailureBanner>` component

**Files:**
- Create: `frontend/src/components/RunFailureBanner.tsx`, `frontend/src/components/RunFailureBanner.test.tsx`

- [ ] **Step 1: Write the failing tests**

Create `frontend/src/components/RunFailureBanner.test.tsx`:
```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { RunFailureBanner } from "./RunFailureBanner";
import type { Run } from "@/lib/types";

function run(p: Partial<Run>): Run {
  return {
    id: 12, client_id: 1, profile: "demo", type_filter: null, status: "FAILED",
    total_tests: 7, completed_tests: 3, started_at: "2026-06-10T14:02:11Z",
    completed_at: "2026-06-10T14:02:40Z", error: { reason: "Engine crashed at test 4", at_test: 4 }, ...p,
  };
}

describe("RunFailureBanner", () => {
  it("renders the reason, run id, and progress for a failed run", () => {
    render(<RunFailureBanner run={run({})} />);
    expect(screen.getByText(/Engine crashed at test 4/)).toBeInTheDocument();
    expect(screen.getByText(/Run #12/)).toBeInTheDocument();
    expect(screen.getByText(/3 of 7/)).toBeInTheDocument();
  });

  it("renders nothing for a non-failed run", () => {
    const { container } = render(<RunFailureBanner run={run({ status: "COMPLETE", error: null })} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("handles a failed run with no error detail", () => {
    render(<RunFailureBanner run={run({ error: null })} />);
    expect(screen.getByText(/Run #12 failed/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm run test:run -- src/components/RunFailureBanner.test.tsx`
Expected: FAIL — cannot resolve `./RunFailureBanner`.

- [ ] **Step 3: Implement `RunFailureBanner.tsx`**

Create `frontend/src/components/RunFailureBanner.tsx`:
```tsx
"use client";

import { useTheme } from "@/lib/theme";
import { NEUTRAL_SCALE, STATUS_PALETTE } from "@/lib/constants";
import type { Run } from "@/lib/types";

/** Run-level failure banner. Renders only when the run FAILED. Surfaces the
 *  sanitized error reason, which test it died on, the profile, and progress —
 *  the detail that is otherwise invisible for runs that produced no results. */
export function RunFailureBanner({ run }: { run: Run }) {
  const { theme } = useTheme();
  const dark = theme === "dark";
  const palette = dark ? NEUTRAL_SCALE.dark : NEUTRAL_SCALE.light;

  if (run.status !== "FAILED") return null;

  const reason = run.error?.reason;
  const atTest = run.error?.at_test ?? null;

  return (
    <div
      className="px-4 py-3"
      style={{
        backgroundColor: `${STATUS_PALETTE.FAILED}14`,
        borderBottom: `1px solid ${STATUS_PALETTE.FAILED}`,
        borderTopLeftRadius: "8px",
        borderTopRightRadius: "8px",
      }}
      role="alert"
    >
      <p className="text-body font-semibold" style={{ color: STATUS_PALETTE.FAILED }}>
        Run #{run.id} failed
        {atTest != null ? ` at test ${atTest}` : ""}
      </p>
      <p className="text-caption mt-1" style={{ color: palette.textSecondary, textTransform: "none", letterSpacing: "0" }}>
        profile: {run.profile} · ran {run.completed_tests} of {run.total_tests} test
        {run.total_tests !== 1 ? "s" : ""} before failing
      </p>
      {reason && (
        <p
          className="text-caption mt-1 font-mono"
          style={{ color: palette.textPrimary, textTransform: "none", letterSpacing: "0" }}
        >
          {reason}
        </p>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `npm run test:run -- src/components/RunFailureBanner.test.tsx`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/components/RunFailureBanner.tsx src/components/RunFailureBanner.test.tsx
git commit -m "feat: add RunFailureBanner for run-level failures"
```

---

## Task 6: History page — runs×results merge, banner, accordion detail

Bring History to parity: drive the list from runs (so failed runs appear), add the banner, and make each result row an accordion that expands `<ErrorDetail>`.

**Files:**
- Modify: `frontend/src/app/dashboard/history/page.tsx`

- [ ] **Step 1: Manual-test baseline note**

Before editing, note current behavior: History shows only runs that produced results, a flat table, no metrics. After this task: all runs appear (including FAILED with zero results), each row expands.

- [ ] **Step 2: Replace data loading to fetch runs + results**

In `frontend/src/app/dashboard/history/page.tsx`, update imports:
```tsx
import { apiGet, listRuns } from "@/lib/api";
import { buildRunViews, type RunView } from "@/lib/run-views";
import { RunFailureBanner } from "@/components/RunFailureBanner";
import { ErrorDetail } from "@/components/ErrorDetail";
import type { TestResult } from "@/lib/types";
```
Replace the `results` state + effect (lines ~31-43) with both fetches and derived views:
```tsx
const [runs, setRuns] = useState<Run[]>([]);
const [results, setResults] = useState<TestResult[]>([]);
const [loading, setLoading] = useState(true);
const [selectedRun, setSelectedRun] = useState<number | null>(null);
const [visibleRuns, setVisibleRuns] = useState(RUNS_PAGE_SIZE);
const [expandedRow, setExpandedRow] = useState<number | null>(null);

useEffect(() => {
  if (authLoading) return;
  if (!token) { router.push("/login"); return; }
  Promise.all([
    listRuns(1000, token),
    apiGet("/api/v1/results?limit=1000", token),
  ])
    .then(([rs, res]) => { setRuns(rs); setResults(res as TestResult[]); })
    .catch(() => router.push("/login"))
    .finally(() => setLoading(false));
}, [token, authLoading, router]);
```
Add `import type { Run } from "@/lib/types";` to the types import.

- [ ] **Step 3: Derive RunViews instead of the old runMap/runs memo**

Replace the `useMemo` that builds `runMap`/`runs` (lines ~45-60) with:
```tsx
const views: RunView[] = useMemo(() => buildRunViews(runs, results), [runs, results]);
const selectedView = selectedRun != null ? views.find((v) => v.run.id === selectedRun) ?? null : null;
```
Delete references to the old `runMap`, `runs` summaries, `selectedResults`, `selectedRunSummary`; they are replaced by `views` and `selectedView`.

- [ ] **Step 4: Update the run list rendering to use `views`**

In the run-list `.map`, iterate `views.slice(0, visibleRuns)`; for each `v`, use `v.run.id` as key, `v.run.started_at` for the timestamp, `v.counts` for the passed/failed/error tallies, and add a FAILED marker. Replace the list item button body's counts/bar with:
```tsx
{v.run.status === "FAILED" ? (
  <div className="flex gap-3 mt-2 text-caption" style={{ textTransform: "none", letterSpacing: "0" }}>
    <span style={{ color: STATUS_PALETTE.FAILED }}>Run failed</span>
  </div>
) : (
  <>
    <div className="flex gap-3 mt-2 text-caption" style={{ textTransform: "none", letterSpacing: "0" }}>
      <span style={{ color: STATUS_PALETTE.PASSED }}>{v.counts.passed} passed</span>
      {v.counts.failed > 0 && <span style={{ color: STATUS_PALETTE.FAILED }}>{v.counts.failed} failed</span>}
      {v.counts.errors > 0 && <span style={{ color: STATUS_PALETTE.ERROR }}>{v.counts.errors} errors</span>}
    </div>
    <div className="mt-2 w-full h-1.5 rounded-full overflow-hidden flex" style={{ backgroundColor: palette.borderSubtle }}>
      <div className="h-full" style={{ width: `${v.counts.total ? (v.counts.passed / v.counts.total) * 100 : 0}%`, backgroundColor: STATUS_PALETTE.PASSED }} />
      <div className="h-full" style={{ width: `${v.counts.total ? (v.counts.failed / v.counts.total) * 100 : 0}%`, backgroundColor: STATUS_PALETTE.FAILED }} />
      <div className="h-full" style={{ width: `${v.counts.total ? (v.counts.errors / v.counts.total) * 100 : 0}%`, backgroundColor: STATUS_PALETTE.ERROR }} />
    </div>
  </>
)}
```
Update the empty-state guard to `views.length === 0`, and the "N runs" / "Show more" counts to use `views.length`.

- [ ] **Step 5: Update the detail panel — banner + accordion rows**

Replace the detail panel (the `selectedRun ? (...)` block) so it renders the banner and an accordion table from `selectedView`:
```tsx
{selectedView ? (
  <div className="overflow-hidden" style={{ backgroundColor: palette.surfaceElevated, border: `1px solid ${palette.borderSubtle}`, borderRadius: "8px" }}>
    <RunFailureBanner run={selectedView.run} />
    <div className="px-6 py-4" style={{ borderBottom: `1px solid ${palette.borderSubtle}` }}>
      <h2 className="text-heading" style={{ color: palette.textPrimary }}>
        Run at <span style={{ fontFamily: "var(--font-jetbrains-mono)" }}>{new Date(selectedView.run.started_at).toLocaleString()}</span>
      </h2>
      <div className="flex gap-4 mt-1 text-caption" style={{ textTransform: "none", letterSpacing: "0" }}>
        <span style={{ color: palette.textSecondary }}>{selectedView.counts.total} total</span>
        <span style={{ color: STATUS_PALETTE.PASSED }}>{selectedView.counts.passed} passed</span>
        {selectedView.counts.failed > 0 && <span style={{ color: STATUS_PALETTE.FAILED }}>{selectedView.counts.failed} failed</span>}
        {selectedView.counts.errors > 0 && <span style={{ color: STATUS_PALETTE.ERROR }}>{selectedView.counts.errors} errors</span>}
      </div>
    </div>
    {selectedView.results.length === 0 ? (
      <div className="px-6 py-10 text-center text-body" style={{ color: palette.textSecondary }}>
        {selectedView.run.status === "FAILED" ? "This run failed before producing any test results." : "No results for this run."}
      </div>
    ) : (
      <table className="w-full text-sm">
        <thead style={{ backgroundColor: palette.surfaceBg }}>
          <tr style={{ color: palette.textSecondary }}>
            <th className="pl-6 py-3" style={{ width: "24px" }}></th>
            <th className="px-2 py-3" style={{ width: "24px" }}></th>
            <th className="px-4 py-3 text-left text-caption">Test</th>
            <th className="px-4 py-3 text-left text-caption">Type</th>
            <th className="px-4 py-3 text-left text-caption">Status</th>
            <th className="px-4 py-3 text-left text-caption">Severity</th>
            <th className="px-4 py-3 text-left text-caption">Message</th>
          </tr>
        </thead>
        <tbody>
          {selectedView.results.map((r) => {
            const isExpanded = expandedRow === r.id;
            return (
              <Fragment key={r.id}>
                <tr
                  className="transition-colors cursor-pointer"
                  style={{ height: "40px", borderTop: `1px solid ${palette.borderSubtle}` }}
                  onClick={() => setExpandedRow(isExpanded ? null : r.id)}
                >
                  <td className="pl-6 py-3"><StatusDot status={r.status} /></td>
                  <td className="px-2 py-3 text-caption" style={{ color: palette.textSecondary, textTransform: "none", letterSpacing: "0" }}>{isExpanded ? "▼" : "▶"}</td>
                  <td className="px-4 py-3 max-w-xs truncate text-body" style={{ fontFamily: "var(--font-jetbrains-mono)", color: palette.textPrimary }} title={r.test_name}>{r.test_name}</td>
                  <td className="px-4 py-3"><TypePill type={r.test_type} /></td>
                  <td className="px-4 py-3"><StatusBadge status={r.status} /></td>
                  <td className="px-4 py-3"><SeverityBadge severity={r.severity} /></td>
                  <td className="px-4 py-3 text-body max-w-xs truncate" style={{ color: palette.textSecondary }} title={r.message}>{r.message}</td>
                </tr>
                {isExpanded && (
                  <tr style={{ borderTop: `1px solid ${palette.borderSubtle}` }}>
                    <td colSpan={7} className="px-12 py-3" style={{ backgroundColor: palette.surfaceBg }}>
                      <ErrorDetail result={r} />
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    )}
  </div>
) : (
  <div className="flex items-center justify-center h-64 text-body" style={{ border: `1px dashed ${palette.borderSubtle}`, borderRadius: "8px", color: palette.textSecondary }}>
    Select a run to see details
  </div>
)}
```
Add `Fragment` to the React import: `import { Fragment, useEffect, useMemo, useState } from "react";`

- [ ] **Step 6: Build + tests**

Run: `npm run build`
Expected: succeeds, no type errors (watch for leftover references to the deleted `runMap`/`selectedResults`).
Run: `npm run test:run`
Expected: all pass.

- [ ] **Step 7: Manual check (History)**

Start the app (`make start`). Open `/dashboard/history`. Confirm: (a) all runs listed including any FAILED ones; (b) selecting a FAILED run shows the banner and the "failed before producing any results" message when empty; (c) selecting a normal run lets you expand each row to see metrics.

- [ ] **Step 8: Commit**

```bash
git add src/app/dashboard/history/page.tsx
git commit -m "feat: History shows run-level failures and expandable per-test detail"
```

---

## Task 7: Dashboard — run-level failure banner for the latest run

The Dashboard already shows the latest run's per-test table; add run-level awareness so a failed latest run isn't silent.

**Files:**
- Modify: `frontend/src/app/dashboard/page.tsx`

- [ ] **Step 1: Fetch the latest run alongside results**

In `dashboard/page.tsx`, add `listRuns` to the api import and a `latestRun` state:
```tsx
import { apiGet, listRuns } from "@/lib/api";
```
Add state near the other `useState`s:
```tsx
const [latestRun, setLatestRun] = useState<Run | null>(null);
```
Add `import type { Run } from "@/lib/types";` to the type import line.
Extend the existing `Promise.all` (lines ~133-139) to also fetch runs and keep the newest:
```tsx
Promise.all([
  apiGet("/api/v1/results?limit=500", token),
  apiGet("/api/v1/tests", token),
  listRuns(50, token),
])
  .then(([res, defs, runs]: [TestResult[], TestDefinition[], Run[]]) => {
    setResults(res); setTestDefs(defs);
    const newest = [...runs].sort((a, b) => b.id - a.id)[0] ?? null;
    setLatestRun(newest);
  })
  .catch(() => router.push("/login"))
  .finally(() => setLoading(false));
```

- [ ] **Step 2: Render the banner above the results table**

Add the import:
```tsx
import { RunFailureBanner } from "@/components/RunFailureBanner";
```
In the returned JSX, immediately before `<ResultsTable .../>` (line ~526), add:
```tsx
{latestRun && <RunFailureBanner run={latestRun} />}
```
Wrap so the banner sits in the normal flow with spacing consistent with the page's `space-y-6`.

- [ ] **Step 3: Build + tests**

Run: `npm run build` — expected success.
Run: `npm run test:run` — expected all pass.

- [ ] **Step 4: Manual check**

Start the app, trigger a run against a bad profile (so the run FAILS), open `/dashboard`. Confirm the banner appears with the reason. Trigger a normal run; confirm the banner disappears.

- [ ] **Step 5: Commit**

```bash
git add src/app/dashboard/page.tsx
git commit -m "feat: show RunFailureBanner on Dashboard for failed latest run"
```

---

## Task 8: Toast primitive + provider

**Files:**
- Create: `frontend/src/components/Toast.tsx`, `frontend/src/components/Toast.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/components/Toast.test.tsx`:
```tsx
import { describe, it, expect } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { ToastProvider, useToast } from "./Toast";

function Trigger() {
  const { showToast } = useToast();
  return <button onClick={() => showToast({ message: "Run #12 failed", href: "/dashboard/history" })}>fire</button>;
}

describe("Toast", () => {
  it("shows a toast message when showToast is called", async () => {
    render(<ToastProvider><Trigger /></ToastProvider>);
    expect(screen.queryByText("Run #12 failed")).not.toBeInTheDocument();
    await act(async () => { screen.getByText("fire").click(); });
    expect(screen.getByText("Run #12 failed")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm run test:run -- src/components/Toast.test.tsx`
Expected: FAIL — cannot resolve `./Toast`.

- [ ] **Step 3: Implement `Toast.tsx`**

Create `frontend/src/components/Toast.tsx`:
```tsx
"use client";

import { createContext, useCallback, useContext, useRef, useState } from "react";
import Link from "next/link";
import { useTheme } from "@/lib/theme";
import { NEUTRAL_SCALE, STATUS_PALETTE } from "@/lib/constants";

interface ToastPayload { message: string; href?: string; }
interface ToastCtx { showToast: (t: ToastPayload) => void; }

const Ctx = createContext<ToastCtx | null>(null);
const AUTO_DISMISS_MS = 8000;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const { theme } = useTheme();
  const dark = theme === "dark";
  const palette = dark ? NEUTRAL_SCALE.dark : NEUTRAL_SCALE.light;
  const [toast, setToast] = useState<ToastPayload | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const showToast = useCallback((t: ToastPayload) => {
    if (timer.current) clearTimeout(timer.current);
    setToast(t);
    timer.current = setTimeout(() => setToast(null), AUTO_DISMISS_MS);
  }, []);

  const dismiss = useCallback(() => {
    if (timer.current) clearTimeout(timer.current);
    setToast(null);
  }, []);

  return (
    <Ctx.Provider value={{ showToast }}>
      {children}
      {toast && (
        <div
          role="status"
          className="fixed bottom-12 right-6 z-50 max-w-sm px-4 py-3 flex items-start gap-3"
          style={{
            backgroundColor: palette.surfaceElevated,
            border: `1px solid ${STATUS_PALETTE.FAILED}`,
            borderRadius: "8px",
            boxShadow: "0 6px 20px rgb(0 0 0 / 0.18)",
          }}
        >
          <span style={{ display: "inline-block", marginTop: "5px", width: "8px", height: "8px", borderRadius: "9999px", backgroundColor: STATUS_PALETTE.FAILED, flex: "0 0 auto" }} />
          <div className="min-w-0">
            <p className="text-body" style={{ color: palette.textPrimary }}>{toast.message}</p>
            {toast.href && (
              <Link href={toast.href} onClick={dismiss} className="text-caption" style={{ color: STATUS_PALETTE.FAILED, textTransform: "none", letterSpacing: "0" }}>
                View detail
              </Link>
            )}
          </div>
          <button onClick={dismiss} aria-label="Dismiss" className="text-caption" style={{ color: palette.textSecondary, background: "none", border: "none", cursor: "pointer" }}>
            Close
          </button>
        </div>
      )}
    </Ctx.Provider>
  );
}

export function useToast(): ToastCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useToast must be used inside ToastProvider");
  return ctx;
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npm run test:run -- src/components/Toast.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/components/Toast.tsx src/components/Toast.test.tsx
git commit -m "feat: add Toast provider primitive"
```

---

## Task 9: Wire the live failure — RunContext detail, expandable footer, toast on FAILED

**Files:**
- Modify: `frontend/src/lib/run-context.tsx`, `frontend/src/components/StatusFooter.tsx`, `frontend/src/app/dashboard/layout.tsx`

- [ ] **Step 1: Expose `runErrorAtTest` from RunContext**

In `run-context.tsx`, add to the `RunCtx` type: `runErrorAtTest: number | null;`. Add state `const [runErrorAtTest, setRunErrorAtTest] = useState<number | null>(null);`. In the poll effect where `if (run.error) setRunError(run.error.reason);`, also set `setRunErrorAtTest(run.error?.at_test ?? null);`. In `trigger()` where `setRunError(null)`, also `setRunErrorAtTest(null)`. Add `runErrorAtTest` to the provider `value`.

- [ ] **Step 2: Make `StatusFooter` expandable on FAILED**

Rewrite `frontend/src/components/StatusFooter.tsx` to accept the error detail and expand in place:
```tsx
"use client";

import { useState } from "react";
import type { RunStatus } from "@/lib/types";
import { NEUTRAL_SCALE, STATUS_PALETTE, RUN_STATUS_PALETTE } from "@/lib/constants";

const ENGINE_STATES: Record<string, { label: string; color: string; pulse: boolean }> = {
  QUEUED:   { label: "Engine: queued",   color: RUN_STATUS_PALETTE.QUEUED,   pulse: false },
  RUNNING:  { label: "Engine: running",  color: RUN_STATUS_PALETTE.RUNNING,  pulse: true  },
  COMPLETE: { label: "Engine: finished", color: STATUS_PALETTE.PASSED,       pulse: false },
  FAILED:   { label: "Engine: failed",   color: STATUS_PALETTE.FAILED,       pulse: false },
};

export function StatusFooter({
  dark, runStatus, runError, runErrorAtTest,
}: {
  dark: boolean;
  runStatus?: RunStatus | null;
  runError?: string | null;
  runErrorAtTest?: number | null;
}) {
  const palette = dark ? NEUTRAL_SCALE.dark : NEUTRAL_SCALE.light;
  const [expanded, setExpanded] = useState(false);

  const state = runStatus ? ENGINE_STATES[runStatus] : null;
  const dotColor = state ? state.color : STATUS_PALETTE.SKIPPED;
  const label    = state ? state.label : "Engine: idle";
  const pulse    = state?.pulse ?? false;
  const isFailed = runStatus === "FAILED";

  return (
    <div className="relative">
      {isFailed && expanded && (
        <div
          className="absolute bottom-full left-0 right-0 px-6 py-3"
          style={{ backgroundColor: palette.surfaceElevated, borderTop: `1px solid ${STATUS_PALETTE.FAILED}` }}
        >
          <p className="text-caption font-semibold" style={{ color: STATUS_PALETTE.FAILED, textTransform: "none", letterSpacing: "0" }}>
            Run failed{runErrorAtTest != null ? ` at test ${runErrorAtTest}` : ""}
          </p>
          {runError && (
            <p className="text-caption mt-1 font-mono" style={{ color: palette.textPrimary, textTransform: "none", letterSpacing: "0" }}>
              {runError}
            </p>
          )}
        </div>
      )}
      <footer
        className="flex items-center px-6"
        style={{ height: "32px", backgroundColor: palette.surfaceElevated, borderTop: `1px solid ${palette.borderSubtle}`, cursor: isFailed ? "pointer" : "default" }}
        onClick={() => isFailed && setExpanded((e) => !e)}
      >
        <span className="flex items-center gap-2 text-[13px]" style={{ color: isFailed ? STATUS_PALETTE.FAILED : palette.textSecondary }}>
          <span style={{ display: "inline-block", width: "6px", height: "6px", borderRadius: "9999px", backgroundColor: dotColor, animation: pulse ? "pulse 1.5s ease-in-out infinite" : "none", transition: "background-color 300ms" }} />
          {label}
          {isFailed && <span className="text-caption" style={{ textTransform: "none", letterSpacing: "0" }}>{expanded ? "— hide detail" : "— click for detail"}</span>}
        </span>
      </footer>
    </div>
  );
}
```

- [ ] **Step 3: Mount `ToastProvider` + fire toast on FAILED in the layout**

In `frontend/src/app/dashboard/layout.tsx`:
- Import: `import { ToastProvider, useToast } from "@/components/Toast";` and `import { useEffect, useRef } from "react";`
- Wrap the inner layout in the provider. Change `DashboardLayout`:
```tsx
export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <RunProvider>
      <ToastProvider>
        <DashboardLayoutInner>{children}</DashboardLayoutInner>
      </ToastProvider>
    </RunProvider>
  );
}
```
- In `DashboardLayoutInner`, pull `runError`, `runErrorAtTest`, `runId` from `useRunContext()` and `showToast` from `useToast()`. Fire the toast once per failed run:
```tsx
const { showToast } = useToast();
const { runId, runError, runErrorAtTest } = useRunContext(); // add to existing destructure
const lastToasted = useRef<number | null>(null);
useEffect(() => {
  if (runStatus === "FAILED" && runId && lastToasted.current !== runId) {
    lastToasted.current = runId;
    showToast({
      message: `Run #${runId} failed${runError ? ` — ${runError}` : ""}`,
      href: "/dashboard/history",
    });
  }
}, [runStatus, runId, runError, showToast]);
```
- Pass the new props to the footer:
```tsx
<StatusFooter dark={dark} runStatus={runStatus} runError={runError} runErrorAtTest={runErrorAtTest} />
```

- [ ] **Step 4: Build + tests**

Run: `npm run build` — expected success.
Run: `npm run test:run` — expected all pass.

- [ ] **Step 5: Manual check (live)**

Start the app (`make start`). Trigger a run against a bad profile from any dashboard page. Confirm: (a) a toast appears bottom-right with the reason and a "View detail" link to History; (b) the StatusFooter turns red and, when clicked, expands to show the reason; (c) triggering a normal run clears the failed state.

- [ ] **Step 6: Commit**

```bash
git add src/lib/run-context.tsx src/components/StatusFooter.tsx src/app/dashboard/layout.tsx
git commit -m "feat: live run failure toast + expandable StatusFooter detail"
```

---

## Task 10: Full manual end-to-end verification

**Files:** none (verification only).

- [ ] **Step 1: Run the whole test suite**

Run (from `frontend/`): `npm run test:run`
Expected: all unit + component tests pass.
Run: `npm run build`
Expected: clean production build.

- [ ] **Step 2: End-to-end demo walkthrough**

Start the app per project workflow (`make start` from repo root). With the demo profile:
1. Trigger a **failing** run (point at a non-existent profile, or temporarily break a `DEMO_DB_*` so the engine crashes). Confirm: toast fires; footer expands; `/dashboard` shows the banner; `/dashboard/history` lists the failed run, shows the banner, and the "failed before producing any results" message if empty.
2. Trigger a **passing/mixed** run. Confirm: no banner; History rows expand to show metrics; ERROR rows show the "could not run" note; FAILED rows show metrics with the message highlighted.
3. Toggle dark/light — confirm colors read correctly in both.

- [ ] **Step 3: Final commit (if any verification fixes were made)**

```bash
git add -A
git commit -m "test: manual E2E verification fixes for error visualization"
```

---

## Self-review notes (author)

- **Spec coverage:** shared `<ErrorDetail>` (Task 4) ✓; History parity (Task 6) ✓; `<RunFailureBanner>` on both pages (Tasks 5/6/7) ✓; client-side runs×results merge (Task 3, used in Task 6) ✓; live toast + expandable footer (Tasks 8/9) ✓; FAILED/ERROR/SKIPPED color + copy distinction (Tasks 2/4) ✓; no backend changes ✓; test runner introduced (Task 1) ✓.
- **Deferred (per spec non-goals):** no traceback persistence, no offending-row capture, no backend/API change, no live per-test expansion (footer links to History).
- **Type consistency:** `failureKind`/`metricEntriesOf`/`NON_METRIC_KEYS` (Task 2), `buildRunViews`/`RunView` (Task 3), `<ErrorDetail result sqlQuery?>` (Task 4), `<RunFailureBanner run>` (Task 5), `useToast().showToast({message, href?})` (Task 8), `StatusFooter` new props `runError`/`runErrorAtTest` (Task 9) are referenced consistently across tasks.
