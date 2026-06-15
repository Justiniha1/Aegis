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
