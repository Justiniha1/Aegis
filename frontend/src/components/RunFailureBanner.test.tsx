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
