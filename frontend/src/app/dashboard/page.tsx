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
  PieChart,
  Pie,
} from "recharts";
import { useAuth } from "@/lib/auth";
import { useTheme } from "@/lib/theme";
import { apiGet } from "@/lib/api";
import { SEVERITY_COLORS } from "@/lib/constants";
import { StatusBadge, SeverityBadge } from "@/components/StatusBadge";
import type { TestResult } from "@/lib/types";

/* ── colour helpers ───────────────────────────────────────────────────────── */
const SEV_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW"] as const;
const BAR_COLORS: Record<string, string> = {
  CRITICAL: "#dc2626",
  HIGH: "#ef4444",
  MEDIUM: "#f59e0b",
  LOW: "#3b82f6",
  PASSED: "#22c55e",
};
const PIE_COLORS = ["#22c55e", "#ef4444", "#f59e0b", "#6b7280"]; // pass, fail, error, skip

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
function ChartTooltip({ active, payload, label, level }: any) {
  if (!active || !payload?.length) return null;
  const count = payload[0].value;
  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 shadow-xl text-white">
      <p className="font-medium text-sm">{label}</p>
      <p className="text-gray-300 text-xs mt-1">
        {count} test{count !== 1 ? "s" : ""}
      </p>
      {level !== "detail" && (
        <p className="text-blue-400 text-xs mt-1">Click to drill down →</p>
      )}
    </div>
  );
}

/* ── severity colour for a bar based on the worst severity in that group ── */
function worstSeverity(items: TestResult[]): string {
  // If all items are passing, return a special key
  if (items.every((r) => r.status === "PASSED")) return "PASSED";
  for (const s of SEV_ORDER) {
    if (items.some((r) => r.severity === s && r.status !== "PASSED")) return s;
  }
  return "MEDIUM";
}

