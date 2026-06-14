"use client";

import { Fragment, useEffect, useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import { useAuth } from "@/lib/auth";
import { useTheme } from "@/lib/theme";
import { apiGet } from "@/lib/api";
import { useRunContext } from "@/lib/run-context";
import {
  SEVERITY_COLORS,
  TYPE_LABELS,
  SEVERITY_LABELS,
  BRAND_TEAL,
  STATUS_PALETTE,
  NEUTRAL_SCALE,
} from "@/lib/constants";
import {
  StatusBadge,
  SeverityBadge,
  TypePill,
  StatusDot,
} from "@/components/StatusBadge";
import { countByStatus, latestRunResults } from "@/lib/format";
import { metricEntriesOf } from "@/lib/error-model";
import { ErrorDetail } from "@/components/ErrorDetail";
import type { TestResult, TestDefinition } from "@/lib/types";

/* ── colour helpers ───────────────────────────────────────────────────────── */
const SEV_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW"] as const;
/* Bar fills encode the outcome mix of items in the bucket:
   - all passing → green
   - all failing → red
   - mixed (some passing, some failing) → amber
   The x-axis label already communicates which type/table the bar represents,
   so the bar's colour is reserved for "is this group healthy?". */
const BAR_COLORS: Record<string, string> = {
  PASSED: STATUS_PALETTE.PASSED,  // #22C55E
  FAILED: STATUS_PALETTE.FAILED,  // #EF4444
  MIXED:  STATUS_PALETTE.ERROR,   // #F59E0B
};

/* ── tiny animated number ─────────────────────────────────────────────────── */
function AnimatedNumber({ value }: { value: number }) {
  const [display, setDisplay] = useState(0);
  useEffect(() => {
    if (value === 0) { setDisplay(0); return; }
    const step = Math.max(1, Math.ceil(value / 20));
    const id = setInterval(() => {
      setDisplay((d) => {
        const next = d + step;
        if (next >= value) { clearInterval(id); return value; }
        return next;
      });
    }, 30);
    return () => clearInterval(id);
  }, [value]);
  return <>{display}</>;
}

/* ── custom tooltip ───────────────────────────────────────────────────────── */
function ChartTooltip({ active, payload, label, level, dark }: any) {
  if (!active || !payload?.length) return null;
  const palette = dark ? NEUTRAL_SCALE.dark : NEUTRAL_SCALE.light;
  const count = payload[0].value;
  return (
    <div
      className="px-3 py-2"
      style={{
        backgroundColor: palette.surfaceElevated,
        border: `1px solid ${palette.borderSubtle}`,
        borderRadius: "8px",
        boxShadow: "0 4px 12px rgb(0 0 0 / 0.08)",
        color: palette.textPrimary,
      }}
    >
      <p className="text-body font-medium">{label}</p>
      <p className="text-caption mt-0.5" style={{ color: palette.textSecondary, textTransform: "none", letterSpacing: "0" }}>
        {count} test{count !== 1 ? "s" : ""}
      </p>
      {level !== "detail" && (
        <p className="text-caption mt-1" style={{ color: BRAND_TEAL, textTransform: "none", letterSpacing: "0" }}>
          Click to drill down →
        </p>
      )}
    </div>
  );
}

/* ── outcome classifier for a bar based on the mix of passing / failing items ── */
function outcomeOf(items: TestResult[]): "PASSED" | "FAILED" | "MIXED" {
  if (items.length === 0) return "PASSED";
  const allPassed = items.every((r) => r.status === "PASSED");
  if (allPassed) return "PASSED";
  const nonePassed = items.every((r) => r.status !== "PASSED");
  if (nonePassed) return "FAILED";
  return "MIXED";
}

/* ══════════════════════════════════════════════════════════════════════════ */
export default function DashboardPage() {
  const { token, isLoading: authLoading } = useAuth();
  const { theme } = useTheme();
  const dark = theme === "dark";
  const palette = dark ? NEUTRAL_SCALE.dark : NEUTRAL_SCALE.light;
  const router = useRouter();
  const { lastCompleted } = useRunContext();
  const [results, setResults] = useState<TestResult[]>([]);
  const [testDefs, setTestDefs] = useState<TestDefinition[]>([]);
  const [loading, setLoading] = useState(true);

  const [drillMode, setDrillMode] = useState<"type" | "table">("type");
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [selectedTable, setSelectedTable] = useState<string | null>(null);
  const [selectedTableFirst, setSelectedTableFirst] = useState<string | null>(null);
  const [selectedTypeSecond, setSelectedTypeSecond] = useState<string | null>(null);
  const [severityFilter, setSeverityFilter] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<"all" | "issues" | "passing">("issues");

  const drillLevel = selectedTable ? "detail" : selectedType ? "table" : "type";
  const tableDrillLevel = selectedTypeSecond ? "detail" : selectedTableFirst ? "typeInTable" : "tableList";

  useEffect(() => {
    if (authLoading) return;
    if (!token) { router.push("/login"); return; }
    Promise.all([
      apiGet("/api/v1/results?limit=500", token),
      apiGet("/api/v1/tests", token),
    ])
      .then(([res, defs]) => { setResults(res); setTestDefs(defs); })
      .catch(() => router.push("/login"))
      .finally(() => setLoading(false));
  }, [token, authLoading, router, lastCompleted]); // lastCompleted triggers re-fetch on run completion

  const derivedTableMap = useMemo(() => {
    const m = new Map<string, string>();
    for (const def of testDefs) {
      const cfg = (def.config || {}) as Record<string, unknown>;
      if (def.type === "custom_sql") {
        const q = (cfg.query as string | undefined) || "";
        const match = q.match(/\bfrom\s+([a-zA-Z_][a-zA-Z0-9_]*)/i);
        if (match) m.set(def.name, match[1]);
      } else if (def.type === "relationship_check") {
        const src = cfg.source_table as string | undefined;
        if (src) m.set(def.name, src);
      }
    }
    return m;
  }, [testDefs]);

  const queryByTestName = useMemo(() => {
    const m = new Map<string, string>();
    for (const def of testDefs) {
      if (def.type !== "custom_sql") continue;
      const q = (def.config?.query as string | undefined);
      if (q) m.set(def.name, q);
    }
    return m;
  }, [testDefs]);

  const tableFor = (r: TestResult): string =>
    r.table || derivedTableMap.get(r.test_name) || r.test_name;

  const latestResults = useMemo(() => latestRunResults(results), [results]);

  const chartResults = useMemo(() => {
    let base = latestResults;
    if (statusFilter === "issues") base = base.filter((r) => r.status !== "PASSED");
    else if (statusFilter === "passing") base = base.filter((r) => r.status === "PASSED");
    if (severityFilter) base = base.filter((r) => r.severity === severityFilter);
    return base;
  }, [latestResults, severityFilter, statusFilter]);

  const summary = useMemo(() => countByStatus(latestResults), [latestResults]);

  const prevSummary = useMemo(() => {
    // Find the second-distinct run_id in the results array (already sorted newest-first).
    const latestId = results[0]?.run_id ?? null;
    const prevId = results.find((r) => r.run_id !== latestId && r.run_id != null)?.run_id ?? null;
    if (prevId == null) return null;
    return countByStatus(results.filter((r) => r.run_id === prevId));
  }, [results]);

  const typeChartData = useMemo(() => {
    const groups: Record<string, TestResult[]> = {};
    for (const r of chartResults) {
      (groups[r.test_type] ??= []).push(r);
    }
    return Object.entries(groups)
      .map(([name, items]) => ({
        name: TYPE_LABELS[name] ?? name,
        rawName: name,
        count: items.length,
        outcome: outcomeOf(items),
      }))
      .sort((a, b) => b.count - a.count);
  }, [chartResults]);

  const tableChartData = useMemo(() => {
    if (!selectedType) return [];
    const groups: Record<string, TestResult[]> = {};
    for (const r of chartResults) {
      if (r.test_type !== selectedType) continue;
      const table = tableFor(r);
      (groups[table] ??= []).push(r);
    }
    return Object.entries(groups)
      .map(([name, items]) => ({ name, count: items.length, outcome: outcomeOf(items) }))
      .sort((a, b) => b.count - a.count);
  }, [chartResults, selectedType, derivedTableMap]);

  const detailResults = useMemo(() => {
    if (!selectedTable || !selectedType) return [];
    return chartResults.filter((r) => {
      const table = tableFor(r);
      return r.test_type === selectedType && table === selectedTable;
    });
  }, [chartResults, selectedType, selectedTable, derivedTableMap]);

  const tableFirstChartData = useMemo(() => {
    const groups: Record<string, TestResult[]> = {};
    for (const r of chartResults) {
      const table = tableFor(r);
      (groups[table] ??= []).push(r);
    }
    return Object.entries(groups)
      .map(([name, items]) => ({ name, count: items.length, outcome: outcomeOf(items) }))
      .sort((a, b) => b.count - a.count);
  }, [chartResults, derivedTableMap]);

  const typeInTableChartData = useMemo(() => {
    if (!selectedTableFirst) return [];
    const groups: Record<string, TestResult[]> = {};
    for (const r of chartResults) {
      const table = tableFor(r);
      if (table !== selectedTableFirst) continue;
      (groups[r.test_type] ??= []).push(r);
    }
    return Object.entries(groups)
      .map(([name, items]) => ({ name: TYPE_LABELS[name] ?? name, rawName: name, count: items.length, outcome: outcomeOf(items) }))
      .sort((a, b) => b.count - a.count);
  }, [chartResults, selectedTableFirst, derivedTableMap]);

  const detailResultsTableFirst = useMemo(() => {
    if (!selectedTableFirst || !selectedTypeSecond) return [];
    return chartResults.filter((r) => {
      const table = tableFor(r);
      return table === selectedTableFirst && r.test_type === selectedTypeSecond;
    });
  }, [chartResults, selectedTableFirst, selectedTypeSecond, derivedTableMap]);

  const severityCounts = useMemo(() => {
    let base = latestResults;
    if (statusFilter === "issues") base = base.filter((r) => r.status !== "PASSED");
    else if (statusFilter === "passing") base = base.filter((r) => r.status === "PASSED");
    const counts: Record<string, number> = {};
    for (const r of base) counts[r.severity] = (counts[r.severity] || 0) + 1;
    return counts;
  }, [latestResults, statusFilter]);

  const handleBack = () => {
    if (drillMode === "type") {
      if (selectedTable) setSelectedTable(null);
      else if (selectedType) setSelectedType(null);
    } else {
      if (selectedTypeSecond) setSelectedTypeSecond(null);
      else if (selectedTableFirst) setSelectedTableFirst(null);
    }
  };

  const resetDrill = () => {
    setSelectedType(null);
    setSelectedTable(null);
    setSelectedTableFirst(null);
    setSelectedTypeSecond(null);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-body animate-pulse" style={{ color: palette.textSecondary }}>Loading results…</div>
      </div>
    );
  }

  /* ══════════════════════════════════════════════════════════════════════ */
  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* ── Metric cards: 4-up grid per UI-SPEC §"Metric cards" (D-05) ── */}
      <div className="grid grid-cols-4 gap-6">
        <SummaryCard label="Total Tests" value={summary.total}  delta={prevSummary != null ? summary.total  - prevSummary.total  : null} dark={dark} />
        <SummaryCard label="Passed"      value={summary.passed} delta={prevSummary != null ? summary.passed - prevSummary.passed : null} dark={dark} />
        <SummaryCard label="Failed"      value={summary.failed} delta={prevSummary != null ? summary.failed - prevSummary.failed : null} deltaPositiveIsBad dark={dark} />
        <SummaryCard label="Errors"      value={summary.errors} delta={prevSummary != null ? summary.errors - prevSummary.errors : null} deltaPositiveIsBad dark={dark} />
      </div>

      {/* ── Drill-down chart ───────────────────────────────────────────── */}
      <div
        className="p-6"
        style={{
          backgroundColor: palette.surfaceElevated,
          border: `1px solid ${palette.borderSubtle}`,
          borderRadius: "8px",
        }}
      >
        {/* Status toggle + View-by toggle */}
        <div className="flex items-center justify-between mb-4">
          <div
            className="flex items-center rounded-lg p-0.5 gap-0.5"
            style={{ backgroundColor: palette.surfaceBg }}
          >
            {([
              ["issues", "Issues Only", latestResults.filter((r) => r.status !== "PASSED").length],
              ["all", "All Tests", latestResults.length],
              ["passing", "Passing", latestResults.filter((r) => r.status === "PASSED").length],
            ] as ["issues" | "all" | "passing", string, number][]).map(([key, label, count]) => {
              const active = statusFilter === key;
              return (
                <button
                  key={key}
                  onClick={() => { setStatusFilter(key); resetDrill(); }}
                  className="text-xs px-3 py-1.5 rounded-md transition-all"
                  style={{
                    backgroundColor: active ? palette.surfaceElevated : "transparent",
                    color: active ? palette.textPrimary : palette.textSecondary,
                    fontWeight: active ? 500 : 400,
                    boxShadow: active ? "0 1px 2px rgb(0 0 0 / 0.06)" : "none",
                  }}
                >
                  {label} ({count})
                </button>
              );
            })}
          </div>
          <div className="flex items-center gap-3">
            <span className="text-caption" style={{ color: palette.textSecondary, textTransform: "none", letterSpacing: "0" }}>View by:</span>
            <div
              className="flex items-center rounded-lg p-0.5 gap-0.5"
              style={{ backgroundColor: palette.surfaceBg }}
            >
              {([["type", "Error Type"], ["table", "Table"]] as ["type" | "table", string][]).map(([key, label]) => {
                const active = drillMode === key;
                return (
                  <button
                    key={key}
                    onClick={() => { setDrillMode(key); resetDrill(); }}
                    className="text-xs px-3 py-1.5 rounded-md transition-all"
                    style={{
                      backgroundColor: active ? palette.surfaceElevated : "transparent",
                      color: active ? palette.textPrimary : palette.textSecondary,
                      fontWeight: active ? 500 : 400,
                      boxShadow: active ? "0 1px 2px rgb(0 0 0 / 0.06)" : "none",
                    }}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Breadcrumb + severity filter */}
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-2 text-sm">
            {((drillMode === "type" && drillLevel !== "type") || (drillMode === "table" && tableDrillLevel !== "tableList")) && (
              <button
                onClick={handleBack}
                className="mr-1 transition-colors"
                style={{ color: palette.textSecondary }}
              >
                ←
              </button>
            )}
            <button
              onClick={resetDrill}
              style={{
                color: (drillMode === "type" ? drillLevel === "type" : tableDrillLevel === "tableList") ? palette.textPrimary : palette.textSecondary,
                fontWeight: (drillMode === "type" ? drillLevel === "type" : tableDrillLevel === "tableList") ? 600 : 400,
              }}
            >
              {statusFilter === "passing" ? "Passing Tests" : statusFilter === "all" ? "All Tests" : "Issues"}
            </button>

            {drillMode === "type" && selectedType && (
              <>
                <span style={{ color: palette.borderSubtle }}>/</span>
                <button
                  onClick={() => setSelectedTable(null)}
                  style={{
                    color: drillLevel === "table" ? palette.textPrimary : palette.textSecondary,
                    fontWeight: drillLevel === "table" ? 600 : 400,
                  }}
                >
                  {TYPE_LABELS[selectedType] ?? selectedType}
                </button>
              </>
            )}
            {drillMode === "type" && selectedTable && (
              <>
                <span style={{ color: palette.borderSubtle }}>/</span>
                <span style={{ color: palette.textPrimary, fontWeight: 600 }}>{selectedTable}</span>
              </>
            )}

            {drillMode === "table" && selectedTableFirst && (
              <>
                <span style={{ color: palette.borderSubtle }}>/</span>
                <button
                  onClick={() => setSelectedTypeSecond(null)}
                  style={{
                    color: tableDrillLevel === "typeInTable" ? palette.textPrimary : palette.textSecondary,
                    fontWeight: tableDrillLevel === "typeInTable" ? 600 : 400,
                  }}
                >
                  {selectedTableFirst}
                </button>
              </>
            )}
            {drillMode === "table" && selectedTypeSecond && (
              <>
                <span style={{ color: palette.borderSubtle }}>/</span>
                <span style={{ color: palette.textPrimary, fontWeight: 600 }}>{TYPE_LABELS[selectedTypeSecond] ?? selectedTypeSecond}</span>
              </>
            )}
          </div>

          {/* Severity filter pills */}
          <div className="flex items-center gap-2">
            <span className="text-caption mr-1" style={{ color: palette.textSecondary, textTransform: "none", letterSpacing: "0" }}>Filter:</span>
            <FilterPill
              label="All"
              count={Object.values(severityCounts).reduce((a, b) => a + b, 0)}
              active={severityFilter === null}
              color={palette.textSecondary}
              onClick={() => setSeverityFilter(null)}
            />
            {SEV_ORDER.map((s) =>
              severityCounts[s] ? (
                <FilterPill
                  key={s}
                  label={SEVERITY_LABELS[s] ?? s}
                  count={severityCounts[s]}
                  active={severityFilter === s}
                  color={SEVERITY_COLORS[s]}
                  onClick={() => setSeverityFilter(severityFilter === s ? null : s)}
                />
              ) : null
            )}
          </div>
        </div>

        {/* Chart area */}
        <div className="transition-all duration-300">

          {drillMode === "type" && drillLevel === "type" && (
            typeChartData.length > 0 ? (
              <DrillBarChart
                data={typeChartData}
                dark={dark}
                level="type"
                onBarClick={(_d, i) => setSelectedType(typeChartData[i].rawName)}
              />
            ) : (
              <EmptyChart statusFilter={statusFilter} dark={dark} />
            )
          )}
          {drillMode === "type" && drillLevel === "table" && (
            tableChartData.length > 0 ? (
              <DrillBarChart
                data={tableChartData}
                dark={dark}
                level="table"
                onBarClick={(_d, i) => setSelectedTable(tableChartData[i].name)}
              />
            ) : (
              <div className="flex items-center justify-center h-48 text-body" style={{ color: palette.textSecondary }}>
                No tests for this filter combination
              </div>
            )
          )}
          {drillMode === "type" && drillLevel === "detail" && (
            <DetailList results={detailResults} dark={dark} queryByTestName={queryByTestName} />
          )}

          {drillMode === "table" && tableDrillLevel === "tableList" && (
            tableFirstChartData.length > 0 ? (
              <DrillBarChart
                data={tableFirstChartData}
                dark={dark}
                level="type"
                onBarClick={(_d, i) => setSelectedTableFirst(tableFirstChartData[i].name)}
              />
            ) : (
              <EmptyChart statusFilter={statusFilter} dark={dark} />
            )
          )}
          {drillMode === "table" && tableDrillLevel === "typeInTable" && (
            typeInTableChartData.length > 0 ? (
              <DrillBarChart
                data={typeInTableChartData}
                dark={dark}
                level="table"
                onBarClick={(_d, i) => setSelectedTypeSecond(typeInTableChartData[i].rawName)}
              />
            ) : (
              <div className="flex items-center justify-center h-48 text-body" style={{ color: palette.textSecondary }}>
                No tests for this filter combination
              </div>
            )
          )}
          {drillMode === "table" && tableDrillLevel === "detail" && (
            <DetailList results={detailResultsTableFirst} dark={dark} queryByTestName={queryByTestName} />
          )}
        </div>
      </div>

      {/* ── Full results table ─────────────────────────────────────────── */}
      <ResultsTable results={latestResults} summary={summary} queryByTestName={queryByTestName} />
    </div>
  );
}

/* ── Shared drill-down chart component ───────────────────────────────────── */
function DrillBarChart({
  data, dark, level, onBarClick,
}: {
  data: { name: string; count: number; outcome: string; rawName?: string }[];
  dark: boolean;
  level: string;
  onBarClick: (d: unknown, i: number) => void;
}) {
  const palette = dark ? NEUTRAL_SCALE.dark : NEUTRAL_SCALE.light;
  return (
    <ResponsiveContainer width="100%" height={320}>
      <BarChart data={data} barCategoryGap="25%">
        <XAxis
          dataKey="name"
          tick={{ fill: palette.textSecondary, fontSize: 12, fontFamily: "var(--font-inter)" }}
          axisLine={{ stroke: palette.borderSubtle }}
          tickLine={false}
        />
        <YAxis
          tick={{ fill: palette.textSecondary, fontSize: 12, fontFamily: "var(--font-inter)" }}
          axisLine={false}
          tickLine={false}
          allowDecimals={false}
        />
        <Tooltip
          content={<ChartTooltip level={level} dark={dark} />}
          cursor={{ fill: dark ? "rgba(232,236,243,0.04)" : "rgba(14,22,38,0.04)" }}
        />
        <Bar dataKey="count" radius={[8, 8, 0, 0]} cursor="pointer" animationDuration={600} onClick={onBarClick}>
          {data.map((d: any, i: number) => (
            <Cell
              key={i}
              fill={BAR_COLORS[d.outcome] || palette.textSecondary}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

function EmptyChart({ statusFilter, dark }: { statusFilter: string; dark: boolean }) {
  const palette = dark ? NEUTRAL_SCALE.dark : NEUTRAL_SCALE.light;
  return (
    <div className="flex flex-col items-center justify-center h-48 gap-2">
      <p
        className="text-heading"
        style={{ color: statusFilter === "issues" ? BRAND_TEAL : palette.textPrimary }}
      >
        {statusFilter === "issues" ? "All tests passing" : "No tests have run yet"}
      </p>
      <p className="text-body" style={{ color: palette.textSecondary }}>
        {statusFilter === "issues"
          ? "No issues detected in the latest run"
          : "Run your tests to see results here — click Run all to trigger a run."}
      </p>
    </div>
  );
}

function DetailList({
  results,
  dark,
  queryByTestName,
}: {
  results: TestResult[];
  dark: boolean;
  queryByTestName: Map<string, string>;
}) {
  const palette = dark ? NEUTRAL_SCALE.dark : NEUTRAL_SCALE.light;
  return (
    <div className="space-y-3 max-h-[400px] overflow-auto pr-2">
      {results.length > 0 ? (
        results.map((r) => (
          <DetailCard key={r.id} result={r} sqlQuery={queryByTestName.get(r.test_name)} />
        ))
      ) : (
        <div className="flex items-center justify-center h-48 text-body" style={{ color: palette.textSecondary }}>
          No tests match the current filter
        </div>
      )}
    </div>
  );
}

/* ── Sub-components ───────────────────────────────────────────────────────── */

function SummaryCard({
  label,
  value,
  delta,
  deltaPositiveIsBad = false,
  dark = true,
}: {
  label: string;
  value: number;
  delta?: number | null;
  deltaPositiveIsBad?: boolean;
  dark?: boolean;
}) {
  const palette = dark ? NEUTRAL_SCALE.dark : NEUTRAL_SCALE.light;

  let trendColor: string = palette.textSecondary;
  let glyph = "•";
  let trendLabel = "first run";

  if (delta != null) {
    if (delta === 0) {
      trendLabel = "last run";
    } else {
      glyph = delta > 0 ? "▲" : "▼";
      const isGood = delta > 0 ? !deltaPositiveIsBad : deltaPositiveIsBad;
      trendColor = isGood ? BRAND_TEAL : "#EF4444";
      trendLabel = delta > 0 ? `+${delta}` : `${delta}`;
    }
  }

  return (
    <div
      className="p-4"
      style={{
        backgroundColor: palette.surfaceElevated,
        border: `1px solid ${palette.borderSubtle}`,
        borderRadius: "8px",
      }}
    >
      <p className="text-body" style={{ color: palette.textSecondary }}>{label}</p>
      <p
        className="mt-2 text-display"
        style={{ fontFamily: "var(--font-jetbrains-mono)", color: palette.textPrimary }}
      >
        <AnimatedNumber value={value} />
      </p>
      <p className="mt-1 text-caption flex items-center gap-1" style={{ color: trendColor, textTransform: "none", letterSpacing: "0" }}>
        <span style={{ fontSize: "10px" }}>{glyph}</span>
        <span style={{ fontFamily: "var(--font-jetbrains-mono)" }}>{trendLabel}</span>
      </p>
    </div>
  );
}

function FilterPill({
  label,
  count,
  active,
  color,
  onClick,
}: {
  label: string;
  count: number;
  active: boolean;
  color: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`text-xs px-2.5 py-1 rounded-full transition-all border ${
        active
          ? "border-current font-medium"
          : "border-transparent opacity-60 hover:opacity-100"
      }`}
      style={{ color }}
    >
      {label} ({count})
    </button>
  );
}

/* ── helpers to extract table / columns ───────────────────────────────── */
function extractTable(r: TestResult): string {
  return r.table || "—";
}

function extractColumns(r: TestResult): string {
  return r.column || "—";
}

/* ── Results table with status filter ─────────────────────────────────── */
type TableFilter = "all" | "issues" | "passing";

function ResultsTable({
  results,
  summary,
  queryByTestName,
}: {
  results: TestResult[];
  summary: { total: number };
  queryByTestName: Map<string, string>;
}) {
  const { theme } = useTheme();
  const dark = theme === "dark";
  const palette = dark ? NEUTRAL_SCALE.dark : NEUTRAL_SCALE.light;
  const [filter, setFilter] = useState<TableFilter>("all");
  const [expandedRow, setExpandedRow] = useState<number | null>(null);

  const filtered = useMemo(() => {
    if (filter === "issues") return results.filter((r) => r.status !== "PASSED");
    if (filter === "passing") return results.filter((r) => r.status === "PASSED");
    return results;
  }, [results, filter]);

  const runTime = results.length > 0 ? new Date(results[0].run_at).toLocaleString() : null;

  return (
    <div
      className="overflow-hidden"
      style={{
        backgroundColor: palette.surfaceElevated,
        border: `1px solid ${palette.borderSubtle}`,
        borderRadius: "8px",
      }}
    >
      <div
        className="px-6 py-4 flex items-center justify-between"
        style={{ borderBottom: `1px solid ${palette.borderSubtle}` }}
      >
        <div>
          <h2 className="text-heading" style={{ color: palette.textPrimary }}>Latest Run Results</h2>
          {runTime && (
            <p className="text-body mt-0.5" style={{ color: palette.textSecondary }}>
              {runTime} · {summary.total} tests
            </p>
          )}
        </div>
        {/* Status filter tabs */}
        <div
          className="flex items-center rounded-lg p-0.5 gap-0.5"
          style={{ backgroundColor: palette.surfaceBg }}
        >
          {([
            ["all", "All", results.length],
            ["issues", "Issues", results.filter((r) => r.status !== "PASSED").length],
            ["passing", "Passing", results.filter((r) => r.status === "PASSED").length],
          ] as [TableFilter, string, number][]).map(([key, label, count]) => {
            const active = filter === key;
            return (
              <button
                key={key}
                onClick={() => setFilter(key)}
                className="text-xs px-3 py-1.5 rounded-md transition-all"
                style={{
                  backgroundColor: active ? palette.surfaceElevated : "transparent",
                  color: active ? palette.textPrimary : palette.textSecondary,
                  fontWeight: active ? 500 : 400,
                  boxShadow: active ? "0 1px 2px rgb(0 0 0 / 0.06)" : "none",
                }}
              >
                {label} ({count})
              </button>
            );
          })}
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead
            className="sticky top-0"
            style={{ backgroundColor: palette.surfaceBg }}
          >
            <tr style={{ color: palette.textSecondary }}>
              {/* 7px dot column */}
              <th className="pl-6 py-3" style={{ width: "24px" }}></th>
              {/* Expand-arrow column */}
              <th className="px-2 py-3" style={{ width: "24px" }}></th>
              <th className="px-4 py-3 text-left text-caption">Test</th>
              <th className="px-4 py-3 text-left text-caption">Type</th>
              <th className="px-4 py-3 text-left text-caption">Table</th>
              <th className="px-4 py-3 text-left text-caption">Column(s)</th>
              <th className="px-4 py-3 text-left text-caption">Status</th>
              <th className="px-4 py-3 text-left text-caption">Severity</th>
              <th className="px-4 py-3 text-left text-caption">Message</th>
            </tr>
          </thead>
          <tbody style={{ borderTop: `1px solid ${palette.borderSubtle}` }}>
            {filtered.map((r) => {
              const isExpanded = expandedRow === r.id;
              const metricEntries = metricEntriesOf(r);
              const isCustomSql = r.test_type === "custom_sql";
              const sqlQuery = isCustomSql ? queryByTestName.get(r.test_name) : undefined;
              const hasExpandContent = metricEntries.length > 0 || (isCustomSql && sqlQuery);
              return (
                <Fragment key={r.id}>
                  <tr
                    className="transition-colors cursor-pointer"
                    style={{ height: "40px", borderTop: `1px solid ${palette.borderSubtle}` }}
                    onClick={() => setExpandedRow(isExpanded ? null : r.id)}
                    onMouseEnter={(e) => ((e.currentTarget as HTMLTableRowElement).style.backgroundColor = dark ? "rgba(232,236,243,0.04)" : "rgba(14,22,38,0.04)")}
                    onMouseLeave={(e) => ((e.currentTarget as HTMLTableRowElement).style.backgroundColor = "transparent")}
                  >
                    {/* 7px solid status dot */}
                    <td className="pl-6 py-3"><StatusDot status={r.status} /></td>

                    {/* Expand chevron */}
                    <td className="px-2 py-3 text-caption" style={{ color: palette.textSecondary, textTransform: "none", letterSpacing: "0" }}>
                      {hasExpandContent ? (isExpanded ? "▼" : "▶") : ""}
                    </td>

                    {/* Test name — verbatim per Phase 1 D-05, JetBrains Mono */}
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

                    {/* Type column — TypePill */}
                    <td className="px-4 py-3"><TypePill type={r.test_type} /></td>

                    {/* Table cell — mono */}
                    <td
                      className="px-4 py-3 max-w-[12rem] truncate text-caption"
                      style={{
                        fontFamily: "var(--font-jetbrains-mono)",
                        color: palette.textSecondary,
                        textTransform: "none",
                        letterSpacing: "0",
                      }}
                      title={extractTable(r)}
                    >
                      {extractTable(r)}
                    </td>

                    {/* Column(s) — mono */}
                    <td
                      className="px-4 py-3 max-w-[10rem] truncate text-caption"
                      style={{
                        fontFamily: "var(--font-jetbrains-mono)",
                        color: palette.textSecondary,
                        textTransform: "none",
                        letterSpacing: "0",
                      }}
                      title={extractColumns(r)}
                    >
                      {extractColumns(r)}
                    </td>

                    <td className="px-4 py-3"><StatusBadge status={r.status} /></td>
                    <td className="px-4 py-3"><SeverityBadge severity={r.severity} /></td>

                    <td
                      className="px-4 py-3 max-w-xs truncate text-body"
                      style={{ color: palette.textSecondary }}
                      title={r.message}
                    >
                      {r.message}
                    </td>
                  </tr>
                  {isExpanded && hasExpandContent && (
                    <tr style={{ borderTop: `1px solid ${palette.borderSubtle}` }}>
                      <td colSpan={9} className="px-12 py-3" style={{ backgroundColor: palette.surfaceBg }}>
                        <ErrorDetail result={r} sqlQuery={sqlQuery} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function DetailCard({ result: r, sqlQuery }: { result: TestResult; sqlQuery?: string }) {
  const { theme } = useTheme();
  const dark = theme === "dark";
  const palette = dark ? NEUTRAL_SCALE.dark : NEUTRAL_SCALE.light;
  const [expanded, setExpanded] = useState(false);
  const table = extractTable(r);
  const columns = extractColumns(r);

  return (
    <div
      className="p-4 transition-colors cursor-pointer"
      style={{
        backgroundColor: palette.surfaceBg,
        border: `1px solid ${palette.borderSubtle}`,
        borderRadius: "8px",
      }}
      onClick={() => setExpanded(!expanded)}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <span className="text-caption" style={{ color: palette.textSecondary, textTransform: "none", letterSpacing: "0" }}>{expanded ? "▼" : "▶"}</span>
          <span
            className="font-medium truncate text-body"
            style={{ color: palette.textPrimary, fontFamily: "var(--font-jetbrains-mono)" }}
            title={r.test_name}
          >
            {r.test_name}
          </span>
        </div>
        <div className="flex gap-2 shrink-0">
          <StatusBadge status={r.status} />
          <SeverityBadge severity={r.severity} />
        </div>
      </div>

      <div className="flex items-center gap-4 mt-2 ml-6">
        {table !== "—" && (
          <span className="text-caption" style={{ color: palette.textSecondary, textTransform: "none", letterSpacing: "0" }}>
            Table: <span style={{ fontFamily: "var(--font-jetbrains-mono)", color: palette.textPrimary }}>{table}</span>
          </span>
        )}
        {columns !== "—" && (
          <span className="text-caption" style={{ color: palette.textSecondary, textTransform: "none", letterSpacing: "0" }}>
            Column{columns.includes(",") ? "s" : ""}: <span style={{ fontFamily: "var(--font-jetbrains-mono)", color: palette.textPrimary }}>{columns}</span>
          </span>
        )}
      </div>

      {r.message && !expanded && (
        <p className="text-body mt-1.5 ml-6 line-clamp-2" style={{ color: palette.textSecondary }} title={r.message}>
          {r.message}
        </p>
      )}

      {expanded && (
        <div className="mt-3 ml-6">
          <ErrorDetail result={r} sqlQuery={sqlQuery} />
        </div>
      )}
    </div>
  );
}
