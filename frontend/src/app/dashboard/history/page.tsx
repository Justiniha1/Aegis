"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useTheme } from "@/lib/theme";
import { useRunContext } from "@/lib/run-context";
import { apiGet, listRuns } from "@/lib/api";
import { buildRunViews, type RunView } from "@/lib/run-views";
import { RunFailureBanner } from "@/components/RunFailureBanner";
import { ResultRow } from "@/components/ResultRow";
import { NEUTRAL_SCALE, STATUS_PALETTE, BRAND_TEAL } from "@/lib/constants";
import { type StatusCounts } from "@/lib/format";
import { formatRunTimeShort, formatRunTimeFull } from "@/lib/time";
import type { Run, TestResult } from "@/lib/types";

type Palette = {
  surfaceBg: string; surfaceElevated: string; borderSubtle: string;
  textSecondary: string; textPrimary: string;
};
type ResultFilter = "all" | "issues" | "passing";

// Run-history list shows this many runs before the "Show more" control.
const RUNS_PAGE_SIZE = 10;

/* A run's headline outcome: the run breaking outranks test failures, which
   outrank test errors. Drives the leading dot color + accessible label. */
function runOutcome(v: RunView): { color: string; label: string } {
  if (v.run.status === "FAILED") return { color: STATUS_PALETTE.FAILED, label: "Run failed" };
  if (v.counts.total === 0) return { color: STATUS_PALETTE.SKIPPED, label: "No results" };
  if (v.counts.failed > 0) return { color: STATUS_PALETTE.FAILED, label: "Has failures" };
  if (v.counts.errors > 0) return { color: STATUS_PALETTE.ERROR, label: "Has errors" };
  return { color: STATUS_PALETTE.PASSED, label: "All passed" };
}

/* Proportional pass/fail/error/skip bar. Returns null for empty runs. */
function HealthBar({ counts, height, palette }: { counts: StatusCounts; height: number; palette: Palette }) {
  if (!counts.total) return null;
  const seg = (n: number, color: string) =>
    n > 0 ? <div className="h-full" style={{ width: `${(n / counts.total) * 100}%`, backgroundColor: color }} /> : null;
  return (
    <div className="flex overflow-hidden rounded-full" style={{ height, backgroundColor: palette.borderSubtle }}>
      {seg(counts.passed, STATUS_PALETTE.PASSED)}
      {seg(counts.failed, STATUS_PALETTE.FAILED)}
      {seg(counts.errors, STATUS_PALETTE.ERROR)}
      {seg(counts.skipped, STATUS_PALETTE.SKIPPED)}
    </div>
  );
}

/* Status-colored count summary, issues first so the eye lands on them. */
function CountSummary({ counts, palette }: { counts: StatusCounts; palette: Palette }) {
  const parts: { t: string; c: string }[] = [];
  if (counts.failed) parts.push({ t: `${counts.failed} failed`, c: STATUS_PALETTE.FAILED });
  if (counts.errors) parts.push({ t: `${counts.errors} errors`, c: STATUS_PALETTE.ERROR });
  if (counts.skipped) parts.push({ t: `${counts.skipped} skipped`, c: STATUS_PALETTE.SKIPPED });
  parts.push({ t: `${counts.passed} passed`, c: palette.textSecondary });
  return (
    <span className="flex items-center gap-1.5" style={{ fontSize: "12px" }}>
      {parts.map((p, i) => (
        <span key={p.t} style={{ color: p.c, whiteSpace: "nowrap" }}>
          {p.t}{i < parts.length - 1 && <span style={{ color: palette.borderSubtle }}> · </span>}
        </span>
      ))}
    </span>
  );
}

