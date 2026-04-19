"use client";

import { Fragment, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useTheme } from "@/lib/theme";
import { apiGet, apiGetText, apiDelete, apiPost, apiPut } from "@/lib/api";
import { SeverityBadge } from "@/components/StatusBadge";
import type { TestDefinition } from "@/lib/types";

/* ── Helpers ──────────────────────────────────────────────────────────────── */
function extractTable(t: TestDefinition): string {
  return (t.config?.table as string) || "—";
}
function extractColumns(t: TestDefinition): string {
  const c = t.config || {};
  if (c.column) return String(c.column);
  if (Array.isArray(c.columns)) return (c.columns as string[]).join(", ");
  return "—";
}

const TEST_TYPES = [
  "null_check", "duplicate_check", "unique_check", "row_count",
  "schema_check", "range_check", "relationship_check", "custom_sql",
];

/* ══════════════════════════════════════════════════════════════════════════ */
export default function TestsPage() {
  const { token, isLoading: authLoading } = useAuth();
  const { theme } = useTheme();
  const dark = theme === "dark";
  const router = useRouter();
  const [tests, setTests] = useState<TestDefinition[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"table" | "yaml">("table");
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

  const handleToggleEnabled = async (test: TestDefinition) => {
    try {
      await apiPut(`/api/v1/tests/${test.id}`, {
        name: test.name,
        description: test.description,
        type: test.type,
        severity: test.severity,
        enabled: !test.enabled,
        tags: test.tags,
        config: test.config,
        profile: test.profile,
      }, token!);
      setTests(tests.map((t) => t.id === test.id ? { ...t, enabled: !t.enabled } : t));
    } catch (err) {
      alert(err instanceof Error ? err.message : "Toggle failed");
    }
  };

  if (loading || authLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className={dark ? "text-gray-400" : "text-gray-500"}>Loading tests...</p>
      </div>
    );
  }

  const enabledCount = tests.filter((t) => t.enabled).length;
  const disabledCount = tests.length - enabledCount;

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className={`text-xl font-bold ${dark ? "text-white" : "text-gray-900"}`}>Test Definitions</h1>
          <p className={`text-sm mt-0.5 ${dark ? "text-gray-500" : "text-gray-400"}`}>
            {tests.length} tests · {enabledCount} enabled · {disabledCount} disabled
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* Tabs */}
          <div className={`flex items-center rounded-lg p-0.5 gap-0.5 ${dark ? "bg-gray-800" : "bg-gray-100"}`}>
            {([["table", "Tests"], ["yaml", "YAML Editor"]] as ["table" | "yaml", string][]).map(([key, label]) => (
              <button
                key={key}
                onClick={() => setActiveTab(key)}
                className={`text-xs px-3 py-1.5 rounded-md transition-all ${
                  activeTab === key
                    ? dark ? "bg-gray-700 text-white font-medium" : "bg-white text-gray-900 font-medium shadow-sm"
                    : dark ? "text-gray-400 hover:text-white" : "text-gray-500 hover:text-gray-900"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          {activeTab === "table" && (
            <button
              onClick={() => setShowCreate(!showCreate)}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded-lg transition-colors"
            >
              {showCreate ? "Cancel" : "+ New Test"}
            </button>
          )}
        </div>
      </div>

      {/* Create form */}
      {showCreate && activeTab === "table" && (
        <CreateTestForm token={token!} dark={dark} onCreated={() => { setShowCreate(false); fetchTests(); }} />
      )}

      {/* Tab content */}
      {activeTab === "table" ? (
        <TestTable tests={tests} dark={dark} onDelete={handleDelete} onToggle={handleToggleEnabled} />
      ) : (
        <YamlEditor token={token!} dark={dark} onSaved={fetchTests} />
      )}
    </div>
  );
}

/* ── Test Table ───────────────────────────────────────────────────────────── */
function TestTable({
  tests, dark, onDelete, onToggle,
}: {
  tests: TestDefinition[];
  dark: boolean;
  onDelete: (id: number, name: string) => void;
  onToggle: (test: TestDefinition) => void;
}) {
  const [expandedId, setExpandedId] = useState<number | null>(null);

  return (
    <div className={`rounded-xl border overflow-hidden ${dark ? "bg-gray-900 border-gray-800" : "bg-white border-gray-200"}`}>
      <table className="w-full text-sm">
        <thead className={dark ? "bg-gray-800/50" : "bg-gray-50"}>
          <tr className={`text-left ${dark ? "text-gray-400" : "text-gray-500"}`}>
            <th className="px-6 py-3 font-medium w-8"></th>
            <th className="px-6 py-3 font-medium">Name</th>
            <th className="px-6 py-3 font-medium">Type</th>
            <th className="px-6 py-3 font-medium">Table</th>
            <th className="px-6 py-3 font-medium">Column(s)</th>
            <th className="px-6 py-3 font-medium">Severity</th>
            <th className="px-6 py-3 font-medium">Enabled</th>
            <th className="px-6 py-3 font-medium">Actions</th>
          </tr>
        </thead>
        <tbody className={`divide-y ${dark ? "divide-gray-800" : "divide-gray-100"}`}>
          {tests.map((t) => {
            const isExpanded = expandedId === t.id;
            const configEntries = Object.entries(t.config || {}).filter(
              ([k]) => !["table", "column", "columns"].includes(k)
            );
            return (
              <Fragment key={t.id}>
                <tr
                  className={`transition-colors cursor-pointer ${
                    dark ? "hover:bg-gray-800/30" : "hover:bg-gray-50"
                  } ${!t.enabled ? "opacity-50" : ""}`}
                  onClick={() => setExpandedId(isExpanded ? null : t.id)}
                >
                  <td className="pl-6 py-3 text-gray-500 text-xs">
                    {configEntries.length > 0 ? (isExpanded ? "▼" : "▶") : ""}
                  </td>
                  <td className="px-6 py-3">
                    <div className={dark ? "text-white" : "text-gray-900"}>{t.name}</div>
                    {t.description && (
                      <div className={`text-xs mt-0.5 ${dark ? "text-gray-500" : "text-gray-400"}`}>{t.description}</div>
                    )}
                  </td>
                  <td className={`px-6 py-3 ${dark ? "text-gray-400" : "text-gray-500"}`}>
                    {t.type.replace(/_/g, " ")}
                  </td>
                  <td className={`px-6 py-3 font-mono text-xs ${dark ? "text-gray-300" : "text-gray-600"}`}>
                    {extractTable(t)}
                  </td>
                  <td className={`px-6 py-3 font-mono text-xs ${dark ? "text-gray-300" : "text-gray-600"}`}>
                    {extractColumns(t)}
                  </td>
                  <td className="px-6 py-3"><SeverityBadge severity={t.severity} /></td>
                  <td className="px-6 py-3">
                    <button
                      onClick={(e) => { e.stopPropagation(); onToggle(t); }}
                      className={`w-9 h-5 rounded-full relative transition-colors ${
                        t.enabled ? "bg-green-500" : dark ? "bg-gray-700" : "bg-gray-300"
                      }`}
                    >
                      <div className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${
                        t.enabled ? "left-4" : "left-0.5"
                      }`} />
                    </button>
                  </td>
                  <td className="px-6 py-3">
                    <button
                      onClick={(e) => { e.stopPropagation(); onDelete(t.id, t.name); }}
                      className="text-xs text-red-400 hover:text-red-300 font-medium"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
                {isExpanded && configEntries.length > 0 && (
                  <tr>
                    <td colSpan={8} className={`px-12 py-3 ${dark ? "bg-gray-800/20" : "bg-gray-50"}`}>
                      <div className="grid grid-cols-4 gap-3">
                        <div className={`rounded-lg px-3 py-2 ${dark ? "bg-gray-900/50" : "bg-white border border-gray-200"}`}>
                          <p className={`text-xs ${dark ? "text-gray-500" : "text-gray-400"}`}>profile</p>
                          <p className={`text-sm font-medium mt-0.5 ${dark ? "text-white" : "text-gray-900"}`}>{t.profile}</p>
                        </div>
                        {t.tags.length > 0 && (
                          <div className={`rounded-lg px-3 py-2 ${dark ? "bg-gray-900/50" : "bg-white border border-gray-200"}`}>
                            <p className={`text-xs ${dark ? "text-gray-500" : "text-gray-400"}`}>tags</p>
                            <div className="flex flex-wrap gap-1 mt-1">
                              {t.tags.map((tag) => (
                                <span key={tag} className={`text-xs px-1.5 py-0.5 rounded ${dark ? "bg-gray-800 text-gray-400" : "bg-gray-100 text-gray-600"}`}>
                                  {tag}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                        {configEntries.map(([key, val]) => (
                          <div key={key} className={`rounded-lg px-3 py-2 ${dark ? "bg-gray-900/50" : "bg-white border border-gray-200"}`}>
                            <p className={`text-xs ${dark ? "text-gray-500" : "text-gray-400"}`}>{key.replace(/_/g, " ")}</p>
                            <p className={`text-sm font-medium mt-0.5 break-all ${dark ? "text-white" : "text-gray-900"}`}>
                              {typeof val === "object" ? JSON.stringify(val) : String(val)}
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
      {tests.length === 0 && (
        <div className={`px-6 py-12 text-center ${dark ? "text-gray-500" : "text-gray-400"}`}>
          No test definitions yet. Click &quot;+ New Test&quot; to create one.
        </div>
      )}
    </div>
  );
}

/* ── YAML Editor ──────────────────────────────────────────────────────────── */
function YamlEditor({ token, dark, onSaved }: { token: string; dark: boolean; onSaved: () => void }) {
  const [yamlContent, setYamlContent] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<{ type: "success" | "error"; message: string } | null>(null);

  useEffect(() => {
    apiGetText("/api/v1/tests/yaml", token)
      .then(setYamlContent)
      .catch((err) => setFeedback({ type: "error", message: err.message }))
      .finally(() => setLoading(false));
  }, [token]);

  const handleSave = async () => {
    setSaving(true);
    setFeedback(null);
    try {
      const result = await apiPost("/api/v1/tests/sync", { yaml_content: yamlContent }, token);
      const msg = `Sync complete: ${result.created} created, ${result.updated} updated, ${result.deleted} deleted, ${result.unchanged} unchanged`;
      setFeedback({ type: "success", message: msg });
      onSaved();
      // Reload the YAML to show the normalized version from the DB
      const refreshed = await apiGetText("/api/v1/tests/yaml", token);
      setYamlContent(refreshed);
    } catch (err) {
      setFeedback({ type: "error", message: err instanceof Error ? err.message : "Sync failed" });
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className={dark ? "text-gray-400" : "text-gray-500"}>Loading YAML...</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Warning banner */}
      <div className={`rounded-lg px-4 py-3 text-sm flex items-center gap-2 ${dark ? "bg-yellow-500/10 text-yellow-400 border border-yellow-500/20" : "bg-yellow-50 text-yellow-700 border border-yellow-200"}`}>
        <span>⚠️</span>
        <span>Saving will sync all test definitions with the database. Tests removed from the YAML will be deleted.</span>
      </div>

      {/* Editor */}
      <div className={`rounded-xl border overflow-hidden ${dark ? "bg-gray-900 border-gray-800" : "bg-white border-gray-200"}`}>
        <div className={`px-4 py-3 border-b flex items-center justify-between ${dark ? "border-gray-800" : "border-gray-200"}`}>
          <p className={`text-sm font-medium ${dark ? "text-gray-300" : "text-gray-700"}`}>test_definitions.yaml</p>
          <div className="flex items-center gap-3">
            {feedback && (
              <span className={`text-xs ${feedback.type === "success" ? "text-green-400" : "text-red-400"}`}>
                {feedback.message}
              </span>
            )}
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-4 py-1.5 bg-green-600 hover:bg-green-500 disabled:bg-green-800 text-white text-sm rounded-lg transition-colors"
            >
              {saving ? "Saving..." : "Save & Sync"}
            </button>
          </div>
        </div>
        <textarea
          value={yamlContent}
          onChange={(e) => { setYamlContent(e.target.value); setFeedback(null); }}
          spellCheck={false}
          className={`w-full h-[600px] px-6 py-4 font-mono text-sm resize-none focus:outline-none ${
            dark
              ? "bg-gray-950 text-gray-300 placeholder-gray-600"
              : "bg-gray-50 text-gray-800 placeholder-gray-400"
          }`}
          placeholder="# Paste or edit your YAML test definitions here..."
        />
      </div>
    </div>
  );
}

/* ── YAML preview builder (mirrors Python _db_test_to_yaml_dict) ──────────── */
function buildYamlPreview(f: {
  name: string; type: string; severity: string; description: string; profile: string;
  table: string; column: string; threshold: string; query: string;
  minRows: string; maxRows: string; minValue: string; maxValue: string;
  refTable: string; refColumn: string; expectedColumns: string;
}): string {
  const lines: string[] = [];
  lines.push(`name: ${f.name || "(required)"}`);
  if (f.description) lines.push(`description: ${f.description}`);
  lines.push(`type: ${f.type}`);
  lines.push(`severity: ${f.severity}`);
  if (f.profile && f.profile !== "dev") lines.push(`profile: ${f.profile}`);

  if (f.type !== "custom_sql" && f.table) lines.push(`table: ${f.table}`);
  if (["null_check", "range_check", "unique_check", "duplicate_check", "relationship_check"].includes(f.type) && f.column) {
    lines.push(`column: ${f.column}`);
  }
  if (f.type === "null_check" && f.threshold) lines.push(`threshold: ${f.threshold}`);
  if (f.type === "range_check") {
    if (f.minValue) lines.push(`min_value: ${f.minValue}`);
    if (f.maxValue) lines.push(`max_value: ${f.maxValue}`);
  }
  if (f.type === "row_count") {
    if (f.minRows) lines.push(`min_rows: ${f.minRows}`);
    if (f.maxRows) lines.push(`max_rows: ${f.maxRows}`);
  }
  if (f.type === "relationship_check") {
    if (f.refTable) lines.push(`ref_table: ${f.refTable}`);
    if (f.refColumn) lines.push(`ref_column: ${f.refColumn}`);
  }
  if (f.type === "schema_check" && f.expectedColumns) {
    const cols = f.expectedColumns.split(",").map((c) => c.trim()).filter(Boolean);
    if (cols.length > 0) {
      lines.push(`expected_columns:`);
      cols.forEach((c) => lines.push(`  - ${c}`));
    }
  }
  if (f.type === "custom_sql" && f.query) {
    const indented = f.query.split("\n").map((l) => `  ${l}`).join("\n");
    lines.push(`query: |\n${indented}`);
  }
  return lines.join("\n");
}

/* ── Create Form ──────────────────────────────────────────────────────────── */
function CreateTestForm({ token, dark, onCreated }: { token: string; dark: boolean; onCreated: () => void }) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [type, setType] = useState("null_check");
  const [severity, setSeverity] = useState("MEDIUM");
  const [profile, setProfile] = useState("dev");
  const [table, setTable] = useState("");
  const [column, setColumn] = useState("");
  const [threshold, setThreshold] = useState("");
  const [query, setQuery] = useState("");
  const [minRows, setMinRows] = useState("");
  const [maxRows, setMaxRows] = useState("");
  const [minValue, setMinValue] = useState("");
  const [maxValue, setMaxValue] = useState("");
  const [refTable, setRefTable] = useState("");
  const [refColumn, setRefColumn] = useState("");
  const [expectedColumns, setExpectedColumns] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const formState = { name, description, type, severity, profile, table, column, threshold, query, minRows, maxRows, minValue, maxValue, refTable, refColumn, expectedColumns };

  const inputCls = `w-full px-3 py-2 rounded-lg text-sm border focus:outline-none focus:border-blue-500 ${
    dark ? "bg-gray-800 border-gray-700 text-white placeholder-gray-500" : "bg-white border-gray-300 text-gray-900 placeholder-gray-400"
  }`;

  const labelCls = `block text-xs font-medium mb-1 ${dark ? "text-gray-400" : "text-gray-600"}`;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    const config: Record<string, unknown> = {};
    if (table) config.table = table;
    if (column && ["null_check", "range_check", "unique_check", "duplicate_check", "relationship_check"].includes(type)) config.column = column;
    if (threshold && type === "null_check") config.threshold = parseFloat(threshold);
    if (type === "range_check") {
      if (minValue) config.min_value = parseFloat(minValue);
      if (maxValue) config.max_value = parseFloat(maxValue);
    }
    if (type === "row_count") {
      if (minRows) config.min_rows = parseInt(minRows);
      if (maxRows) config.max_rows = parseInt(maxRows);
    }
    if (type === "relationship_check") {
      if (refTable) config.ref_table = refTable;
      if (refColumn) config.ref_column = refColumn;
    }
    if (type === "schema_check" && expectedColumns) {
      config.expected_columns = expectedColumns.split(",").map((c) => c.trim()).filter(Boolean);
    }
    if (type === "custom_sql" && query) config.query = query;

    try {
      await apiPost("/api/v1/tests", { name, description, type, severity, config, enabled: true, tags: [], profile }, token);
      onCreated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create test");
    } finally {
      setSubmitting(false);
    }
  };

  const showColumn = ["null_check", "range_check", "unique_check", "duplicate_check", "relationship_check"].includes(type);
  const showThreshold = type === "null_check";
  const showRangeMinMax = type === "range_check";
  const showRowCount = type === "row_count";
  const showRelationship = type === "relationship_check";
  const showExpectedColumns = type === "schema_check";
  const showQuery = type === "custom_sql";

  return (
    <div className={`rounded-xl border p-6 ${dark ? "bg-gray-900 border-gray-800" : "bg-white border-gray-200"}`}>
      <h2 className={`font-medium mb-4 ${dark ? "text-white" : "text-gray-900"}`}>Create Test</h2>
      <div className="grid grid-cols-5 gap-6">
        {/* Left: form */}
        <div className="col-span-3">
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Row 1: Name + Type + Severity */}
            <div className="grid grid-cols-3 gap-3">
              <div className="col-span-1">
                <label className={labelCls}>Name *</label>
                <input value={name} onChange={(e) => setName(e.target.value)} required placeholder="Customer Email Null Check" className={inputCls} />
              </div>
              <div>
                <label className={labelCls}>Type</label>
                <select value={type} onChange={(e) => setType(e.target.value)} className={inputCls}>
                  {TEST_TYPES.map((t) => <option key={t} value={t}>{t.replace(/_/g, " ")}</option>)}
                </select>
              </div>
              <div>
                <label className={labelCls}>Severity</label>
                <select value={severity} onChange={(e) => setSeverity(e.target.value)} className={inputCls}>
                  <option>LOW</option><option>MEDIUM</option><option>HIGH</option><option>CRITICAL</option>
                </select>
              </div>
            </div>

            {/* Row 2: Description + Profile */}
            <div className="grid grid-cols-3 gap-3">
              <div className="col-span-2">
                <label className={labelCls}>Description (optional)</label>
                <input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="What this test checks..." className={inputCls} />
              </div>
              <div>
                <label className={labelCls}>Profile</label>
                <select value={profile} onChange={(e) => setProfile(e.target.value)} className={inputCls}>
                  <option value="dev">dev</option>
                  <option value="staging">staging</option>
                  <option value="prod">prod</option>
                </select>
              </div>
            </div>

            {/* Row 3: Table + Column (conditional) */}
            {!showQuery && (
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className={labelCls}>Table *</label>
                  <input value={table} onChange={(e) => setTable(e.target.value)} required placeholder="customers" className={inputCls} />
                </div>
                {showColumn && (
                  <div>
                    <label className={labelCls}>Column</label>
                    <input value={column} onChange={(e) => setColumn(e.target.value)} placeholder="email" className={inputCls} />
                  </div>
                )}
              </div>
            )}

            {/* Type-specific fields */}
            {showThreshold && (
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className={labelCls}>Null Threshold (0–1)</label>
                  <input value={threshold} onChange={(e) => setThreshold(e.target.value)} type="number" step="0.01" min="0" max="1" placeholder="0.02 = allow 2% nulls" className={inputCls} />
                </div>
              </div>
            )}

            {showRangeMinMax && (
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className={labelCls}>Min Value</label>
                  <input value={minValue} onChange={(e) => setMinValue(e.target.value)} type="number" placeholder="0" className={inputCls} />
                </div>
                <div>
                  <label className={labelCls}>Max Value</label>
                  <input value={maxValue} onChange={(e) => setMaxValue(e.target.value)} type="number" placeholder="1000" className={inputCls} />
                </div>
              </div>
            )}

            {showRowCount && (
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className={labelCls}>Min Rows</label>
                  <input value={minRows} onChange={(e) => setMinRows(e.target.value)} type="number" min="0" placeholder="1" className={inputCls} />
                </div>
                <div>
                  <label className={labelCls}>Max Rows (optional)</label>
                  <input value={maxRows} onChange={(e) => setMaxRows(e.target.value)} type="number" min="0" placeholder="leave blank for no max" className={inputCls} />
                </div>
              </div>
            )}

            {showRelationship && (
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className={labelCls}>Reference Table</label>
                  <input value={refTable} onChange={(e) => setRefTable(e.target.value)} placeholder="orders" className={inputCls} />
                </div>
                <div>
                  <label className={labelCls}>Reference Column</label>
                  <input value={refColumn} onChange={(e) => setRefColumn(e.target.value)} placeholder="customer_id" className={inputCls} />
                </div>
              </div>
            )}

            {showExpectedColumns && (
              <div>
                <label className={labelCls}>Expected Columns (comma-separated)</label>
                <input value={expectedColumns} onChange={(e) => setExpectedColumns(e.target.value)} placeholder="id, name, email, created_at" className={inputCls} />
              </div>
            )}

            {showQuery && (
              <div>
                <label className={labelCls}>SQL Query *</label>
                <textarea
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  rows={6}
                  required
                  placeholder={"SELECT COUNT(*) AS result\nFROM customers\nWHERE status NOT IN ('active', 'inactive')"}
                  className={`${inputCls} font-mono resize-y`}
                />
                <p className={`text-xs mt-1 ${dark ? "text-gray-600" : "text-gray-400"}`}>Query must return a single numeric value. Non-zero = test fails.</p>
              </div>
            )}

            <div className="flex items-center gap-3 pt-1">
              <button type="submit" disabled={submitting} className="px-4 py-2 bg-green-600 hover:bg-green-500 disabled:bg-green-800 text-white text-sm rounded-lg transition-colors">
                {submitting ? "Creating..." : "Create Test"}
              </button>
              {error && <span className="text-red-400 text-sm">{error}</span>}
            </div>
          </form>
        </div>

        {/* Right: live YAML preview */}
        <div className="col-span-2">
          <p className={`text-xs font-medium mb-2 ${dark ? "text-gray-400" : "text-gray-600"}`}>YAML Preview</p>
          <pre className={`rounded-lg p-4 font-mono text-xs leading-relaxed overflow-auto h-[calc(100%-2rem)] min-h-[200px] ${
            dark ? "bg-gray-950 text-gray-300 border border-gray-800" : "bg-gray-50 text-gray-700 border border-gray-200"
          }`}>
            {buildYamlPreview(formState)}
          </pre>
        </div>
      </div>
    </div>
  );
}
