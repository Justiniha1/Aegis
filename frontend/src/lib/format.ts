import type { TestResult } from "./types";

/** Per-status tallies for a set of results. Shared by the dashboard summary,
 *  the history run list, and the TopBar badge counts so the counting logic
 *  lives in one place. */
export interface StatusCounts {
  total: number;
  passed: number;
  failed: number;
  errors: number;
  skipped: number;
}

export function countByStatus(results: TestResult[]): StatusCounts {
  const counts: StatusCounts = { total: results.length, passed: 0, failed: 0, errors: 0, skipped: 0 };
  for (const r of results) {
    if (r.status === "PASSED") counts.passed++;
    else if (r.status === "FAILED") counts.failed++;
    else if (r.status === "ERROR") counts.errors++;
    else if (r.status === "SKIPPED") counts.skipped++;
  }
  return counts;
}

/** The results belonging to the most recent run in a flat result list.
 *  Prefers grouping by run_id (the first row is newest); falls back to
 *  run_at when run_id is absent. Returns [] for empty input. */
export function latestRunResults(results: TestResult[]): TestResult[] {
  if (results.length === 0) return [];
  const latestRunId = results[0].run_id;
  return latestRunId != null
    ? results.filter((r) => r.run_id === latestRunId)
    : results.filter((r) => r.run_at === results[0].run_at);
}

/** Format a numeric metric value for display: fractions in (0,1) render as a
 *  percentage, everything else uses locale grouping. Non-numbers pass through
 *  as their string form. */
export function formatMetricValue(val: unknown): string {
  if (typeof val === "number") {
    return val < 1 && val > 0 ? `${(val * 100).toFixed(1)}%` : val.toLocaleString();
  }
  return String(val);
}
