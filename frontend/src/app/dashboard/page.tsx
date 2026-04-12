"use client";

import { useEffect, useState } from "react";
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
import { apiGet } from "@/lib/api";
import { STATUS_COLORS, SEVERITY_COLORS } from "@/lib/constants";
import { StatusBadge, SeverityBadge } from "@/components/StatusBadge";
import type { TestResult } from "@/lib/types";

export default function DashboardPage() {
  const { token, isLoading: authLoading } = useAuth();
  const router = useRouter();
  const [results, setResults] = useState<TestResult[]>([]);
  const [loading, setLoading] = useState(true);

  // Drill-down: selectedType/selectedTable drive the view level
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [selectedTable, setSelectedTable] = useState<string | null>(null);

  const drillLevel = selectedTable ? "detail" : selectedType ? "table" : "type";

  useEffect(() => {
    if (authLoading) return;
    if (!token) {
      router.push("/login");
      return;
    }
    apiGet("/api/v1/results?limit=500", token)
      .then(setResults)
      .catch(() => router.push("/login"))
      .finally(() => setLoading(false));
  }, [token, authLoading, router]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-gray-400">Loading results...</p>
      </div>
    );
  }

  // Get latest run only
  const latestRunAt = results.length > 0 ? results[0].run_at : null;
  const latestResults = latestRunAt
    ? results.filter((r) => r.run_at === latestRunAt)
    : [];

  // Single pass for summary counts
  let passed = 0, failed = 0, errors = 0;
  for (const r of latestResults) {
    if (r.status === "PASSED") passed++;
    else if (r.status === "FAILED") failed++;
    else if (r.status === "ERROR") errors++;
  }
  const total = latestResults.length;

  // Level 1: Issues by test type
  const issuesByType: Record<string, number> = {};
  for (const r of latestResults) {
    if (r.status !== "PASSED") {
      issuesByType[r.test_type] = (issuesByType[r.test_type] || 0) + 1;
    }
  }
  const typeChartData = Object.entries(issuesByType)
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count);

  // Level 2: Issues by table for a selected type
  const tableChartData =
    selectedType
      ? Object.entries(
          latestResults
            .filter((r) => r.test_type === selectedType && r.status !== "PASSED")
            .reduce<Record<string, number>>((acc, r) => {
              const table = (r.metrics?.table as string) || r.test_name;
              acc[table] = (acc[table] || 0) + 1;
              return acc;
            }, {})
        )
          .map(([name, count]) => ({ name, count }))
          .sort((a, b) => b.count - a.count)
      : [];

  // Level 3: Detail view for a selected table
  const detailResults = selectedTable
    ? latestResults.filter((r) => {
        const table = (r.metrics?.table as string) || r.test_name;
        return (
          r.test_type === selectedType &&
          table === selectedTable &&
          r.status !== "PASSED"
        );
      })
    : [];

  const handleBack = () => {
    if (selectedTable) setSelectedTable(null);
    else if (selectedType) setSelectedType(null);
  };

  return (
    <div className="space-y-8">
      {/* Summary cards */}
      <div className="grid grid-cols-4 gap-4">
        <SummaryCard label="Total Tests" value={total} color="text-white" />
        <SummaryCard label="Passed" value={passed} color="text-green-400" />
        <SummaryCard label="Failed" value={failed} color="text-red-400" />
        <SummaryCard label="Errors" value={errors} color="text-yellow-400" />
      </div>

      {/* Drill-down chart area */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-6">
        {/* Breadcrumb */}
        <div className="flex items-center gap-2 mb-4 text-sm">
          <button
            onClick={() => { setSelectedType(null); setSelectedTable(null); }}
            className={drillLevel === "type" ? "text-white font-medium" : "text-gray-400 hover:text-white"}
          >
            Issues by Type
          </button>
          {selectedType && (
            <>
              <span className="text-gray-600">/</span>
              <button
                onClick={() => setSelectedTable(null)}
                className={drillLevel === "table" ? "text-white font-medium" : "text-gray-400 hover:text-white"}
              >
                {selectedType}
              </button>
            </>
          )}
          {selectedTable && (
            <>
              <span className="text-gray-600">/</span>
              <span className="text-white font-medium">{selectedTable}</span>
            </>
          )}
        </div>

        {drillLevel !== "type" && (
          <button
            onClick={handleBack}
            className="text-sm text-blue-400 hover:text-blue-300 mb-4 flex items-center gap-1"
          >
            ← Back
          </button>
        )}

        {/* Charts */}
        {drillLevel === "type" && (
          typeChartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={typeChartData}>
                <XAxis dataKey="name" tick={{ fill: "#9ca3af", fontSize: 12 }} />
                <YAxis tick={{ fill: "#9ca3af", fontSize: 12 }} allowDecimals={false} />
                <Tooltip
                  contentStyle={{ backgroundColor: "#1f2937", border: "1px solid #374151", borderRadius: "8px", color: "#fff" }}
                />
                <Bar
                  dataKey="count"
                  radius={[6, 6, 0, 0]}
                  cursor="pointer"
                  onClick={(_: unknown, index: number) => setSelectedType(typeChartData[index].name)}
                >
                  {typeChartData.map((_, i) => (
                    <Cell key={i} fill="#ef4444" />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex items-center justify-center h-48 text-green-400 text-lg font-medium">
              All tests passing
            </div>
          )
        )}

        {drillLevel === "table" && (
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={tableChartData}>
              <XAxis dataKey="name" tick={{ fill: "#9ca3af", fontSize: 12 }} />
              <YAxis tick={{ fill: "#9ca3af", fontSize: 12 }} allowDecimals={false} />
              <Tooltip
                contentStyle={{ backgroundColor: "#1f2937", border: "1px solid #374151", borderRadius: "8px", color: "#fff" }}
              />
              <Bar
                dataKey="count"
                radius={[6, 6, 0, 0]}
                cursor="pointer"
                onClick={(_: unknown, index: number) => setSelectedTable(tableChartData[index].name)}
              >
                {tableChartData.map((_, i) => (
                  <Cell key={i} fill="#f59e0b" />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}

        {drillLevel === "detail" && (
          <div className="space-y-3">
            {detailResults.map((r) => (
              <div key={r.id} className="bg-gray-800 border border-gray-700 rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-white font-medium">{r.test_name}</span>
                  <div className="flex gap-2">
                    <StatusBadge status={r.status} />
                    <SeverityBadge severity={r.severity} />
                  </div>
                </div>
                <p className="text-gray-400 text-sm">{r.message}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* All results table */}
      <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-800">
          <h2 className="text-white font-medium">Latest Run Results</h2>
          {latestRunAt && (
            <p className="text-gray-500 text-sm mt-1">
              {new Date(latestRunAt).toLocaleString()}
            </p>
          )}
        </div>
        <table className="w-full text-sm">
          <thead className="bg-gray-800/50">
            <tr className="text-gray-400 text-left">
              <th className="px-6 py-3">Test</th>
              <th className="px-6 py-3">Type</th>
              <th className="px-6 py-3">Status</th>
              <th className="px-6 py-3">Severity</th>
              <th className="px-6 py-3">Message</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800">
            {latestResults.map((r) => (
              <tr key={r.id} className="hover:bg-gray-800/30">
                <td className="px-6 py-3 text-white">{r.test_name}</td>
                <td className="px-6 py-3 text-gray-400">{r.test_type}</td>
                <td className="px-6 py-3"><StatusBadge status={r.status} /></td>
                <td className="px-6 py-3"><SeverityBadge severity={r.severity} /></td>
                <td className="px-6 py-3 text-gray-400 max-w-xs truncate">{r.message}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SummaryCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
      <p className="text-gray-400 text-sm">{label}</p>
      <p className={`text-3xl font-bold mt-1 ${color}`}>{value}</p>
    </div>
  );
}
