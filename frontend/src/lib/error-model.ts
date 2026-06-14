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
