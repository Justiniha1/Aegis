"use client";

import { useState } from "react";
import { useTheme } from "@/lib/theme";
import { useAuth } from "@/lib/auth";
import { useRunContext } from "@/lib/run-context";
import { createProfile, deleteProfile } from "@/lib/api";
import { NEUTRAL_SCALE, BRAND_TEAL, STATUS_PALETTE } from "@/lib/constants";

const DB_TYPES = ["postgresql", "mysql", "sqlite", "mssql"] as const;

const EMPTY_FORM = { name: "", connection_url: "", db_type: "postgresql" };

export default function SettingsPage() {
  const { theme, setTheme } = useTheme();
  const { token } = useAuth();
  const { profiles, selectedProfile, setSelectedProfile, refreshProfiles, profilesLoading, profilesError } = useRunContext();
  const dark = theme === "dark";
  const palette = dark ? NEUTRAL_SCALE.dark : NEUTRAL_SCALE.light;

  const [showAddForm, setShowAddForm] = useState(false);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [adding, setAdding] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!token) return;
    setAdding(true);
    setFormError(null);
    try {
      await createProfile(form, token);
      setForm({ ...EMPTY_FORM });
      setShowAddForm(false);
      refreshProfiles();
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : "Failed to add profile — check your connection URL and try again.");
    } finally {
      setAdding(false);
    }
  }

  async function handleDelete(id: number) {
    if (!token) return;
    setDeletingId(id);
    try {
      await deleteProfile(id, token);
      refreshProfiles();
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : "Failed to remove profile — try again.");
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="max-w-2xl mx-auto space-y-8">
      <div>
        <h1
          className="text-heading"
          style={{ color: palette.textPrimary }}
        >
          Settings
        </h1>
        <p
          className="text-body mt-1"
          style={{ color: palette.textSecondary }}
        >
          Customize your dashboard experience
        </p>
      </div>

      {/* Active Environment */}
      <section
        className="p-6"
        style={{
          backgroundColor: palette.surfaceElevated,
          border: `1px solid ${palette.borderSubtle}`,
          borderRadius: "8px",
        }}
      >
        <h2
          className="text-heading mb-1"
          style={{ color: palette.textPrimary }}
        >
          Active Environment
        </h2>
        <p
          className="text-body mb-5"
          style={{ color: palette.textSecondary }}
        >
          "Run all" runs tests tagged to this profile.
        </p>

        {profilesLoading ? (
          <p className="text-body" style={{ color: palette.textSecondary }}>
            Loading profiles…
          </p>
        ) : profilesError ? (
          <p className="text-body" style={{ color: STATUS_PALETTE.FAILED }}>
            Could not load profiles — check your connection and reload.
          </p>
        ) : profiles.length === 0 ? (
          <p className="text-body" style={{ color: palette.textSecondary }}>
            No environments found — add a profile to get started.
          </p>
        ) : (
          <div className="space-y-1">
            {profiles.map((p) => {
              const active = selectedProfile === p.name;
              return (
                <button
                  key={p.name}
                  type="button"
                  onClick={() => setSelectedProfile(p.name)}
                  className="w-full text-left flex items-center gap-3 px-3 py-2.5 transition-all"
                  style={{
                    borderRadius: "6px",
                    backgroundColor: active ? `${BRAND_TEAL}0F` : "transparent",
                    opacity: active ? 1 : 0.75,
                    cursor: "pointer",
                    border: "none",
                  }}
                  onMouseEnter={(e) => {
                    if (!active) (e.currentTarget as HTMLButtonElement).style.opacity = "0.90";
                  }}
                  onMouseLeave={(e) => {
                    if (!active) (e.currentTarget as HTMLButtonElement).style.opacity = "0.75";
                  }}
                >
                  <div
                    style={{
                      width: "7px",
                      height: "7px",
                      borderRadius: "9999px",
                      backgroundColor: active ? BRAND_TEAL : palette.textSecondary,
                      flexShrink: 0,
                      transition: "background-color 120ms",
                    }}
                  />
                  <span
                    className="text-body"
                    style={{
                      fontFamily: "var(--font-jetbrains-mono)",
                      color: active ? palette.textPrimary : palette.textSecondary,
                      fontWeight: active ? 500 : 400,
                    }}
                  >
                    {p.name}
                  </span>
                </button>
              );
            })}
          </div>
        )}
      </section>

      {/* Connection Profiles */}
      <section
        className="p-6"
        style={{
          backgroundColor: palette.surfaceElevated,
          border: `1px solid ${palette.borderSubtle}`,
          borderRadius: "8px",
        }}
      >
        <h2 className="text-heading mb-1" style={{ color: palette.textPrimary }}>
          Connection Profiles
        </h2>
        <p className="text-body mb-5" style={{ color: palette.textSecondary }}>
          Database connections used by the engine. Connection URLs are encrypted at rest.
        </p>

        {profiles.length === 0 ? (
          <p className="text-body" style={{ color: palette.textSecondary }}>
            No database connections configured yet.
          </p>
        ) : (
          <div className="space-y-1 mb-4">
            {profiles.map((p) => (
              <div
                key={p.id}
                className="flex items-center justify-between px-3 py-2.5"
                style={{
                  borderRadius: "6px",
                  backgroundColor: palette.surfaceBg,
                  border: `1px solid ${palette.borderSubtle}`,
                }}
              >
                <div className="flex items-center gap-3">
                  <span
                    className="text-body"
                    style={{
                      fontFamily: "var(--font-jetbrains-mono)",
                      color: palette.textPrimary,
                      fontWeight: 500,
                    }}
                  >
                    {p.name}
                  </span>
                  <span
                    className="text-[10px] px-1.5 py-0.5 rounded font-semibold uppercase"
                    style={{
                      backgroundColor: `${palette.borderSubtle}`,
                      color: palette.textSecondary,
                    }}
                  >
                    {p.db_type}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => handleDelete(p.id)}
                  disabled={deletingId === p.id}
                  className="text-caption"
                  style={{
                    color: STATUS_PALETTE.FAILED,
                    background: "none",
                    border: "none",
                    cursor: deletingId === p.id ? "not-allowed" : "pointer",
                    opacity: deletingId === p.id ? 0.5 : 1,
                    padding: "2px 6px",
                    borderRadius: "4px",
                  }}
                >
                  {deletingId === p.id ? "Removing…" : "Remove"}
                </button>
              </div>
            ))}
          </div>
        )}

        {!showAddForm ? (
          <button
            type="button"
            onClick={() => setShowAddForm(true)}
            className="text-body"
            style={{
              color: BRAND_TEAL,
              background: "none",
              border: `1px solid ${BRAND_TEAL}4D`,
              borderRadius: "6px",
              padding: "6px 14px",
              cursor: "pointer",
            }}
          >
            + Add connection
          </button>
        ) : (
          <form onSubmit={handleAdd} className="space-y-3 mt-2">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-caption block mb-1" style={{ color: palette.textSecondary, textTransform: "none", letterSpacing: 0 }}>
                  Profile name
                </label>
                <input
                  required
                  value={form.name}
                  onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                  placeholder="e.g. production"
                  style={{
                    width: "100%",
                    padding: "7px 10px",
                    borderRadius: "6px",
                    border: `1px solid ${palette.borderSubtle}`,
                    backgroundColor: palette.surfaceBg,
                    color: palette.textPrimary,
                    fontFamily: "var(--font-jetbrains-mono)",
                    fontSize: "13px",
                    outline: "none",
                  }}
                />
              </div>
              <div>
                <label className="text-caption block mb-1" style={{ color: palette.textSecondary, textTransform: "none", letterSpacing: 0 }}>
                  Database type
                </label>
                <select
                  value={form.db_type}
                  onChange={(e) => setForm((f) => ({ ...f, db_type: e.target.value }))}
                  style={{
                    width: "100%",
                    padding: "7px 10px",
                    borderRadius: "6px",
                    border: `1px solid ${palette.borderSubtle}`,
                    backgroundColor: palette.surfaceBg,
                    color: palette.textPrimary,
                    fontSize: "13px",
                    outline: "none",
                  }}
                >
                  {DB_TYPES.map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </div>
            </div>
            <div>
              <label className="text-caption block mb-1" style={{ color: palette.textSecondary, textTransform: "none", letterSpacing: 0 }}>
                Connection URL
              </label>
              <input
                required
                type="password"
                value={form.connection_url}
                onChange={(e) => setForm((f) => ({ ...f, connection_url: e.target.value }))}
                placeholder="postgresql://user:pass@host:5432/db"
                style={{
                  width: "100%",
                  padding: "7px 10px",
                  borderRadius: "6px",
                  border: `1px solid ${palette.borderSubtle}`,
                  backgroundColor: palette.surfaceBg,
                  color: palette.textPrimary,
                  fontFamily: "var(--font-jetbrains-mono)",
                  fontSize: "13px",
                  outline: "none",
                }}
              />
            </div>
            {formError && (
              <p className="text-caption" style={{ color: STATUS_PALETTE.FAILED, textTransform: "none", letterSpacing: 0 }}>
                {formError}
              </p>
            )}
            <div className="flex gap-2">
              <button
                type="submit"
                disabled={adding}
                style={{
                  padding: "6px 16px",
                  borderRadius: "6px",
                  backgroundColor: BRAND_TEAL,
                  color: "#fff",
                  border: "none",
                  cursor: adding ? "not-allowed" : "pointer",
                  opacity: adding ? 0.6 : 1,
                  fontSize: "13px",
                  fontWeight: 500,
                }}
              >
                {adding ? "Saving changes…" : "Save Changes"}
              </button>
              <button
                type="button"
                onClick={() => { setShowAddForm(false); setForm({ ...EMPTY_FORM }); setFormError(null); }}
                style={{
                  padding: "6px 16px",
                  borderRadius: "6px",
                  backgroundColor: "transparent",
                  color: palette.textSecondary,
                  border: `1px solid ${palette.borderSubtle}`,
                  cursor: "pointer",
                  fontSize: "13px",
                }}
              >
                Cancel
              </button>
            </div>
          </form>
        )}
      </section>

      {/* Appearance */}
      <section
        className="p-6"
        style={{
          backgroundColor: palette.surfaceElevated,
          border: `1px solid ${palette.borderSubtle}`,
          borderRadius: "8px",
        }}
      >
        <h2
          className="text-heading mb-1"
          style={{ color: palette.textPrimary }}
        >
          Appearance
        </h2>
        <p
          className="text-body mb-5"
          style={{ color: palette.textSecondary }}
        >
          Choose how the dashboard looks
        </p>

        <div className="grid grid-cols-2 gap-4">
          {/* Dark mode card */}
          <button
            onClick={() => setTheme("dark")}
            className="p-4 transition-all text-left"
            style={{
              backgroundColor: palette.surfaceElevated,
              border: `2px solid ${theme === "dark" ? BRAND_TEAL : palette.borderSubtle}`,
              borderRadius: "8px",
              cursor: "pointer",
            }}
          >
            <div
              className="p-3 mb-3"
              style={{
                backgroundColor: "#0B1220",
                border: `1px solid #1E2A40`,
                borderRadius: "6px",
              }}
            >
              <div className="flex gap-2 mb-2">
                <div className="w-8 h-2 rounded" style={{ backgroundColor: "#1E2A40" }} />
                <div className="w-12 h-2 rounded" style={{ backgroundColor: "#1E2A40" }} />
              </div>
              <div className="space-y-1.5">
                <div className="h-2 rounded w-3/4" style={{ backgroundColor: `${STATUS_PALETTE.PASSED}66` }} />
                <div className="h-2 rounded w-1/2" style={{ backgroundColor: `${STATUS_PALETTE.FAILED}66` }} />
                <div className="h-2 rounded w-2/3" style={{ backgroundColor: `${STATUS_PALETTE.ERROR}66` }} />
              </div>
            </div>
            <p
              className="text-body font-medium"
              style={{ color: palette.textPrimary }}
            >
              Dark
            </p>
            <p
              className="text-caption mt-0.5"
              style={{ color: palette.textSecondary, textTransform: "none", letterSpacing: "0" }}
            >
              Easy on the eyes
            </p>
          </button>

          {/* Light mode card */}
          <button
            onClick={() => setTheme("light")}
            className="p-4 transition-all text-left"
            style={{
              backgroundColor: palette.surfaceElevated,
              border: `2px solid ${theme === "light" ? BRAND_TEAL : palette.borderSubtle}`,
              borderRadius: "8px",
              cursor: "pointer",
            }}
          >
            <div
              className="p-3 mb-3"
              style={{
                backgroundColor: "#F7F9FB",
                border: `1px solid #E4E8EE`,
                borderRadius: "6px",
              }}
            >
              <div className="flex gap-2 mb-2">
                <div className="w-8 h-2 rounded" style={{ backgroundColor: "#E4E8EE" }} />
                <div className="w-12 h-2 rounded" style={{ backgroundColor: "#E4E8EE" }} />
              </div>
              <div className="space-y-1.5">
                <div className="h-2 rounded w-3/4" style={{ backgroundColor: `${STATUS_PALETTE.PASSED}66` }} />
                <div className="h-2 rounded w-1/2" style={{ backgroundColor: `${STATUS_PALETTE.FAILED}66` }} />
                <div className="h-2 rounded w-2/3" style={{ backgroundColor: `${STATUS_PALETTE.ERROR}66` }} />
              </div>
            </div>
            <p
              className="text-body font-medium"
              style={{ color: palette.textPrimary }}
            >
              Light
            </p>
            <p
              className="text-caption mt-0.5"
              style={{ color: palette.textSecondary, textTransform: "none", letterSpacing: "0" }}
            >
              Classic bright mode
            </p>
          </button>
        </div>
      </section>

      {/* Notifications (placeholder) */}
      <section
        className="p-6"
        style={{
          backgroundColor: palette.surfaceElevated,
          border: `1px solid ${palette.borderSubtle}`,
          borderRadius: "8px",
        }}
      >
        <h2
          className="text-heading mb-1"
          style={{ color: palette.textPrimary }}
        >
          Notifications
        </h2>
        <p
          className="text-body mb-5"
          style={{ color: palette.textSecondary }}
        >
          Configure alert preferences
        </p>

        <div className="space-y-4">
          <ToggleRow
            label="Auto-refresh dashboard"
            description="Refresh results every 30 seconds"
            enabled={false}
            disabled
            theme={theme}
          />
          <ToggleRow
            label="Email alerts on failure"
            description="Get notified when critical tests fail"
            enabled={false}
            disabled
            theme={theme}
          />
          <ToggleRow
            label="Slack integration"
            description="Post alerts to a Slack channel"
            enabled={false}
            disabled
            theme={theme}
          />
        </div>
        <p
          className="text-caption mt-4 italic"
          style={{ color: palette.textSecondary, textTransform: "none", letterSpacing: "0" }}
        >
          Coming soon
        </p>
      </section>
    </div>
  );
}

