"use client";

import Link from "next/link";
import {
  BRAND_NAVY,
  STATUS_PALETTE,
  NEUTRAL_SCALE,
  RUN_STATUS_LABELS,
  RUN_STATUS_PALETTE,
} from "@/lib/constants";
import type { RunStatus } from "@/lib/types";

export function TopBar({
  breadcrumb,
  passingCount,
  warningCount,
  dark,
  showNewTestButton,
  onRun,
  runStatus,
  runError,
  isRunning = false,
}: {
  breadcrumb: { client: string; environment: string };
  passingCount: number;
  warningCount: number;
  dark: boolean;
  showNewTestButton: boolean;
  onRun?: () => void;
  runStatus?: RunStatus | null;
  runError?: string | null;
  isRunning?: boolean;
}) {
  const palette = dark ? NEUTRAL_SCALE.dark : NEUTRAL_SCALE.light;
  const passColor = STATUS_PALETTE.PASSED;
  const warnColor = STATUS_PALETTE.ERROR;

  const runButtonDisabled = isRunning;
  const statusPill = runStatus && (runStatus === "QUEUED" || runStatus === "RUNNING");

  return (
    <header
      className="flex items-center justify-between px-6"
      style={{
        height: "56px",
        backgroundColor: palette.surfaceElevated,
        borderBottom: `1px solid ${palette.borderSubtle}`,
      }}
    >
      {/* ── Left: breadcrumb + status badges (or run-status pill) ── */}
      <div className="flex items-center gap-4">
        <nav className="text-sm" style={{ color: palette.textSecondary }} aria-label="Breadcrumb">
          <span style={{ color: palette.textPrimary, fontWeight: 500 }}>{breadcrumb.client}</span>
          <span className="mx-2" style={{ color: palette.textSecondary }}>/</span>
          <span style={{ color: palette.textSecondary }}>{breadcrumb.environment}</span>
        </nav>

        <div className="flex items-center gap-2">
          {statusPill && runStatus ? (
            /* In-progress run pill replaces the passing/warning badges */
            <span
              className="inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider px-2 py-0.5"
              style={{
                backgroundColor: `${RUN_STATUS_PALETTE[runStatus]}1A`,
                color: RUN_STATUS_PALETTE[runStatus],
                borderRadius: "4px",
              }}
            >
              <span
                style={{
                  display: "inline-block",
                  width: "6px",
                  height: "6px",
                  borderRadius: "9999px",
                  backgroundColor: RUN_STATUS_PALETTE[runStatus],
                  animation: runStatus === "RUNNING" ? "pulse 1.5s ease-in-out infinite" : "none",
                }}
              />
              {RUN_STATUS_LABELS[runStatus]}
            </span>
          ) : runError ? (
            /* Error pill after a failed run */
            <span
              className="inline-flex items-center gap-1.5 text-[11px] font-semibold px-2 py-0.5 max-w-xs truncate"
              style={{
                backgroundColor: `${STATUS_PALETTE.FAILED}1A`,
                color: STATUS_PALETTE.FAILED,
                borderRadius: "4px",
              }}
              title={runError}
            >
              Run failed — {runError}
            </span>
          ) : (
            /* Normal passing / warning counts */
            <>
              <span
                className="inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider px-2 py-0.5"
                style={{
                  backgroundColor: `${passColor}1A`,
                  color: passColor,
                  borderRadius: "4px",
                }}
              >
                <span style={{ display: "inline-block", width: "6px", height: "6px", borderRadius: "9999px", backgroundColor: passColor }} />
                {passingCount} passing
              </span>
              <span
                className="inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider px-2 py-0.5"
                style={{
                  backgroundColor: `${warnColor}1A`,
                  color: warnColor,
                  borderRadius: "4px",
                }}
              >
                <span style={{ display: "inline-block", width: "6px", height: "6px", borderRadius: "9999px", backgroundColor: warnColor }} />
                {warningCount} warnings
              </span>
            </>
          )}
        </div>
      </div>

      {/* ── Right: "Run all" trigger + optional "New test" ── */}
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => !runButtonDisabled && onRun?.()}
          disabled={runButtonDisabled}
          aria-disabled={runButtonDisabled}
          className="text-sm font-medium px-3 py-1.5"
          style={{
            height: "36px",
            border: `1px solid ${runButtonDisabled ? palette.borderSubtle : BRAND_NAVY}`,
            color: runButtonDisabled ? palette.textSecondary : BRAND_NAVY,
            backgroundColor: "transparent",
            borderRadius: "8px",
            opacity: runButtonDisabled ? 0.5 : 1,
            cursor: runButtonDisabled ? "not-allowed" : "pointer",
            transition: "opacity 150ms",
          }}
        >
          {isRunning ? RUN_STATUS_LABELS[runStatus ?? "QUEUED"] ?? "Running…" : "Run all"}
        </button>

        {showNewTestButton && (
          <Link
            href="/dashboard/tests"
            className="inline-flex items-center text-sm font-medium px-3"
            style={{
              height: "36px",
              backgroundColor: BRAND_NAVY,
              color: "#FFFFFF",
              border: "none",
              borderRadius: "8px",
              cursor: "pointer",
              textDecoration: "none",
            }}
          >
            New test
          </Link>
        )}
      </div>
    </header>
  );
}
