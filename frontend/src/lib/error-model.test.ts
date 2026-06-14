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