function ToggleRow({
  label,
  description,
  enabled,
  disabled,
  theme,
}: {
  label: string;
  description: string;
  enabled: boolean;
  disabled?: boolean;
  theme: string;
}) {
  const dark = theme === "dark";
  const palette = dark ? NEUTRAL_SCALE.dark : NEUTRAL_SCALE.light;
  return (
    <div
      className="flex items-center justify-between py-2"
      style={{ opacity: disabled ? 0.5 : 1 }}
    >
      <div>
        <p
          className="text-body font-medium"
          style={{ color: palette.textPrimary }}
        >
          {label}
        </p>
        <p
          className="text-caption mt-0.5"
          style={{ color: palette.textSecondary, textTransform: "none", letterSpacing: "0" }}
        >
          {description}
        </p>
      </div>
      <button
        disabled={disabled}
        className="relative transition-colors"
        style={{
          width: "40px",
          height: "24px",
          borderRadius: "9999px",
          backgroundColor: enabled ? BRAND_TEAL : (dark ? "#374151" : "#D1D5DB"),
          border: "none",
          cursor: disabled ? "not-allowed" : "pointer",
        }}
      >
        <div
          style={{
            position: "absolute",
            top: "4px",
            left: enabled ? "20px" : "4px",
            width: "16px",
            height: "16px",
            borderRadius: "9999px",
            backgroundColor: "#FFFFFF",
            transition: "left 120ms ease-in-out",
          }}
        />
      </button>
    </div>
  );
}
