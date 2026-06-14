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
