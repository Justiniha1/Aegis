"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { apiGet } from "@/lib/api";
import { StatusBadge } from "@/components/StatusBadge";
import type { TestResult, RunSummary } from "@/lib/types";

export default function HistoryPage() {
  const { token, isLoading: authLoading } = useAuth();
  const router = useRouter();
  const [results, setResults] = useState<TestResult[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedRun, setSelectedRun] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;
    if (!token) {
      router.push("/login");
      return;
    }
    apiGet("/api/v1/results?limit=1000", token)
      .then(setResults)
      .catch(() => router.push("/login"))
      .finally(() => setLoading(false));
  }, [token, authLoading, router]);

  if (loading || authLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-gray-400">Loading history...</p>
      </div>
    );
  }

  // Group results by run_at timestamp
  const runMap = new Map<string, TestResult[]>();
  for (const r of results) {
    const existing = runMap.get(r.run_at) || [];
    existing.push(r);
    runMap.set(r.run_at, existing);
  }

  const runs: RunSummary[] = Array.from(runMap.entries())
    .map(([run_at, items]) => ({
      run_at,
      total: items.length,
      passed: items.filter((i) => i.status === "PASSED").length,
      failed: items.filter((i) => i.status === "FAILED").length,
      errors: items.filter((i) => i.status === "ERROR").length,
    }))
    .sort((a, b) => new Date(b.run_at).getTime() - new Date(a.run_at).getTime());

  const selectedResults = selectedRun ? runMap.get(selectedRun) || [] : [];

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold text-white">Run History</h1>

      <div className="grid grid-cols-3 gap-6">
        {/* Runs list */}
        <div className="col-span-1 space-y-2">
          {runs.map((run) => {
            const active = selectedRun === run.run_at;
            const allPassed = run.failed === 0 && run.errors === 0;
            return (
              <button
                key={run.run_at}
                onClick={() => setSelectedRun(run.run_at)}
                className={`w-full text-left p-4 rounded-xl border transition-colors ${
                  active
                    ? "bg-gray-800 border-blue-500"
                    : "bg-gray-900 border-gray-800 hover:border-gray-700"
                }`}
              >
                <p className="text-sm text-white font-medium">
                  {new Date(run.run_at).toLocaleString()}
                </p>
                <div className="flex gap-3 mt-2 text-xs">
                  <span className="text-green-400">{run.passed} passed</span>
                  {run.failed > 0 && (
                    <span className="text-red-400">{run.failed} failed</span>
                  )}
                  {run.errors > 0 && (
                    <span className="text-yellow-400">{run.errors} errors</span>
                  )}
                </div>
                <div className="mt-2 w-full h-1.5 bg-gray-700 rounded-full overflow-hidden flex">
                  <div
                    className="h-full bg-green-500"
                    style={{ width: `${(run.passed / run.total) * 100}%` }}
                  />
                  <div
                    className="h-full bg-red-500"
                    style={{ width: `${(run.failed / run.total) * 100}%` }}
                  />
                  <div
                    className="h-full bg-yellow-500"
                    style={{ width: `${(run.errors / run.total) * 100}%` }}
                  />
                </div>
              </button>
            );
          })}
          {runs.length === 0 && (
            <p className="text-gray-500 text-sm text-center py-8">
              No runs yet
            </p>
          )}
        </div>

        {/* Run detail */}
        <div className="col-span-2">
          {selectedRun ? (
            <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-800">
                <h2 className="text-white font-medium">
                  Run at {new Date(selectedRun).toLocaleString()}
                </h2>
              </div>
              <table className="w-full text-sm">
                <thead className="bg-gray-800/50">
                  <tr className="text-gray-400 text-left">
                    <th className="px-6 py-3">Test</th>
                    <th className="px-6 py-3">Type</th>
                    <th className="px-6 py-3">Status</th>
                    <th className="px-6 py-3">Message</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800">
                  {selectedResults.map((r) => (
                    <tr key={r.id} className="hover:bg-gray-800/30">
                      <td className="px-6 py-3 text-white">{r.test_name}</td>
                      <td className="px-6 py-3 text-gray-400">{r.test_type}</td>
                      <td className="px-6 py-3">
                        <StatusBadge status={r.status} />
                      </td>
                      <td className="px-6 py-3 text-gray-400 max-w-sm truncate">
                        {r.message}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="flex items-center justify-center h-64 text-gray-500">
              Select a run to see details
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
