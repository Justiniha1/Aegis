"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useTheme } from "@/lib/theme";
import { apiGet } from "@/lib/api";
import { StatusBadge, SeverityBadge } from "@/components/StatusBadge";
import { TYPE_LABELS } from "@/lib/constants";
import type { TestResult, RunSummary } from "@/lib/types";

export default function HistoryPage() {
  const { token, isLoading: authLoading } = useAuth();
  const { theme } = useTheme();
  const dark = theme === "dark";
  const router = useRouter();
  const [results, setResults] = useState<TestResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedRun, setSelectedRun] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;
    if (!token) { router.push("/login"); return; }
    apiGet("/api/v1/results?limit=1000", token)
      .then(setResults)
      .catch(() => router.push("/login"))
      .finally(() => setLoading(false));
  }, [token, authLoading, router]);

  // Group results by run_at timestamp (memoized) — must be before any early returns
  const { runMap, runs } = useMemo(() => {
    const map = new Map<string, TestResult[]>();
    for (const r of results) {
      const existing = map.get(r.run_at) || [];
      existing.push(r);
      map.set(r.run_at, existing);
    }
    const summaries: RunSummary[] = Array.from(map.entries())
      .map(([run_at, items]) => ({
        run_at,
        total: items.length,
        passed: items.filter((i) => i.status === "PASSED").length,
        failed: items.filter((i) => i.status === "FAILED").length,
        errors: items.filter((i) => i.status === "ERROR").length,
      }))
      .sort((a, b) => new Date(b.run_at).getTime() - new Date(a.run_at).getTime());
    return { runMap: map, runs: summaries };
  }, [results]);

  const selectedResults = selectedRun ? runMap.get(selectedRun) || [] : [];

  if (loading || authLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className={dark ? "text-gray-400" : "text-gray-500"}>Loading history...</p>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <h1 className={`text-xl font-bold ${dark ? "text-white" : "text-gray-900"}`}>Run History</h1>

      <div className="grid grid-cols-3 gap-6">
        {/* Runs list */}
        <div className="col-span-1 space-y-2">
          {runs.map((run) => {
            const active = selectedRun === run.run_at;
            return (
              <button
                key={run.run_at}
                onClick={() => setSelectedRun(run.run_at)}
                className={`w-full text-left p-4 rounded-xl border transition-colors ${
                  active
                    ? dark ? "bg-gray-800 border-blue-500" : "bg-blue-50 border-blue-500"
                    : dark ? "bg-gray-900 border-gray-800 hover:border-gray-700" : "bg-white border-gray-200 hover:border-gray-300"
                }`}
              >
                <p className={`text-sm font-medium ${dark ? "text-white" : "text-gray-900"}`}>
                  {new Date(run.run_at).toLocaleString()}
                </p>
                <div className="flex gap-3 mt-2 text-xs">
                  <span className="text-green-500">{run.passed} passed</span>
                  {run.failed > 0 && <span className="text-red-500">{run.failed} failed</span>}
                  {run.errors > 0 && <span className="text-yellow-500">{run.errors} errors</span>}
                </div>
                <div className={`mt-2 w-full h-1.5 rounded-full overflow-hidden flex ${dark ? "bg-gray-700" : "bg-gray-200"}`}>
                  <div className="h-full bg-green-500" style={{ width: `${(run.passed / run.total) * 100}%` }} />
                  <div className="h-full bg-red-500" style={{ width: `${(run.failed / run.total) * 100}%` }} />
                  <div className="h-full bg-yellow-500" style={{ width: `${(run.errors / run.total) * 100}%` }} />
                </div>
              </button>
            );
          })}
          {runs.length === 0 && (
            <p className={`text-sm text-center py-8 ${dark ? "text-gray-500" : "text-gray-400"}`}>No runs yet</p>
          )}
        </div>

        {/* Run detail */}
        <div className="col-span-2">
          {selectedRun ? (
            <div className={`rounded-xl border overflow-hidden ${dark ? "bg-gray-900 border-gray-800" : "bg-white border-gray-200"}`}>
              <div className={`px-6 py-4 border-b ${dark ? "border-gray-800" : "border-gray-200"}`}>
                <h2 className={`font-medium ${dark ? "text-white" : "text-gray-900"}`}>
                  Run at {new Date(selectedRun).toLocaleString()}
                </h2>
                <div className="flex gap-4 mt-1 text-xs">
                  {(() => {
                    const run = runs.find((r) => r.run_at === selectedRun);
                    if (!run) return null;
                    return (
                      <>
                        <span className={dark ? "text-gray-400" : "text-gray-500"}>{run.total} total</span>
                        <span className="text-green-500">{run.passed} passed</span>
                        {run.failed > 0 && <span className="text-red-500">{run.failed} failed</span>}
                        {run.errors > 0 && <span className="text-yellow-500">{run.errors} errors</span>}
                      </>
                    );
                  })()}
                </div>
              </div>
              <table className="w-full text-sm">
                <thead className={dark ? "bg-gray-800/50" : "bg-gray-50"}>
                  <tr className={`text-left ${dark ? "text-gray-400" : "text-gray-500"}`}>
                    <th className="px-6 py-3 font-medium">Test</th>
                    <th className="px-6 py-3 font-medium">Type</th>
                    <th className="px-6 py-3 font-medium">Status</th>
                    <th className="px-6 py-3 font-medium">Severity</th>
                    <th className="px-6 py-3 font-medium">Message</th>
                  </tr>
                </thead>
                <tbody className={`divide-y ${dark ? "divide-gray-800" : "divide-gray-100"}`}>
                  {selectedResults.map((r) => (
                    <tr key={r.id} className={dark ? "hover:bg-gray-800/30" : "hover:bg-gray-50"}>
                      <td className={`px-6 py-3 ${dark ? "text-white" : "text-gray-900"}`}>{r.test_name}</td>
                      <td className={`px-6 py-3 ${dark ? "text-gray-400" : "text-gray-500"}`}>{TYPE_LABELS[r.test_type] ?? r.test_type}</td>
                      <td className="px-6 py-3"><StatusBadge status={r.status} /></td>
                      <td className="px-6 py-3"><SeverityBadge severity={r.severity} /></td>
                      <td className={`px-6 py-3 max-w-sm truncate ${dark ? "text-gray-400" : "text-gray-500"}`}>{r.message}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className={`flex items-center justify-center h-64 rounded-xl border border-dashed ${dark ? "border-gray-800 text-gray-500" : "border-gray-300 text-gray-400"}`}>
              Select a run to see details
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
