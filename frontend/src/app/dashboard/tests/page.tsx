"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useTheme } from "@/lib/theme";
import { apiGet, apiDelete, apiPost } from "@/lib/api";
import { SeverityBadge } from "@/components/StatusBadge";
import type { TestDefinition } from "@/lib/types";

export default function TestsPage() {
  const { token, isLoading: authLoading } = useAuth();
  const { theme } = useTheme();
  const dark = theme === "dark";
  const router = useRouter();
  const [tests, setTests] = useState<TestDefinition[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);

  const fetchTests = () => {
    if (!token) return;
    apiGet("/api/v1/tests", token)
      .then(setTests)
      .catch(() => router.push("/login"))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    if (authLoading) return;
    if (!token) { router.push("/login"); return; }
    fetchTests();
  }, [token, authLoading, router]);

  const handleDelete = async (id: number, name: string) => {
    if (!confirm(`Delete test "${name}"?`)) return;
    try {
      await apiDelete(`/api/v1/tests/${id}`, token!);
      setTests(tests.filter((t) => t.id !== id));
    } catch (err) {
      alert(err instanceof Error ? err.message : "Delete failed");
    }
  };

  if (loading || authLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className={dark ? "text-gray-400" : "text-gray-500"}>Loading tests...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className={`text-xl font-bold ${dark ? "text-white" : "text-gray-900"}`}>Test Definitions</h1>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg transition-colors"
        >
          {showCreate ? "Cancel" : "New Test"}
        </button>
      </div>

      {showCreate && (
        <CreateTestForm token={token!} dark={dark} onCreated={() => { setShowCreate(false); fetchTests(); }} />
      )}

      <div className={`rounded-xl border overflow-hidden ${dark ? "bg-gray-900 border-gray-800" : "bg-white border-gray-200"}`}>
        <table className="w-full text-sm">
          <thead className={dark ? "bg-gray-800/50" : "bg-gray-50"}>
            <tr className={`text-left ${dark ? "text-gray-400" : "text-gray-500"}`}>
              <th className="px-6 py-3 font-medium">Name</th>
              <th className="px-6 py-3 font-medium">Type</th>
              <th className="px-6 py-3 font-medium">Severity</th>
              <th className="px-6 py-3 font-medium">Enabled</th>
              <th className="px-6 py-3 font-medium">Tags</th>
              <th className="px-6 py-3 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody className={`divide-y ${dark ? "divide-gray-800" : "divide-gray-100"}`}>
            {tests.map((t) => (
              <tr key={t.id} className={dark ? "hover:bg-gray-800/30" : "hover:bg-gray-50"}>
                <td className="px-6 py-3">
                  <div className={dark ? "text-white" : "text-gray-900"}>{t.name}</div>
                  {t.description && (
                    <div className={`text-xs mt-0.5 ${dark ? "text-gray-500" : "text-gray-400"}`}>
                      {t.description}
                    </div>
                  )}
                </td>
                <td className={`px-6 py-3 ${dark ? "text-gray-400" : "text-gray-500"}`}>
                  {t.type.replace(/_/g, " ")}
                </td>
                <td className="px-6 py-3"><SeverityBadge severity={t.severity} /></td>
                <td className="px-6 py-3">
                  <span className={`text-xs font-medium ${t.enabled ? "text-green-500" : dark ? "text-gray-500" : "text-gray-400"}`}>
                    {t.enabled ? "Yes" : "No"}
                  </span>
                </td>
                <td className="px-6 py-3">
                  <div className="flex flex-wrap gap-1">
                    {t.tags.map((tag) => (
                      <span
                        key={tag}
                        className={`text-xs px-2 py-0.5 rounded ${dark ? "bg-gray-800 text-gray-400" : "bg-gray-100 text-gray-600"}`}
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                </td>
                <td className="px-6 py-3">
                  <button
                    onClick={() => handleDelete(t.id, t.name)}
                    className="text-xs text-red-400 hover:text-red-300 font-medium"
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {tests.length === 0 && (
          <div className={`px-6 py-12 text-center ${dark ? "text-gray-500" : "text-gray-400"}`}>
            No test definitions yet. Click &quot;New Test&quot; to create one.
          </div>
        )}
      </div>
    </div>
  );
}

function CreateTestForm({ token, dark, onCreated }: { token: string; dark: boolean; onCreated: () => void }) {
  const [name, setName] = useState("");
  const [type, setType] = useState("null_check");
  const [severity, setSeverity] = useState("MEDIUM");
  const [table, setTable] = useState("");
  const [column, setColumn] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const TEST_TYPES = [
    "null_check", "duplicate_check", "unique_check", "row_count",
    "schema_check", "range_check", "relationship_check", "custom_sql",
  ];

  const inputCls = `w-full px-3 py-2 rounded-lg text-sm border focus:outline-none focus:border-blue-500 ${
    dark
      ? "bg-gray-800 border-gray-700 text-white placeholder-gray-500"
      : "bg-white border-gray-300 text-gray-900 placeholder-gray-400"
  }`;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    const config: Record<string, unknown> = { table };
    if (column) config.column = column;
    try {
      await apiPost("/api/v1/tests", { name, type, severity, config, enabled: true, tags: [], profile: "dev" }, token);
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create test");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className={`rounded-xl border p-6 ${dark ? "bg-gray-900 border-gray-800" : "bg-white border-gray-200"}`}>
      <h2 className={`font-medium mb-4 ${dark ? "text-white" : "text-gray-900"}`}>Create Test</h2>
      <form onSubmit={handleSubmit} className="grid grid-cols-2 gap-4">
        <div>
          <label className={`block text-sm mb-1 ${dark ? "text-gray-400" : "text-gray-600"}`}>Name</label>
          <input value={name} onChange={(e) => setName(e.target.value)} required placeholder="Customer Email Null Check" className={inputCls} />
        </div>
        <div>
          <label className={`block text-sm mb-1 ${dark ? "text-gray-400" : "text-gray-600"}`}>Type</label>
          <select value={type} onChange={(e) => setType(e.target.value)} className={inputCls}>
            {TEST_TYPES.map((t) => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}
          </select>
        </div>
        <div>
          <label className={`block text-sm mb-1 ${dark ? "text-gray-400" : "text-gray-600"}`}>Table</label>
          <input value={table} onChange={(e) => setTable(e.target.value)} required placeholder="customers" className={inputCls} />
        </div>
        <div>
          <label className={`block text-sm mb-1 ${dark ? "text-gray-400" : "text-gray-600"}`}>Column (optional)</label>
          <input value={column} onChange={(e) => setColumn(e.target.value)} placeholder="email" className={inputCls} />
        </div>
        <div>
          <label className={`block text-sm mb-1 ${dark ? "text-gray-400" : "text-gray-600"}`}>Severity</label>
          <select value={severity} onChange={(e) => setSeverity(e.target.value)} className={inputCls}>
            <option value="LOW">LOW</option>
            <option value="MEDIUM">MEDIUM</option>
            <option value="HIGH">HIGH</option>
            <option value="CRITICAL">CRITICAL</option>
          </select>
        </div>
        <div className="flex items-end">
          <button type="submit" disabled={submitting} className="px-4 py-2 bg-green-600 hover:bg-green-500 disabled:bg-green-800 text-white text-sm rounded-lg transition-colors">
            {submitting ? "Creating..." : "Create Test"}
          </button>
        </div>
        {error && <p className="col-span-2 text-red-400 text-sm bg-red-400/10 px-3 py-2 rounded-lg">{error}</p>}
      </form>
    </div>
  );
}