export default function HistoryPage() {
  const { token, isLoading: authLoading } = useAuth();
  const { theme } = useTheme();
  const { lastCompleted } = useRunContext();
  const dark = theme === "dark";
  const palette = dark ? NEUTRAL_SCALE.dark : NEUTRAL_SCALE.light;
  const hoverBg = dark ? "rgba(232,236,243,0.04)" : "rgba(14,22,38,0.035)";
  const selectedBg = dark ? "rgba(29,158,117,0.12)" : "rgba(29,158,117,0.08)";
  const router = useRouter();

  const [runs, setRuns] = useState<Run[]>([]);
  const [results, setResults] = useState<TestResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedRun, setSelectedRun] = useState<number | null>(null);
  const [visibleRuns, setVisibleRuns] = useState(RUNS_PAGE_SIZE);
  const [expandedRow, setExpandedRow] = useState<number | null>(null);
  const [filter, setFilter] = useState<ResultFilter>("all");

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

  // Default to the most recent run by derivation (no effect): use the chosen run
  // when it still exists, otherwise fall back to the newest.
  const effectiveSelected =
    selectedRun != null && views.some((v) => v.run.id === selectedRun)
      ? selectedRun
      : views[0]?.run.id ?? null;
  const selectedView = views.find((v) => v.run.id === effectiveSelected) ?? null;

  const filteredResults = useMemo(() => {
    if (!selectedView) return [];
    if (filter === "issues") return selectedView.results.filter((r) => r.status !== "PASSED");
    if (filter === "passing") return selectedView.results.filter((r) => r.status === "PASSED");
    return selectedView.results;
  }, [selectedView, filter]);

  const selectRun = (id: number) => { setSelectedRun(id); setExpandedRow(null); setFilter("all"); };

  if (loading || authLoading) return <HistorySkeleton palette={palette} />;

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <header>
        <h1 className="text-heading" style={{ color: palette.textPrimary }}>Run History</h1>
        <p className="text-body mt-0.5" style={{ color: palette.textSecondary }}>
          {views.length === 0 ? "No runs yet" : `${views.length} run${views.length !== 1 ? "s" : ""}`}
        </p>
      </header>

      {views.length === 0 ? (
        <EmptyPanel
          palette={palette}
          title="No run history yet"
          body="Trigger a run from the dashboard and its results will appear here."
        />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-6 items-start">
          {/* ── Run list ─────────────────────────────────────────────── */}
          <nav
            aria-label="Run history"
            className="overflow-hidden"
            style={{ backgroundColor: palette.surfaceElevated, border: `1px solid ${palette.borderSubtle}`, borderRadius: "10px" }}
          >
            <ul>
              {views.slice(0, visibleRuns).map((v, i) => {
                const active = effectiveSelected === v.run.id;
                const outcome = runOutcome(v);
                const failed = v.run.status === "FAILED";
                return (
                  <li key={v.run.id}>
                    <button
                      onClick={() => selectRun(v.run.id)}
                      aria-current={active ? "true" : undefined}
                      className="w-full text-left px-4 py-3 flex gap-3 transition-colors duration-150 motion-reduce:transition-none focus-visible:outline-2 focus-visible:-outline-offset-2"
                      style={{
                        backgroundColor: active ? selectedBg : "transparent",
                        borderTop: i === 0 ? "none" : `1px solid ${palette.borderSubtle}`,
                        outlineColor: BRAND_TEAL,
                        cursor: "pointer",
                      }}
                      onMouseEnter={(e) => { if (!active) (e.currentTarget as HTMLButtonElement).style.backgroundColor = hoverBg; }}
                      onMouseLeave={(e) => { if (!active) (e.currentTarget as HTMLButtonElement).style.backgroundColor = "transparent"; }}
                    >
                      <span
                        aria-hidden="true"
                        className="shrink-0 mt-1.5"
                        style={{ width: "9px", height: "9px", borderRadius: "9999px", backgroundColor: outcome.color, boxShadow: active ? `0 0 0 3px ${selectedBg}` : "none" }}
                      />
                      <span className="min-w-0 flex-1">
                        <span className="flex items-baseline justify-between gap-2">
                          <span
                            className="truncate"
                            style={{ fontFamily: "var(--font-jetbrains-mono)", fontSize: "13px", fontWeight: active ? 600 : 500, color: active ? palette.textPrimary : palette.textPrimary }}
                            title={formatRunTimeFull(v.run.started_at)}
                          >
                            {formatRunTimeShort(v.run.started_at)}
                          </span>
                          <span className="shrink-0" style={{ fontSize: "11px", color: palette.textSecondary, fontFamily: "var(--font-jetbrains-mono)" }}>
                            #{v.run.id}
                          </span>
                        </span>
                        <span className="block mt-1.5">
                          {failed ? (
                            <span style={{ fontSize: "12px", color: STATUS_PALETTE.FAILED, fontWeight: 500 }}>{outcome.label}</span>
                          ) : v.counts.total === 0 ? (
                            <span style={{ fontSize: "12px", color: palette.textSecondary }}>No tests</span>
                          ) : (
                            <CountSummary counts={v.counts} palette={palette} />
                          )}
                        </span>
                        {!failed && v.counts.total > 0 && (
                          <span className="block mt-2"><HealthBar counts={v.counts} height={3} palette={palette} /></span>
                        )}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>

            {views.length > RUNS_PAGE_SIZE && (
              <div
                className="flex items-center justify-between px-4 py-2.5"
                style={{ borderTop: `1px solid ${palette.borderSubtle}`, backgroundColor: palette.surfaceBg }}
              >
                <span style={{ fontSize: "11px", color: palette.textSecondary }}>
                  {Math.min(visibleRuns, views.length)} of {views.length}
                </span>
                {visibleRuns < views.length ? (
                  <button
                    onClick={() => setVisibleRuns((n) => Math.min(n + RUNS_PAGE_SIZE, views.length))}
                    className="font-medium transition-opacity hover:opacity-70"
                    style={{ fontSize: "12px", color: BRAND_TEAL, background: "transparent", border: "none", cursor: "pointer" }}
                  >
                    Show more
                  </button>
                ) : (
                  <button
                    onClick={() => setVisibleRuns(RUNS_PAGE_SIZE)}
                    className="font-medium transition-opacity hover:opacity-70"
                    style={{ fontSize: "12px", color: BRAND_TEAL, background: "transparent", border: "none", cursor: "pointer" }}
                  >
                    Show less
                  </button>
                )}
              </div>
            )}
          </nav>

          {/* ── Run detail ───────────────────────────────────────────── */}
          <section className="min-w-0">
            {selectedView ? (
              <div
                className="overflow-hidden"
                style={{ backgroundColor: palette.surfaceElevated, border: `1px solid ${palette.borderSubtle}`, borderRadius: "10px" }}
              >
                <RunFailureBanner run={selectedView.run} />

                {/* Detail header */}
                <div className="px-6 pt-5 pb-4" style={{ borderBottom: `1px solid ${palette.borderSubtle}` }}>
                  <div className="flex items-baseline justify-between gap-3 flex-wrap">
                    <h2 className="text-heading" style={{ color: palette.textPrimary }}>
                      Run{" "}
                      <span style={{ fontFamily: "var(--font-jetbrains-mono)", color: palette.textSecondary, fontWeight: 500 }}>
                        #{selectedView.run.id}
                      </span>
                    </h2>
                    <span
                      style={{ fontSize: "12px", color: palette.textSecondary, fontFamily: "var(--font-jetbrains-mono)" }}
                      title={formatRunTimeFull(selectedView.run.started_at)}
                    >
                      {formatRunTimeFull(selectedView.run.started_at)} · {selectedView.run.profile}
                    </span>
                  </div>
                  {selectedView.counts.total > 0 && (
                    <div className="mt-3 flex items-center gap-3">
                      <div className="flex-1 max-w-xs"><HealthBar counts={selectedView.counts} height={6} palette={palette} /></div>
                      <CountSummary counts={selectedView.counts} palette={palette} />
                    </div>
                  )}
                </div>

                {selectedView.results.length === 0 ? (
                  <EmptyState
                    palette={palette}
                    color={selectedView.run.status === "FAILED" ? STATUS_PALETTE.FAILED : palette.textSecondary}
                    title={selectedView.run.status === "FAILED" ? "Failed before any tests ran" : "No results for this run"}
                    body={
                      selectedView.run.status === "FAILED"
                        ? "The run stopped before producing test results. The reason is shown above."
                        : "This run did not record any test results."
                    }
                  />
                ) : (
                  <>
                    {/* Filter */}
                    <div className="px-6 py-3 flex items-center gap-1" style={{ borderBottom: `1px solid ${palette.borderSubtle}` }}>
                      <FilterTabs
                        filter={filter}
                        setFilter={setFilter}
                        palette={palette}
                        counts={{
                          all: selectedView.counts.total,
                          issues: selectedView.counts.total - selectedView.counts.passed,
                          passing: selectedView.counts.passed,
                        }}
                      />
                    </div>

                    {/* Results list */}
                    {filteredResults.length === 0 ? (
                      <div className="px-6 py-10 text-center" style={{ fontSize: "13px", color: palette.textSecondary }}>
                        {filter === "issues" ? "No issues in this run." : "Nothing to show for this filter."}
                      </div>
                    ) : (
                      <ul>
                        {filteredResults.map((r) => (
                          <ResultRow
                            key={r.id}
                            result={r}
                            expanded={expandedRow === r.id}
                            onToggle={() => setExpandedRow(expandedRow === r.id ? null : r.id)}
                          />
                        ))}
                      </ul>
                    )}
                  </>
                )}
              </div>
            ) : (
              <EmptyPanel palette={palette} title="Select a run" body="Choose a run from the list to see its results and any failures." />
            )}
          </section>
        </div>
      )}
    </div>
  );
}

/* ── All / Issues / Passing segmented control (mirrors the dashboard) ──────── */
function FilterTabs({
  filter, setFilter, counts, palette,
}: {
  filter: ResultFilter; setFilter: (f: ResultFilter) => void; counts: Record<ResultFilter, number>; palette: Palette;
}) {
  const tabs: [ResultFilter, string][] = [["all", "All"], ["issues", "Issues"], ["passing", "Passing"]];
  return (
    <div className="inline-flex rounded-lg p-0.5 gap-0.5" style={{ backgroundColor: palette.surfaceBg, border: `1px solid ${palette.borderSubtle}` }}>
      {tabs.map(([key, label]) => {
        const active = filter === key;
        return (
          <button
            key={key}
            onClick={() => setFilter(key)}
            className="rounded-md transition-colors duration-150 motion-reduce:transition-none"
            style={{
              fontSize: "12px",
              padding: "4px 12px",
              fontWeight: active ? 600 : 400,
              backgroundColor: active ? palette.surfaceElevated : "transparent",
              color: active ? palette.textPrimary : palette.textSecondary,
              boxShadow: active ? "0 1px 2px rgb(0 0 0 / 0.06)" : "none",
              cursor: "pointer",
            }}
          >
            {label} <span style={{ color: active ? palette.textSecondary : palette.textSecondary, opacity: 0.8 }}>{counts[key]}</span>
          </button>
        );
      })}
    </div>
  );
}

/* ── Empty / placeholder panels ────────────────────────────────────────────── */
function EmptyPanel({ palette, title, body }: { palette: Palette; title: string; body: string }) {
  return (
    <div
      className="flex flex-col items-center justify-center text-center px-6 py-16"
      style={{ border: `1px dashed ${palette.borderSubtle}`, borderRadius: "10px", minHeight: "16rem" }}
    >
      <p className="text-heading" style={{ color: palette.textPrimary }}>{title}</p>
      <p className="text-body mt-2" style={{ color: palette.textSecondary, maxWidth: "36ch" }}>{body}</p>
    </div>
  );
}

function EmptyState({ palette, color, title, body }: { palette: Palette; color: string; title: string; body: string }) {
  return (
    <div className="flex flex-col items-center justify-center text-center px-6 py-12">
      <span aria-hidden="true" style={{ width: "10px", height: "10px", borderRadius: "9999px", backgroundColor: color, marginBottom: "12px" }} />
      <p className="text-body font-medium" style={{ color: palette.textPrimary }}>{title}</p>
      <p className="mt-1.5" style={{ fontSize: "13px", color: palette.textSecondary, maxWidth: "42ch" }}>{body}</p>
    </div>
  );
}

/* ── Loading skeleton (no spinner; mirrors the two-pane shape) ──────────────── */
function HistorySkeleton({ palette }: { palette: Palette }) {
  const bar = (w: string, h = 12) => (
    <div className="rounded animate-pulse motion-reduce:animate-none" style={{ width: w, height: h, backgroundColor: palette.borderSubtle }} />
  );
  return (
    <div className="max-w-7xl mx-auto space-y-6" aria-busy="true" aria-label="Loading run history">
      <div className="space-y-2">{bar("160px", 22)}{bar("80px")}</div>
      <div className="grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-6 items-start">
        <div className="overflow-hidden" style={{ backgroundColor: palette.surfaceElevated, border: `1px solid ${palette.borderSubtle}`, borderRadius: "10px" }}>
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="px-4 py-3 space-y-2" style={{ borderTop: i === 0 ? "none" : `1px solid ${palette.borderSubtle}` }}>
              {bar("60%")}{bar("40%", 10)}
            </div>
          ))}
        </div>
        <div className="overflow-hidden" style={{ backgroundColor: palette.surfaceElevated, border: `1px solid ${palette.borderSubtle}`, borderRadius: "10px" }}>
          <div className="px-6 pt-5 pb-4 space-y-3" style={{ borderBottom: `1px solid ${palette.borderSubtle}` }}>{bar("120px", 18)}{bar("220px", 6)}</div>
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="px-6 py-3.5 flex items-center gap-3" style={{ borderTop: i === 0 ? "none" : `1px solid ${palette.borderSubtle}` }}>
              <div className="rounded-full animate-pulse motion-reduce:animate-none" style={{ width: 9, height: 9, backgroundColor: palette.borderSubtle }} />
              <div className="flex-1 space-y-1.5">{bar("45%")}{bar("70%", 10)}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
