"use client";

import { Fragment, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useTheme } from "@/lib/theme";
import { useRunContext } from "@/lib/run-context";
import { apiGet, apiGetText, apiDelete, apiPost, apiPut } from "@/lib/api";
import { SeverityBadge, TypePill } from "@/components/StatusBadge";
import {
  TYPE_LABELS,
  formatConfigKey,
  BRAND_NAVY,
  NEUTRAL_SCALE,
  STATUS_PALETTE,
} from "@/lib/constants";
import type { TestDefinition, ProfileOut } from "@/lib/types";

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
  const { selectedProfile, profiles } = useRunContext();
  const dark = theme === "dark";
  const palette = dark ? NEUTRAL_SCALE.dark : NEUTRAL_SCALE.light;
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
        <p className="text-body" style={{ color: palette.textSecondary }}>Loading tests…</p>
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
          <h1 className="text-heading" style={{ color: palette.textPrimary }}>Test Definitions</h1>
          <p className="text-body mt-0.5" style={{ color: palette.textSecondary }}>
            {tests.length} tests · {enabledCount} enabled · {disabledCount} disabled
          </p>
        </div>
        <div className="flex items-center gap-3">
          {/* Tabs */}
          <div
            className="flex items-center p-0.5 gap-0.5"
            style={{
              backgroundColor: palette.surfaceBg,
              border: `1px solid ${palette.borderSubtle}`,
              borderRadius: "8px",
            }}
          >
            {([["table", "Tests"], ["yaml", "YAML Editor"]] as ["table" | "yaml", string][]).map(([key, label]) => {
              const active = activeTab === key;
              return (
                <button
                  key={key}
                  onClick={() => setActiveTab(key)}
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
          {activeTab === "table" && (
            <button
              onClick={() => setShowCreate(!showCreate)}
              className="px-4 text-body font-medium transition-colors"
              style={{
                height: "36px",
                backgroundColor: BRAND_NAVY,
                color: "#FFFFFF",
                border: "none",
                borderRadius: "8px",
                cursor: "pointer",
              }}
            >
              {showCreate ? "Cancel" : "+ New Test"}
            </button>
          )}
        </div>
      </div>

      {/* Create form */}
      {showCreate && activeTab === "table" && (
        <CreateTestForm token={token!} dark={dark} initialProfile={selectedProfile ?? "dev"} profiles={profiles} onCreated={() => { setShowCreate(false); fetchTests(); }} />
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
  const palette = dark ? NEUTRAL_SCALE.dark : NEUTRAL_SCALE.light;
  const [expandedId, setExpandedId] = useState<number | null>(null);

  return (
    <div
      className="overflow-hidden"
      style={{
        backgroundColor: palette.surfaceElevated,
        border: `1px solid ${palette.borderSubtle}`,
        borderRadius: "8px",
      }}
    >
      <table className="w-full text-sm">
        <thead style={{ backgroundColor: palette.surfaceBg }}>
          <tr style={{ color: palette.textSecondary }}>
            <th className="px-2 py-3" style={{ width: "24px" }}></th>
            <th className="px-4 py-3 text-left text-caption">Name</th>
            <th className="px-4 py-3 text-left text-caption">Type</th>
            <th className="px-4 py-3 text-left text-caption">Table</th>
            <th className="px-4 py-3 text-left text-caption">Column(s)</th>
            <th className="px-4 py-3 text-left text-caption">Severity</th>
            <th className="px-4 py-3 text-left text-caption">Enabled</th>
            <th className="px-4 py-3 text-left text-caption">Actions</th>
          </tr>
        </thead>
        <tbody style={{ borderTop: `1px solid ${palette.borderSubtle}` }}>
          {tests.map((t) => {
            const isExpanded = expandedId === t.id;
            const configEntries = Object.entries(t.config || {}).filter(
              ([k]) => !["table", "column", "columns", "query"].includes(k)
            );
            const isCustomSql = t.type === "custom_sql";
            const sqlQuery = isCustomSql ? (t.config?.query as string | undefined) : undefined;
            return (
              <Fragment key={t.id}>
                <tr
                  className="transition-colors cursor-pointer"
                  style={{ height: "40px", opacity: t.enabled ? 1 : 0.5, borderTop: `1px solid ${palette.borderSubtle}` }}
                  onClick={() => setExpandedId(isExpanded ? null : t.id)}
                  onMouseEnter={(e) => ((e.currentTarget as HTMLTableRowElement).style.backgroundColor = dark ? "rgba(232,236,243,0.04)" : "rgba(14,22,38,0.04)")}
                  onMouseLeave={(e) => ((e.currentTarget as HTMLTableRowElement).style.backgroundColor = "transparent")}
                >
                  <td
                    className="px-2 py-3 text-caption"
                    style={{
                      color: palette.textSecondary,
                      textTransform: "none",
                      letterSpacing: "0",
                    }}
                  >
                    {(configEntries.length > 0 || (isCustomSql && sqlQuery)) ? (isExpanded ? "▼" : "▶") : ""}
                  </td>

                  {/* Name — verbatim per D-10; primary text neutral; JetBrains Mono; Body size */}
                  <td className="px-4 py-3 max-w-xs">
                    <div
                      className="line-clamp-2 text-body"
                      style={{
                        fontFamily: "var(--font-jetbrains-mono)",
                        color: palette.textPrimary,
                      }}
                      title={t.name}
                    >
                      {t.name}
                    </div>
                    {t.description && (
                      <div
                        className="text-caption mt-0.5 line-clamp-1"
                        style={{
                          color: palette.textSecondary,
                          textTransform: "none",
                          letterSpacing: "0",
                        }}
                        title={t.description}
                      >
                        {t.description}
                      </div>
                    )}
                  </td>

                  {/* Type — TypePill */}
                  <td className="px-4 py-3"><TypePill type={t.type} dark={dark} /></td>

                  {/* Table — mono, verbatim per D-10 */}
                  <td
                    className="px-4 py-3 text-caption"
                    style={{
                      fontFamily: "var(--font-jetbrains-mono)",
                      color: palette.textSecondary,
                      textTransform: "none",
                      letterSpacing: "0",
                    }}
                  >
                    {extractTable(t)}
                  </td>

                  {/* Column(s) */}
                  <td
                    className="px-4 py-3 text-caption"
                    style={{
                      fontFamily: "var(--font-jetbrains-mono)",
                      color: palette.textSecondary,
                      textTransform: "none",
                      letterSpacing: "0",
                    }}
                  >
                    {extractColumns(t)}
                  </td>

                  <td className="px-4 py-3"><SeverityBadge severity={t.severity} /></td>

                  {/* Enabled toggle — teal-when-on */}
                  <td className="px-4 py-3">
                    <button
                      onClick={(e) => { e.stopPropagation(); onToggle(t); }}
                      className="relative transition-colors"
                      style={{
                        width: "36px",
                        height: "20px",
                        borderRadius: "9999px",
                        backgroundColor: t.enabled
                          ? STATUS_PALETTE.PASSED
                          : (dark ? "#374151" : "#D1D5DB"),
                        border: "none",
                        cursor: "pointer",
                      }}
                      aria-label={t.enabled ? "Disable test" : "Enable test"}
                    >
                      <span
                        style={{
                          position: "absolute",
                          top: "2px",
                          left: t.enabled ? "18px" : "2px",
                          width: "16px",
                          height: "16px",
                          borderRadius: "9999px",
                          backgroundColor: "#FFFFFF",
                          transition: "left 120ms ease-in-out",
                        }}
                      />
                    </button>
                  </td>

                  {/* Actions */}
                  <td className="px-4 py-3">
                    <button
                      onClick={(e) => { e.stopPropagation(); onDelete(t.id, t.name); }}
                      className="text-body font-medium transition-colors"
                      style={{ color: STATUS_PALETTE.FAILED }}
                      onMouseEnter={(e) => ((e.currentTarget as HTMLButtonElement).style.opacity = "0.7")}
                      onMouseLeave={(e) => ((e.currentTarget as HTMLButtonElement).style.opacity = "1")}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
                {isExpanded && (configEntries.length > 0 || (isCustomSql && sqlQuery)) && (
                  <tr style={{ borderTop: `1px solid ${palette.borderSubtle}` }}>
                    <td
                      colSpan={8}
                      className="px-12 py-3"
                      style={{ backgroundColor: palette.surfaceBg }}
                    >
                      {isCustomSql && (
                        <div
                          className="mt-3 overflow-hidden"
                          style={{
                            backgroundColor: palette.surfaceBg,
                            border: `1px solid ${palette.borderSubtle}`,
                            borderRadius: "8px",
                          }}
                        >
                          <div
                            className="px-4 py-2 text-caption"
                            style={{
                              borderBottom: `1px solid ${palette.borderSubtle}`,
                              color: palette.textSecondary,
                              fontFamily: "var(--font-jetbrains-mono)",
                              textTransform: "none",
                              letterSpacing: "0",
                            }}
                          >
                            query
                          </div>
                          <pre
                            className="px-4 py-3 font-mono text-xs overflow-x-auto whitespace-pre max-h-80 overflow-y-auto"
                            style={{ color: palette.textPrimary }}
                          >
                            <code>{sqlQuery || "(no query defined)"}</code>
                          </pre>
                        </div>
                      )}
                      <div className="grid grid-cols-4 gap-3">
                        <div
                          className="px-3 py-2"
                          style={{
                            backgroundColor: palette.surfaceElevated,
                            border: `1px solid ${palette.borderSubtle}`,
                            borderRadius: "8px",
                          }}
                        >
                          <p className="text-caption" style={{ color: palette.textSecondary }}>profile</p>
                          <p className="text-body font-medium mt-0.5" style={{ color: palette.textPrimary }}>{t.profile}</p>
                        </div>
                        {t.tags.length > 0 && (
                          <div
                            className="px-3 py-2"
                            style={{
                              backgroundColor: palette.surfaceElevated,
                              border: `1px solid ${palette.borderSubtle}`,
                              borderRadius: "8px",
                            }}
                          >
                            <p className="text-caption" style={{ color: palette.textSecondary }}>tags</p>
                            <div className="flex flex-wrap gap-1 mt-1">
                              {t.tags.map((tag) => (
                                <span
                                  key={tag}
                                  className="text-caption px-1.5 py-0.5"
                                  style={{
                                    backgroundColor: palette.surfaceBg,
                                    color: palette.textSecondary,
                                    borderRadius: "4px",
                                    textTransform: "none",
                                    letterSpacing: "0",
                                  }}
                                >
                                  {tag}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                        {configEntries.map(([key, val]) => (
                          <div
                            key={key}
                            className="px-3 py-2"
                            style={{
                              backgroundColor: palette.surfaceElevated,
                              border: `1px solid ${palette.borderSubtle}`,
                              borderRadius: "8px",
                            }}
                          >
                            <p className="text-caption" style={{ color: palette.textSecondary }}>{formatConfigKey(key)}</p>
                            <p
                              className="text-body font-medium mt-0.5 truncate"
                              style={{ color: palette.textPrimary }}
                              title={typeof val === "object" ? JSON.stringify(val) : String(val)}
                            >
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
        <div
          className="px-6 py-12 text-center"
          style={{ color: palette.textSecondary }}
        >
          <p
            className="text-heading"
            style={{ color: palette.textPrimary }}
          >
            No tests configured yet
          </p>
          <p className="text-body mt-2">
            Add a test in the YAML editor to start checking your data.
          </p>
        </div>
      )}
    </div>
  );
}

/* ── YAML Editor ──────────────────────────────────────────────────────────── */
function YamlEditor({ token, dark, onSaved }: { token: string; dark: boolean; onSaved: () => void }) {
  const palette = dark ? NEUTRAL_SCALE.dark : NEUTRAL_SCALE.light;
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
        <p className="text-body" style={{ color: palette.textSecondary }}>Loading YAML…</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Warning banner */}
      <div
        className="px-4 py-3 text-body flex items-center gap-2"
        style={{
          backgroundColor: `${STATUS_PALETTE.ERROR}1A`,
          border: `1px solid ${STATUS_PALETTE.ERROR}40`,
          borderRadius: "8px",
          color: STATUS_PALETTE.ERROR,
        }}
      >
        <span aria-hidden="true">⚠</span>
        <span>Saving will sync all test definitions with the database. Tests removed from the YAML will be deleted.</span>
      </div>

      {/* Editor */}
      <div
        className="overflow-hidden"
        style={{
          backgroundColor: palette.surfaceElevated,
          border: `1px solid ${palette.borderSubtle}`,
          borderRadius: "8px",
        }}
      >
        <div
          className="px-4 py-3 flex items-center justify-between"
          style={{ borderBottom: `1px solid ${palette.borderSubtle}` }}
        >
          <p
            className="text-body"
            style={{
              fontFamily: "var(--font-jetbrains-mono)",
              color: palette.textPrimary,
            }}
          >
            test_definitions.yaml
          </p>
          <div className="flex items-center gap-3">
            {feedback && (
              <span
                className="text-caption"
                style={{
                  color: feedback.type === "success" ? STATUS_PALETTE.PASSED : STATUS_PALETTE.FAILED,
                  textTransform: "none",
                  letterSpacing: "0",
                }}
              >
                {feedback.message}
              </span>
            )}
            <button
              onClick={handleSave}
              disabled={saving}
              className="text-body font-medium px-4 transition-colors"
              style={{
                height: "36px",
                backgroundColor: BRAND_NAVY,
                color: "#FFFFFF",
                border: "none",
                borderRadius: "8px",
                cursor: saving ? "not-allowed" : "pointer",
                opacity: saving ? 0.5 : 1,
              }}
            >
              {saving ? "Saving…" : "Save & Sync"}
            </button>
          </div>
        </div>
        <textarea
          value={yamlContent}
          onChange={(e) => { setYamlContent(e.target.value); setFeedback(null); }}
          spellCheck={false}
          className="w-full h-[600px] px-6 py-4 text-body resize-none focus:outline-none"
          style={{
            fontFamily: "var(--font-jetbrains-mono)",
            backgroundColor: palette.surfaceBg,
            color: palette.textPrimary,
            border: "none",
          }}
          placeholder="# Paste or edit your YAML test definitions here…"
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

/* ── Page-local form primitives — single source of truth for input/label/select styling.
   Per CONVENTIONS.md §"Module Design": page-local sub-components stay in the page file.
   Created in Plan 04 to eliminate the bulk-edit partial-coverage risk of inlining
   style props across ~15 inputs + ~15 labels + selects (WARNING 1 from planner revision). */

function TestFormInput({
  dark,
  ...rest
}: React.InputHTMLAttributes<HTMLInputElement> & { dark: boolean }) {
  const palette = dark ? NEUTRAL_SCALE.dark : NEUTRAL_SCALE.light;
  return (
    <input
      {...rest}
      className={`w-full px-3 text-body focus:outline-none transition-colors ${rest.className ?? ""}`}
      style={{
        height: "36px",
        backgroundColor: dark ? palette.surfaceBg : palette.surfaceElevated,
        border: `1px solid ${palette.borderSubtle}`,
        borderRadius: "8px",
        color: palette.textPrimary,
        ...(rest.style ?? {}),
      }}
    />
  );
}

function TestFormSelect({
  dark,
  children,
  ...rest
}: React.SelectHTMLAttributes<HTMLSelectElement> & { dark: boolean }) {
  const palette = dark ? NEUTRAL_SCALE.dark : NEUTRAL_SCALE.light;
  return (
    <select
      {...rest}
      className={`w-full px-3 text-body focus:outline-none transition-colors ${rest.className ?? ""}`}
      style={{
        height: "36px",
        backgroundColor: dark ? palette.surfaceBg : palette.surfaceElevated,
        border: `1px solid ${palette.borderSubtle}`,
        borderRadius: "8px",
        color: palette.textPrimary,
        ...(rest.style ?? {}),
      }}
    >
      {children}
    </select>
  );
}

function TestFormLabel({
  dark,
  children,
  ...rest
}: React.LabelHTMLAttributes<HTMLLabelElement> & { dark: boolean }) {
  const palette = dark ? NEUTRAL_SCALE.dark : NEUTRAL_SCALE.light;
  return (
    <label
      {...rest}
      className={`block text-caption mb-1 ${rest.className ?? ""}`}
      style={{
        color: palette.textSecondary,
        textTransform: "none",
        letterSpacing: "0",
        fontWeight: 500,
        ...(rest.style ?? {}),
      }}
    >
      {children}
    </label>
  );
}

/* ── Create Form ──────────────────────────────────────────────────────────── */
function CreateTestForm({ token, dark, initialProfile, profiles, onCreated }: { token: string; dark: boolean; initialProfile: string; profiles: ProfileOut[]; onCreated: () => void }) {
  const palette = dark ? NEUTRAL_SCALE.dark : NEUTRAL_SCALE.light;
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [type, setType] = useState("null_check");
  const [severity, setSeverity] = useState("MEDIUM");
  const [profile, setProfile] = useState(initialProfile);
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
    <div
      className="p-6"
      style={{
        backgroundColor: palette.surfaceElevated,
        border: `1px solid ${palette.borderSubtle}`,
        borderRadius: "8px",
      }}
    >
      <h2 className="text-heading mb-4" style={{ color: palette.textPrimary }}>Create Test</h2>
      <div className="grid grid-cols-5 gap-6">
        {/* Left: form */}
        <div className="col-span-3">
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Row 1: Name + Type + Severity */}
            <div className="grid grid-cols-3 gap-3">
              <div className="col-span-1">
                <TestFormLabel dark={dark}>Name *</TestFormLabel>
                <TestFormInput dark={dark} value={name} onChange={(e) => setName(e.target.value)} required placeholder="Customer Email Null Check" />
              </div>
              <div>
                <TestFormLabel dark={dark}>Type</TestFormLabel>
                <TestFormSelect dark={dark} value={type} onChange={(e) => setType(e.target.value)}>
                  {TEST_TYPES.map((t) => <option key={t} value={t}>{TYPE_LABELS[t] ?? t}</option>)}
                </TestFormSelect>
              </div>
              <div>
                <TestFormLabel dark={dark}>Severity</TestFormLabel>
                <TestFormSelect dark={dark} value={severity} onChange={(e) => setSeverity(e.target.value)}>
                  <option>LOW</option><option>MEDIUM</option><option>HIGH</option><option>CRITICAL</option>
                </TestFormSelect>
              </div>
            </div>

            {/* Row 2: Description + Profile */}
            <div className="grid grid-cols-3 gap-3">
              <div className="col-span-2">
                <TestFormLabel dark={dark}>Description (optional)</TestFormLabel>
                <TestFormInput dark={dark} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="What this test checks…" />
              </div>
              <div>
                <TestFormLabel dark={dark}>Profile</TestFormLabel>
                <TestFormSelect dark={dark} value={profile} onChange={(e) => setProfile(e.target.value)}>
                  {profiles.length > 0
                    ? profiles.map((p) => <option key={p.name} value={p.name}>{p.name}</option>)
                    : [<option key="dev" value="dev">dev</option>, <option key="staging" value="staging">staging</option>, <option key="prod" value="prod">prod</option>]
                  }
                </TestFormSelect>
              </div>
            </div>

            {/* Row 3: Table + Column (conditional) */}
            {!showQuery && (
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <TestFormLabel dark={dark}>Table *</TestFormLabel>
                  <TestFormInput dark={dark} value={table} onChange={(e) => setTable(e.target.value)} required placeholder="customers" />
                </div>
                {showColumn && (
                  <div>
                    <TestFormLabel dark={dark}>Column</TestFormLabel>
                    <TestFormInput dark={dark} value={column} onChange={(e) => setColumn(e.target.value)} placeholder="email" />
                  </div>
                )}
              </div>
            )}

            {/* Type-specific fields */}
            {showThreshold && (
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <TestFormLabel dark={dark}>Null Threshold (0–1)</TestFormLabel>
                  <TestFormInput dark={dark} value={threshold} onChange={(e) => setThreshold(e.target.value)} type="number" step="0.01" min="0" max="1" placeholder="0.02 = allow 2% nulls" />
                </div>
              </div>
            )}

            {showRangeMinMax && (
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <TestFormLabel dark={dark}>Min Value</TestFormLabel>
                  <TestFormInput dark={dark} value={minValue} onChange={(e) => setMinValue(e.target.value)} type="number" placeholder="0" />
                </div>
                <div>
                  <TestFormLabel dark={dark}>Max Value</TestFormLabel>
                  <TestFormInput dark={dark} value={maxValue} onChange={(e) => setMaxValue(e.target.value)} type="number" placeholder="1000" />
                </div>
              </div>
            )}

            {showRowCount && (
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <TestFormLabel dark={dark}>Min Rows</TestFormLabel>
                  <TestFormInput dark={dark} value={minRows} onChange={(e) => setMinRows(e.target.value)} type="number" min="0" placeholder="1" />
                </div>
                <div>
                  <TestFormLabel dark={dark}>Max Rows (optional)</TestFormLabel>
                  <TestFormInput dark={dark} value={maxRows} onChange={(e) => setMaxRows(e.target.value)} type="number" min="0" placeholder="leave blank for no max" />
                </div>
              </div>
            )}

            {showRelationship && (
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <TestFormLabel dark={dark}>Reference Table</TestFormLabel>
                  <TestFormInput dark={dark} value={refTable} onChange={(e) => setRefTable(e.target.value)} placeholder="orders" />
                </div>
                <div>
                  <TestFormLabel dark={dark}>Reference Column</TestFormLabel>
                  <TestFormInput dark={dark} value={refColumn} onChange={(e) => setRefColumn(e.target.value)} placeholder="customer_id" />
                </div>
              </div>
            )}

            {showExpectedColumns && (
              <div>
                <TestFormLabel dark={dark}>Expected Columns (comma-separated)</TestFormLabel>
                <TestFormInput dark={dark} value={expectedColumns} onChange={(e) => setExpectedColumns(e.target.value)} placeholder="id, name, email, created_at" />
              </div>
            )}

            {showQuery && (
              <div>
                <TestFormLabel dark={dark}>SQL Query *</TestFormLabel>
                <textarea
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  rows={6}
                  required
                  placeholder={"SELECT COUNT(*) AS result\nFROM customers\nWHERE status NOT IN ('active', 'inactive')"}
                  className="w-full px-3 py-2 text-body resize-y focus:outline-none"
                  style={{
                    fontFamily: "var(--font-jetbrains-mono)",
                    backgroundColor: dark ? palette.surfaceBg : palette.surfaceElevated,
                    border: `1px solid ${palette.borderSubtle}`,
                    borderRadius: "8px",
                    color: palette.textPrimary,
                  }}
                />
                <p
                  className="text-caption mt-1"
                  style={{
                    color: palette.textSecondary,
                    textTransform: "none",
                    letterSpacing: "0",
                  }}
                >
                  Query must return a single numeric value. Non-zero = test fails.
                </p>
              </div>
            )}

            <div className="flex items-center gap-3 pt-1">
              <button
                type="submit"
                disabled={submitting}
                className="px-4 text-body font-medium transition-colors"
                style={{
                  height: "36px",
                  backgroundColor: BRAND_NAVY,
                  color: "#FFFFFF",
                  border: "none",
                  borderRadius: "8px",
                  cursor: submitting ? "not-allowed" : "pointer",
                  opacity: submitting ? 0.5 : 1,
                }}
              >
                {submitting ? "Creating…" : "Create test"}
              </button>
              {error && (
                <span
                  className="text-body"
                  style={{ color: STATUS_PALETTE.FAILED }}
                >
                  {error}
                </span>
              )}
            </div>
          </form>
        </div>

        {/* Right: live YAML preview */}
        <div className="col-span-2">
          <p
            className="text-caption mb-2"
            style={{
              color: palette.textSecondary,
              textTransform: "none",
              letterSpacing: "0",
              fontWeight: 500,
            }}
          >
            YAML Preview
          </p>
          <pre
            className="p-4 font-mono text-xs leading-relaxed overflow-auto h-[calc(100%-2rem)] min-h-[200px]"
            style={{
              backgroundColor: palette.surfaceBg,
              color: palette.textPrimary,
              border: `1px solid ${palette.borderSubtle}`,
              borderRadius: "8px",
            }}
          >
            {buildYamlPreview(formState)}
          </pre>
        </div>
      </div>
    </div>
  );
}
