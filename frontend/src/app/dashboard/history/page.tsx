"use client";

import { Fragment, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useTheme } from "@/lib/theme";
import { useRunContext } from "@/lib/run-context";
import { apiGet, listRuns } from "@/lib/api";
import { buildRunViews, type RunView } from "@/lib/run-views";
import { RunFailureBanner } from "@/components/RunFailureBanner";
import { ErrorDetail } from "@/components/ErrorDetail";
import {
  StatusBadge,
  SeverityBadge,
  TypePill,
  StatusDot,
} from "@/components/StatusBadge";
import {
  NEUTRAL_SCALE,
  STATUS_PALETTE,
  BRAND_TEAL,
} from "@/lib/constants";
import type { Run, TestResult } from "@/lib/types";

// Run-history list shows this many runs before the "Show more" control.
const RUNS_PAGE_SIZE = 8;

export default function HistoryPage() {
  const { token, isLoading: authLoading } = useAuth();
  const { theme } = useTheme();
  const { lastCompleted } = useRunContext();
  const dark = theme === "dark";
  const palette = dark ? NEUTRAL_SCALE.dark : NEUTRAL_SCALE.light;
  const router = useRouter();
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
      // The runs list endpoint caps limit at 200 (ge=1, le=200); 1000 would 422 and
      // trip the catch below into a spurious logout redirect.
      listRuns(200, token),
      apiGet("/api/v1/results?limit=1000", token),
    ])
      .then(([rs, res]) => { setRuns(rs); setResults(res as TestResult[]); })
      .catch(() => router.push("/login"))
      .finally(() => setLoading(false));
  }, [token, authLoading, router, lastCompleted]);

  const views: RunView[] = useMemo(() => buildRunViews(runs, results), [runs, results]);
  const selectedView = selectedRun != null ? views.find((v) => v.run.id === selectedRun) ?? null : null;

  if (loading || authLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-body" style={{ color: palette.textSecondary }}>Loading…</p>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <div>
        <h1
          className="text-heading"
          style={{ color: palette.textPrimary }}
        >
          Run History
        </h1>
        <p
          className="text-body mt-0.5"
          style={{ color: palette.textSecondary }}
        >
          {views.length} run{views.length !== 1 ? "s" : ""}
        </p>
      </div>

      {views.length === 0 ? (
        <div
          className="px-6 py-12 text-center"
          style={{
            backgroundColor: palette.surfaceElevated,
            border: `1px solid ${palette.borderSubtle}`,
            borderRadius: "8px",
          }}
        >
          <p
            className="text-heading"
            style={{ color: palette.textPrimary }}
          >
            No run history yet
          </p>
          <p
            className="text-body mt-2"
            style={{ color: palette.textSecondary }}
          >
            Past runs will appear here once you trigger one.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-4 gap-6">
          {/* Runs list */}
          <div className="col-span-1 space-y-2">
            {views.slice(0, visibleRuns).map((v) => {
              const active = selectedRun === v.run.id;
              return (
                <button
                  key={v.run.id}
                  onClick={() => { setSelectedRun(v.run.id); setExpandedRow(null); }}
                  className="w-full text-left p-4 transition-colors"
                  style={{
                    backgroundColor: palette.surfaceElevated,
                    border: `1px solid ${palette.borderSubtle}`,
                    borderLeft: active ? `3px solid ${BRAND_TEAL}` : `1px solid ${palette.borderSubtle}`,
                    borderRadius: "8px",
                    cursor: "pointer",
                  }}
                >
                  <p
                    className="text-body font-medium"
                    style={{
                      fontFamily: "var(--font-jetbrains-mono)",
                      color: palette.textPrimary,
                    }}
                  >
                    {new Date(v.run.started_at).toLocaleString()}
                  </p>
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
                      <div
                        className="mt-2 w-full h-1.5 rounded-full overflow-hidden flex"
                        style={{ backgroundColor: palette.borderSubtle }}
                      >
                        <div className="h-full" style={{ width: `${v.counts.total ? (v.counts.passed / v.counts.total) * 100 : 0}%`, backgroundColor: STATUS_PALETTE.PASSED }} />
                        <div className="h-full" style={{ width: `${v.counts.total ? (v.counts.failed / v.counts.total) * 100 : 0}%`, backgroundColor: STATUS_PALETTE.FAILED }} />
                        <div className="h-full" style={{ width: `${v.counts.total ? (v.counts.errors / v.counts.total) * 100 : 0}%`, backgroundColor: STATUS_PALETTE.ERROR }} />
                      </div>
                    </>
                  )}
                </button>
              );
            })}

            {views.length > RUNS_PAGE_SIZE && (
              <div className="space-y-2 pt-1">
                {visibleRuns < views.length && (
                  <button
                    onClick={() => setVisibleRuns((v) => Math.min(v + RUNS_PAGE_SIZE, views.length))}
                    className="w-full text-caption font-medium py-2.5 transition-colors"
                    style={{
                      color: BRAND_TEAL,
                      backgroundColor: "transparent",
                      border: `1px dashed ${palette.borderSubtle}`,
                      borderRadius: "8px",
                      textTransform: "none",
                      letterSpacing: "0",
                      cursor: "pointer",
                    }}
                    onMouseEnter={(e) => ((e.currentTarget as HTMLButtonElement).style.backgroundColor = dark ? "rgba(29,158,117,0.08)" : "rgba(29,158,117,0.06)")}
                    onMouseLeave={(e) => ((e.currentTarget as HTMLButtonElement).style.backgroundColor = "transparent")}
                  >
                    Show {Math.min(RUNS_PAGE_SIZE, views.length - visibleRuns)} more
                  </button>
                )}
                <div className="flex items-center justify-between px-1">
                  <span className="text-caption" style={{ color: palette.textSecondary, textTransform: "none", letterSpacing: "0" }}>
                    Showing {Math.min(visibleRuns, views.length)} of {views.length}
                  </span>
                  {visibleRuns > RUNS_PAGE_SIZE && (
                    <button
                      onClick={() => setVisibleRuns(RUNS_PAGE_SIZE)}
                      className="text-caption font-medium transition-opacity hover:opacity-70"
                      style={{ color: BRAND_TEAL, background: "transparent", border: "none", cursor: "pointer", textTransform: "none", letterSpacing: "0" }}
                    >
                      Show less
                    </button>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Run detail */}
          <div className="col-span-3">
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
                              onMouseEnter={(e) => ((e.currentTarget as HTMLTableRowElement).style.backgroundColor = dark ? "rgba(232,236,243,0.04)" : "rgba(14,22,38,0.04)")}
                              onMouseLeave={(e) => ((e.currentTarget as HTMLTableRowElement).style.backgroundColor = "transparent")}
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
                                  {/* sqlQuery not passed: TestResult does not carry the query; would require joining TestDefinition */}
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
              <div
                className="flex items-center justify-center h-64 text-body"
                style={{
                  border: `1px dashed ${palette.borderSubtle}`,
                  borderRadius: "8px",
                  color: palette.textSecondary,
                }}
              >
                Select a run to see details
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
