"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useTheme } from "@/lib/theme";
import { apiGet } from "@/lib/api";
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
import { countByStatus } from "@/lib/format";
import type { TestResult, RunSummary } from "@/lib/types";

// Run-history list shows this many runs before the "Show more" control.
const RUNS_PAGE_SIZE = 8;

export default function HistoryPage() {
  const { token, isLoading: authLoading } = useAuth();
  const { theme } = useTheme();
  const dark = theme === "dark";
  const palette = dark ? NEUTRAL_SCALE.dark : NEUTRAL_SCALE.light;
  const router = useRouter();
  const [results, setResults] = useState<TestResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedRun, setSelectedRun] = useState<number | null>(null);
  const [visibleRuns, setVisibleRuns] = useState(RUNS_PAGE_SIZE);

  useEffect(() => {
    if (authLoading) return;
    if (!token) { router.push("/login"); return; }
    apiGet("/api/v1/results?limit=1000", token)
      .then(setResults)
      .catch(() => router.push("/login"))
      .finally(() => setLoading(false));
  }, [token, authLoading, router]);

  const { runMap, runs } = useMemo(() => {
    const map = new Map<number, TestResult[]>();
    for (const r of results) {
      if (r.run_id == null) continue;
      const existing = map.get(r.run_id) || [];
      existing.push(r);
      map.set(r.run_id, existing);
    }
    const summaries: RunSummary[] = Array.from(map.entries())
      .map(([run_id, items]) => {
        const c = countByStatus(items);
        return { run_id, run_at: items[0].run_at, total: c.total, passed: c.passed, failed: c.failed, errors: c.errors };
      })
      .sort((a, b) => b.run_id - a.run_id);
    return { runMap: map, runs: summaries };
  }, [results]);

  const selectedResults = selectedRun != null ? runMap.get(selectedRun) || [] : [];
  const selectedRunSummary = runs.find((r) => r.run_id === selectedRun);

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
          {runs.length} run{runs.length !== 1 ? "s" : ""}
        </p>
      </div>

      {runs.length === 0 ? (
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
            {runs.slice(0, visibleRuns).map((run) => {
              const active = selectedRun === run.run_id;
              return (
                <button
                  key={run.run_id}
                  onClick={() => setSelectedRun(run.run_id)}
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
                    {new Date(run.run_at).toLocaleString()}
                  </p>
                  <div className="flex gap-3 mt-2 text-caption" style={{ textTransform: "none", letterSpacing: "0" }}>
                    <span style={{ color: STATUS_PALETTE.PASSED }}>{run.passed} passed</span>
                    {run.failed > 0 && <span style={{ color: STATUS_PALETTE.FAILED }}>{run.failed} failed</span>}
                    {run.errors > 0 && <span style={{ color: STATUS_PALETTE.ERROR }}>{run.errors} errors</span>}
                  </div>
                  <div
                    className="mt-2 w-full h-1.5 rounded-full overflow-hidden flex"
                    style={{ backgroundColor: palette.borderSubtle }}
                  >
                    <div className="h-full" style={{ width: `${(run.passed / run.total) * 100}%`, backgroundColor: STATUS_PALETTE.PASSED }} />
                    <div className="h-full" style={{ width: `${(run.failed / run.total) * 100}%`, backgroundColor: STATUS_PALETTE.FAILED }} />
                    <div className="h-full" style={{ width: `${(run.errors / run.total) * 100}%`, backgroundColor: STATUS_PALETTE.ERROR }} />
                  </div>
                </button>
              );
            })}

            {runs.length > RUNS_PAGE_SIZE && (
              <div className="space-y-2 pt-1">
                {visibleRuns < runs.length && (
                  <button
                    onClick={() => setVisibleRuns((v) => Math.min(v + RUNS_PAGE_SIZE, runs.length))}
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
                    Show {Math.min(RUNS_PAGE_SIZE, runs.length - visibleRuns)} more
                  </button>
                )}
                <div className="flex items-center justify-between px-1">
                  <span className="text-caption" style={{ color: palette.textSecondary, textTransform: "none", letterSpacing: "0" }}>
                    Showing {Math.min(visibleRuns, runs.length)} of {runs.length}
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
            {selectedRun ? (
              <div
                className="overflow-hidden"
                style={{
                  backgroundColor: palette.surfaceElevated,
                  border: `1px solid ${palette.borderSubtle}`,
                  borderRadius: "8px",
                }}
              >
                <div
                  className="px-6 py-4"
                  style={{ borderBottom: `1px solid ${palette.borderSubtle}` }}
                >
                  <h2
                    className="text-heading"
                    style={{ color: palette.textPrimary }}
                  >
                    Run at <span style={{ fontFamily: "var(--font-jetbrains-mono)" }}>{selectedRunSummary ? new Date(selectedRunSummary.run_at).toLocaleString() : ""}</span>
                  </h2>
                  <div className="flex gap-4 mt-1 text-caption" style={{ textTransform: "none", letterSpacing: "0" }}>
                    {(() => {
                      const run = selectedRunSummary;
                      if (!run) return null;
                      return (
                        <>
                          <span style={{ color: palette.textSecondary }}>{run.total} total</span>
                          <span style={{ color: STATUS_PALETTE.PASSED }}>{run.passed} passed</span>
                          {run.failed > 0 && <span style={{ color: STATUS_PALETTE.FAILED }}>{run.failed} failed</span>}
                          {run.errors > 0 && <span style={{ color: STATUS_PALETTE.ERROR }}>{run.errors} errors</span>}
                        </>
                      );
                    })()}
                  </div>
                </div>
                <table className="w-full text-sm">
                  <thead style={{ backgroundColor: palette.surfaceBg }}>
                    <tr style={{ color: palette.textSecondary }}>
                      <th className="pl-6 py-3" style={{ width: "24px" }}></th>
                      <th className="px-4 py-3 text-left text-caption">Test</th>
                      <th className="px-4 py-3 text-left text-caption">Type</th>
                      <th className="px-4 py-3 text-left text-caption">Status</th>
                      <th className="px-4 py-3 text-left text-caption">Severity</th>
                      <th className="px-4 py-3 text-left text-caption">Message</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedResults.map((r) => (
                      <tr
                        key={r.id}
                        className="transition-colors"
                        style={{
                          height: "40px",
                          borderTop: `1px solid ${palette.borderSubtle}`,
                        }}
                        onMouseEnter={(e) => ((e.currentTarget as HTMLTableRowElement).style.backgroundColor = dark ? "rgba(232,236,243,0.04)" : "rgba(14,22,38,0.04)")}
                        onMouseLeave={(e) => ((e.currentTarget as HTMLTableRowElement).style.backgroundColor = "transparent")}
                      >
                        <td className="pl-6 py-3"><StatusDot status={r.status} /></td>
                        <td
                          className="px-4 py-3 max-w-xs truncate text-body"
                          style={{
                            fontFamily: "var(--font-jetbrains-mono)",
                            color: palette.textPrimary,
                          }}
                          title={r.test_name}
                        >
                          {r.test_name}
                        </td>
                        <td className="px-4 py-3"><TypePill type={r.test_type} /></td>
                        <td className="px-4 py-3"><StatusBadge status={r.status} /></td>
                        <td className="px-4 py-3"><SeverityBadge severity={r.severity} /></td>
                        <td
                          className="px-4 py-3 text-body"
                          style={{ color: palette.textSecondary, whiteSpace: "normal", wordBreak: "break-word" }}
                        >
                          {r.message}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
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
