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