/* ══════════════════════════════════════════════════════════════════════════ */
export default function DashboardPage() {
  const { token, isLoading: authLoading } = useAuth();
  const { theme } = useTheme();
  const dark = theme === "dark";
  const router = useRouter();
  const [results, setResults] = useState<TestResult[]>([]);
  const [loading, setLoading] = useState(true);

  // Drill state
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [selectedTable, setSelectedTable] = useState<string | null>(null);
  const [severityFilter, setSeverityFilter] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<"all" | "issues" | "passing">("issues");

  const drillLevel = selectedTable ? "detail" : selectedType ? "table" : "type";

  useEffect(() => {
    if (authLoading) return;
    if (!token) { router.push("/login"); return; }
    apiGet("/api/v1/results?limit=500", token)
      .then(setResults)
      .catch(() => router.push("/login"))
      .finally(() => setLoading(false));
  }, [token, authLoading, router]);

  /* ── derived data (memoised) ──────────────────────────────────────────── */
  const latestResults = useMemo(() => {
    if (results.length === 0) return [];
    const latestRun = results[0].run_at;
    return results.filter((r) => r.run_at === latestRun);
  }, [results]);

  const chartResults = useMemo(() => {
    let base = latestResults;
    if (statusFilter === "issues") base = base.filter((r) => r.status !== "PASSED");
    else if (statusFilter === "passing") base = base.filter((r) => r.status === "PASSED");
    if (severityFilter) base = base.filter((r) => r.severity === severityFilter);
    return base;
  }, [latestResults, severityFilter, statusFilter]);

  // Summary counts (always from unfiltered latest)
  const summary = useMemo(() => {
    let passed = 0, failed = 0, errors = 0, skipped = 0;
    for (const r of latestResults) {
      if (r.status === "PASSED") passed++;
      else if (r.status === "FAILED") failed++;
      else if (r.status === "ERROR") errors++;
      else skipped++;
    }
    return { total: latestResults.length, passed, failed, errors, skipped };
  }, [latestResults]);

  const passRate = summary.total > 0 ? Math.round((summary.passed / summary.total) * 100) : 100;

  // Health ring data
  const pieData = useMemo(() => [
    { name: "Passed", value: summary.passed },
    { name: "Failed", value: summary.failed },
    { name: "Errors", value: summary.errors },
    { name: "Skipped", value: summary.skipped },
  ].filter((d) => d.value > 0), [summary]);

  // Level 1: tests grouped by test_type
  const typeChartData = useMemo(() => {
    const groups: Record<string, TestResult[]> = {};
    for (const r of chartResults) {
      (groups[r.test_type] ??= []).push(r);
    }
    return Object.entries(groups)
      .map(([name, items]) => ({
        name: name.replace(/_/g, " "),
        rawName: name,
        count: items.length,
        severity: worstSeverity(items),
      }))
      .sort((a, b) => b.count - a.count);
  }, [chartResults]);

  // Level 2: tests grouped by table for the selected type
  const tableChartData = useMemo(() => {
    if (!selectedType) return [];
    const groups: Record<string, TestResult[]> = {};
    for (const r of chartResults) {
      if (r.test_type !== selectedType) continue;
      const table = (r.metrics?.table as string) || r.test_name;
      (groups[table] ??= []).push(r);
    }
    return Object.entries(groups)
      .map(([name, items]) => ({
        name,
        count: items.length,
        severity: worstSeverity(items),
      }))
      .sort((a, b) => b.count - a.count);
  }, [chartResults, selectedType]);

  // Level 3: detail rows
  const detailResults = useMemo(() => {
    if (!selectedTable || !selectedType) return [];
    return chartResults.filter((r) => {
      const table = (r.metrics?.table as string) || r.test_name;
      return r.test_type === selectedType && table === selectedTable;
    });
  }, [chartResults, selectedType, selectedTable]);

  /* ── severity filter counts (for the filter pills) ─────────────────── */
  const severityCounts = useMemo(() => {
    let base = latestResults;
    if (statusFilter === "issues") base = base.filter((r) => r.status !== "PASSED");
    else if (statusFilter === "passing") base = base.filter((r) => r.status === "PASSED");
    const counts: Record<string, number> = {};
    for (const r of base) counts[r.severity] = (counts[r.severity] || 0) + 1;
    return counts;
  }, [latestResults, statusFilter]);

  /* ── handlers ──────────────────────────────────────────────────────── */
  const handleBack = () => {
    if (selectedTable) setSelectedTable(null);
    else if (selectedType) setSelectedType(null);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className={`animate-pulse ${dark ? "text-gray-500" : "text-gray-400"}`}>Loading results…</div>
      </div>
    );
  }

  /* ══════════════════════════════════════════════════════════════════════ */
  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* ── Header row: summary + health ring ──────────────────────────── */}
      <div className="grid grid-cols-12 gap-4">
        {/* Health ring */}
        <div className={`col-span-3 rounded-xl p-5 flex flex-col items-center justify-center relative border ${dark ? "bg-gray-900 border-gray-800" : "bg-white border-gray-200"}`}>
          <PieChart width={140} height={140}>
            <Pie
              data={pieData}
              cx={65}
              cy={65}
              innerRadius={45}
              outerRadius={65}
              dataKey="value"
              startAngle={90}
              endAngle={-270}
              stroke="none"
              animationDuration={800}
            >
              {pieData.map((entry, i) => (
                <Cell
                  key={entry.name}
                  fill={PIE_COLORS[["Passed", "Failed", "Errors", "Skipped"].indexOf(entry.name)] || "#6b7280"}
                />
              ))}
            </Pie>
          </PieChart>
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <div className="text-center">
              <p className={`text-2xl font-bold ${passRate >= 80 ? "text-green-400" : passRate >= 50 ? "text-yellow-400" : "text-red-400"}`}>
                {passRate}%
              </p>
            </div>
          </div>
          <p className={`text-xs mt-2 ${dark ? "text-gray-500" : "text-gray-400"}`}>Health Score</p>
        </div>

        {/* Summary cards */}
        <div className="col-span-9 grid grid-cols-4 gap-4">
          <SummaryCard label="Total Tests" value={summary.total} color={dark ? "text-white" : "text-gray-900"} icon="📋" dark={dark} />
          <SummaryCard label="Passed" value={summary.passed} color="text-green-400" icon="✓" accent="bg-green-500/10 border-green-500/20" dark={dark} />
          <SummaryCard label="Failed" value={summary.failed} color="text-red-400" icon="✗" accent="bg-red-500/10 border-red-500/20" dark={dark} />
          <SummaryCard label="Errors" value={summary.errors} color="text-yellow-400" icon="⚠" accent="bg-yellow-500/10 border-yellow-500/20" dark={dark} />
        </div>
      </div>

      {/* ── Drill-down chart ───────────────────────────────────────────── */}
      <div className={`rounded-xl border p-6 ${dark ? "bg-gray-900 border-gray-800" : "bg-white border-gray-200"}`}>
        {/* Status toggle */}
        <div className="flex items-center justify-between mb-4">
          <div className={`flex items-center rounded-lg p-0.5 gap-0.5 ${dark ? "bg-gray-800" : "bg-gray-100"}`}>
            {([
              ["issues", "Issues Only", latestResults.filter((r) => r.status !== "PASSED").length],
              ["all", "All Tests", latestResults.length],
              ["passing", "Passing", latestResults.filter((r) => r.status === "PASSED").length],
            ] as ["issues" | "all" | "passing", string, number][]).map(([key, label, count]) => (
              <button
                key={key}
                onClick={() => { setStatusFilter(key); setSelectedType(null); setSelectedTable(null); }}
                className={`text-xs px-3 py-1.5 rounded-md transition-all ${
                  statusFilter === key
                    ? dark ? "bg-gray-700 text-white font-medium" : "bg-white text-gray-900 font-medium shadow-sm"
                    : dark ? "text-gray-400 hover:text-white" : "text-gray-500 hover:text-gray-900"
                }`}
              >
                {label} ({count})
              </button>
            ))}
          </div>
          <p className={`text-xs ${dark ? "text-gray-600" : "text-gray-400"}`}>
            Showing {chartResults.length} test{chartResults.length !== 1 ? "s" : ""}
          </p>
        </div>

        {/* Breadcrumb + severity filter */}
        <div className="flex items-center justify-between mb-5">
          {/* Breadcrumb */}
          <div className="flex items-center gap-2 text-sm">
            {drillLevel !== "type" && (
              <button onClick={handleBack} className={`mr-1 transition-colors ${dark ? "text-gray-500 hover:text-white" : "text-gray-400 hover:text-gray-900"}`}>
                ←
              </button>
            )}
            <button
              onClick={() => { setSelectedType(null); setSelectedTable(null); }}
              className={drillLevel === "type"
                ? dark ? "text-white font-semibold" : "text-gray-900 font-semibold"
                : dark ? "text-gray-500 hover:text-gray-300 transition-colors" : "text-gray-400 hover:text-gray-700 transition-colors"
              }
            >
              {statusFilter === "passing" ? "Passing Tests" : statusFilter === "all" ? "All Tests" : "Issues"}
            </button>
            {selectedType && (
              <>
                <span className={dark ? "text-gray-700" : "text-gray-300"}>/</span>
                <button
                  onClick={() => setSelectedTable(null)}
                  className={drillLevel === "table"
                    ? dark ? "text-white font-semibold" : "text-gray-900 font-semibold"
                    : dark ? "text-gray-500 hover:text-gray-300 transition-colors" : "text-gray-400 hover:text-gray-700 transition-colors"
                  }
                >
                  {selectedType.replace(/_/g, " ")}
                </button>
              </>
            )}
            {selectedTable && (
              <>
                <span className={dark ? "text-gray-700" : "text-gray-300"}>/</span>
                <span className={dark ? "text-white font-semibold" : "text-gray-900 font-semibold"}>{selectedTable}</span>
              </>
            )}
          </div>

          {/* Severity filter pills */}
          <div className="flex items-center gap-2">
            <span className={`text-xs mr-1 ${dark ? "text-gray-600" : "text-gray-400"}`}>Filter:</span>
            <FilterPill
              label="All"
              count={Object.values(severityCounts).reduce((a, b) => a + b, 0)}
              active={severityFilter === null}
              color="#9ca3af"
              onClick={() => setSeverityFilter(null)}
            />
            {SEV_ORDER.map((s) =>
              severityCounts[s] ? (
                <FilterPill
                  key={s}
                  label={s}
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
          {drillLevel === "type" && (
            typeChartData.length > 0 ? (
              <ResponsiveContainer width="100%" height={320}>
                <BarChart data={typeChartData} barCategoryGap="25%">
                  <XAxis
                    dataKey="name"
                    tick={{ fill: dark ? "#9ca3af" : "#6b7280", fontSize: 12 }}
                    axisLine={{ stroke: dark ? "#374151" : "#d1d5db" }}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fill: dark ? "#9ca3af" : "#6b7280", fontSize: 12 }}
                    axisLine={false}
                    tickLine={false}
                    allowDecimals={false}
                  />
                  <Tooltip content={<ChartTooltip level="type" />} cursor={{ fill: dark ? "rgba(255,255,255,0.03)" : "rgba(0,0,0,0.04)" }} />
                  <Bar
                    dataKey="count"
                    radius={[8, 8, 0, 0]}
                    cursor="pointer"
                    animationDuration={600}
                    onClick={(_: unknown, index: number) => setSelectedType(typeChartData[index].rawName)}
                  >
                    {typeChartData.map((d, i) => (
                      <Cell key={i} fill={BAR_COLORS[d.severity] || "#6b7280"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex flex-col items-center justify-center h-48 gap-2">
                <span className="text-4xl">{statusFilter === "issues" ? "✓" : "—"}</span>
                <p className={`text-lg font-medium ${statusFilter === "issues" ? "text-green-400" : "text-gray-500"}`}>
                  {statusFilter === "issues" ? "All tests passing" : "No tests match this filter"}
                </p>
                <p className={`text-sm ${dark ? "text-gray-600" : "text-gray-400"}`}>
                  {statusFilter === "issues" ? "No issues detected in the latest run" : "Try changing the filter above"}
                </p>
              </div>
            )
          )}

          {drillLevel === "table" && (
            tableChartData.length > 0 ? (
              <ResponsiveContainer width="100%" height={320}>
                <BarChart data={tableChartData} barCategoryGap="25%">
                  <XAxis
                    dataKey="name"
                    tick={{ fill: dark ? "#9ca3af" : "#6b7280", fontSize: 12 }}
                    axisLine={{ stroke: dark ? "#374151" : "#d1d5db" }}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fill: dark ? "#9ca3af" : "#6b7280", fontSize: 12 }}
                    axisLine={false}
                    tickLine={false}
                    allowDecimals={false}
                  />
                  <Tooltip content={<ChartTooltip level="table" />} cursor={{ fill: dark ? "rgba(255,255,255,0.03)" : "rgba(0,0,0,0.04)" }} />
                  <Bar
                    dataKey="count"
                    radius={[8, 8, 0, 0]}
                    cursor="pointer"
                    animationDuration={600}
                    onClick={(_: unknown, index: number) => setSelectedTable(tableChartData[index].name)}
                  >
                    {tableChartData.map((d, i) => (
                      <Cell key={i} fill={BAR_COLORS[d.severity] || "#6b7280"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className={`flex items-center justify-center h-48 ${dark ? "text-gray-500" : "text-gray-400"}`}>
                No tests for this filter combination
              </div>
            )
          )}

          {drillLevel === "detail" && (
            <div className="space-y-3 max-h-[400px] overflow-auto pr-2">
              {detailResults.length > 0 ? (
                detailResults.map((r) => <DetailCard key={r.id} result={r} />)
              ) : (
                <div className={`flex items-center justify-center h-48 ${dark ? "text-gray-500" : "text-gray-400"}`}>
                  No tests match the current filter
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* ── Full results table ─────────────────────────────────────────── */}
      <ResultsTable results={latestResults} summary={summary} />
    </div>
  );
}

/* ── Sub-components ───────────────────────────────────────────────────────── */

function SummaryCard({
  label,
  value,
  color,
  icon,
  accent,
  dark = true,
}: {
  label: string;
  value: number;
  color: string;
  icon: string;
  accent?: string;
  dark?: boolean;
}) {
  return (
    <div className={`rounded-xl p-5 border transition-colors ${accent || (dark ? "bg-gray-900 border-gray-800" : "bg-white border-gray-200")}`}>
      <div className="flex items-center justify-between">
        <p className={`text-sm ${dark ? "text-gray-400" : "text-gray-500"}`}>{label}</p>
        <span className="text-lg opacity-50">{icon}</span>
      </div>
      <p className={`text-3xl font-bold mt-2 ${color}`}>
        <AnimatedNumber value={value} />
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

/* ── helpers to extract table / columns from metrics ──────────────────── */
function extractTable(r: TestResult): string {
  return (r.metrics?.table as string) || "—";
}

function extractColumns(r: TestResult): string {
  const m = r.metrics || {};
  // Check common metric keys that hold column info
  if (m.column) return String(m.column);
  if (Array.isArray(m.columns)) return (m.columns as string[]).join(", ");
  if (m.expected_columns && typeof m.expected_columns === "object") {
    return Object.keys(m.expected_columns as Record<string, unknown>).join(", ");
  }
  return "—";
}

/* ── Results table with status filter ─────────────────────────────────── */
type TableFilter = "all" | "issues" | "passing";

function ResultsTable({ results, summary }: { results: TestResult[]; summary: { total: number } }) {
  const { theme } = useTheme();
  const dark = theme === "dark";
  const [filter, setFilter] = useState<TableFilter>("all");
  const [expandedRow, setExpandedRow] = useState<number | null>(null);

  const filtered = useMemo(() => {
    if (filter === "issues") return results.filter((r) => r.status !== "PASSED");
    if (filter === "passing") return results.filter((r) => r.status === "PASSED");
    return results;
  }, [results, filter]);

  const runTime = results.length > 0 ? new Date(results[0].run_at).toLocaleString() : null;

  return (
    <div className={`rounded-xl border overflow-hidden ${dark ? "bg-gray-900 border-gray-800" : "bg-white border-gray-200"}`}>
      <div className={`px-6 py-4 border-b flex items-center justify-between ${dark ? "border-gray-800" : "border-gray-200"}`}>
        <div>
          <h2 className={`font-medium ${dark ? "text-white" : "text-gray-900"}`}>Latest Run Results</h2>
          {runTime && (
            <p className={`text-sm mt-0.5 ${dark ? "text-gray-500" : "text-gray-400"}`}>
              {runTime} · {summary.total} tests
            </p>
          )}
        </div>
        {/* Status filter tabs */}
        <div className={`flex items-center rounded-lg p-0.5 gap-0.5 ${dark ? "bg-gray-800" : "bg-gray-100"}`}>
          {([
            ["all", "All", results.length],
            ["issues", "Issues", results.filter((r) => r.status !== "PASSED").length],
            ["passing", "Passing", results.filter((r) => r.status === "PASSED").length],
          ] as [TableFilter, string, number][]).map(([key, label, count]) => (
            <button
              key={key}
              onClick={() => setFilter(key)}
              className={`text-xs px-3 py-1.5 rounded-md transition-all ${
                filter === key
                  ? dark ? "bg-gray-700 text-white font-medium" : "bg-white text-gray-900 font-medium shadow-sm"
                  : dark ? "text-gray-400 hover:text-white" : "text-gray-500 hover:text-gray-900"
              }`}
            >
              {label} ({count})
            </button>
          ))}
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className={`sticky top-0 ${dark ? "bg-gray-800/50" : "bg-gray-50"}`}>
            <tr className={`text-left ${dark ? "text-gray-400" : "text-gray-500"}`}>
              <th className="px-6 py-3 font-medium w-8"></th>
              <th className="px-6 py-3 font-medium">Test</th>
              <th className="px-6 py-3 font-medium">Type</th>
              <th className="px-6 py-3 font-medium">Table</th>
              <th className="px-6 py-3 font-medium">Column(s)</th>
              <th className="px-6 py-3 font-medium">Status</th>
              <th className="px-6 py-3 font-medium">Severity</th>
              <th className="px-6 py-3 font-medium">Message</th>
            </tr>
          </thead>
          <tbody className={`divide-y ${dark ? "divide-gray-800/50" : "divide-gray-100"}`}>
            {filtered.map((r) => {
              const isExpanded = expandedRow === r.id;
              const metricEntries = Object.entries(r.metrics || {}).filter(
                ([k]) => !["table", "column", "columns", "expected_columns", "query"].includes(k)
              );
              return (
                <Fragment key={r.id}>
                  <tr
                    className={`transition-colors cursor-pointer ${dark ? "hover:bg-gray-800/30" : "hover:bg-gray-50"}`}
                    onClick={() => setExpandedRow(isExpanded ? null : r.id)}
                  >
                    <td className="pl-6 py-3 text-gray-600 text-xs">
                      {metricEntries.length > 0 ? (isExpanded ? "▼" : "▶") : ""}
                    </td>
                    <td className={`px-6 py-3 ${dark ? "text-white" : "text-gray-900"}`}>{r.test_name}</td>
                    <td className={`px-6 py-3 ${dark ? "text-gray-400" : "text-gray-500"}`}>{r.test_type.replace(/_/g, " ")}</td>
                    <td className={`px-6 py-3 font-mono text-xs ${dark ? "text-gray-300" : "text-gray-600"}`}>{extractTable(r)}</td>
                    <td className={`px-6 py-3 font-mono text-xs ${dark ? "text-gray-300" : "text-gray-600"}`}>{extractColumns(r)}</td>
                    <td className="px-6 py-3"><StatusBadge status={r.status} /></td>
                    <td className="px-6 py-3"><SeverityBadge severity={r.severity} /></td>
                    <td className={`px-6 py-3 max-w-xs truncate ${dark ? "text-gray-400" : "text-gray-500"}`}>{r.message}</td>
                  </tr>
                  {isExpanded && metricEntries.length > 0 && (
                    <tr>
                      <td colSpan={8} className={`px-12 py-3 ${dark ? "bg-gray-800/20" : "bg-gray-50"}`}>
                        <div className="grid grid-cols-4 gap-3">
                          {metricEntries.map(([key, val]) => (
                            <div key={key} className={`rounded-lg px-3 py-2 ${dark ? "bg-gray-900/50" : "bg-white border border-gray-200"}`}>
                              <p className={`text-xs ${dark ? "text-gray-500" : "text-gray-400"}`}>{key.replace(/_/g, " ")}</p>
                              <p className={`text-sm font-medium mt-0.5 ${dark ? "text-white" : "text-gray-900"}`}>
                                {typeof val === "number"
                                  ? val < 1 && val > 0
                                    ? `${(val * 100).toFixed(1)}%`
                                    : val.toLocaleString()
                                  : String(val)}
                              </p>
                            </div>
                          ))}
                        </div>
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

function DetailCard({ result: r }: { result: TestResult }) {
  const { theme } = useTheme();
  const dark = theme === "dark";
  const [expanded, setExpanded] = useState(false);
  const metrics = r.metrics || {};
  const table = extractTable(r);
  const columns = extractColumns(r);
  const metricEntries = Object.entries(metrics).filter(
    ([k]) => !["table", "column", "columns", "expected_columns", "query"].includes(k)
  );

  return (
    <div
      className={`border rounded-lg p-4 transition-colors cursor-pointer ${
        dark
          ? "bg-gray-800/50 border-gray-700/50 hover:border-gray-600"
          : "bg-gray-50 border-gray-200 hover:border-gray-300"
      }`}
      onClick={() => setExpanded(!expanded)}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className={`text-xs ${dark ? "text-gray-600" : "text-gray-400"}`}>{expanded ? "▼" : "▶"}</span>
          <span className={`font-medium ${dark ? "text-white" : "text-gray-900"}`}>{r.test_name}</span>
        </div>
        <div className="flex gap-2">
          <StatusBadge status={r.status} />
          <SeverityBadge severity={r.severity} />
        </div>
      </div>

      {/* Table + column info */}
      <div className="flex items-center gap-4 mt-2 ml-6">
        {table !== "—" && (
          <span className={`text-xs ${dark ? "text-gray-500" : "text-gray-400"}`}>
            Table: <span className={`font-mono ${dark ? "text-gray-300" : "text-gray-700"}`}>{table}</span>
          </span>
        )}
        {columns !== "—" && (
          <span className={`text-xs ${dark ? "text-gray-500" : "text-gray-400"}`}>
            Column{columns.includes(",") ? "s" : ""}: <span className={`font-mono ${dark ? "text-gray-300" : "text-gray-700"}`}>{columns}</span>
          </span>
        )}
      </div>

      {r.message && (
        <p className={`text-sm mt-1.5 ml-6 ${dark ? "text-gray-400" : "text-gray-500"}`}>{r.message}</p>
      )}

      {expanded && metricEntries.length > 0 && (
        <div className="mt-3 ml-6 grid grid-cols-3 gap-3">
          {metricEntries.map(([key, val]) => (
            <div key={key} className={`rounded-lg px-3 py-2 ${dark ? "bg-gray-900/50" : "bg-white border border-gray-200"}`}>
              <p className={`text-xs ${dark ? "text-gray-500" : "text-gray-400"}`}>{key.replace(/_/g, " ")}</p>
              <p className={`text-sm font-medium mt-0.5 ${dark ? "text-white" : "text-gray-900"}`}>
                {typeof val === "number"
                  ? val < 1 && val > 0
                    ? `${(val * 100).toFixed(1)}%`
                    : val.toLocaleString()
                  : String(val)}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
