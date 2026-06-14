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
