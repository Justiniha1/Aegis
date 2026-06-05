"use client";

import { useEffect, useState, useCallback } from "react";
import { useTheme } from "@/lib/theme";
import { useRunContext } from "@/lib/run-context";
import { useAuth } from "@/lib/auth";
import { NEUTRAL_SCALE, BRAND_TEAL, STATUS_PALETTE } from "@/lib/constants";
import type { Schedule, ScheduleCreate, ScheduleUpdate } from "@/lib/types";
import {
  listSchedules,
  createSchedule,
  updateSchedule,
  deleteSchedule,
} from "@/lib/api";

// ---------------------------------------------------------------------------
// Preset label helpers
// ---------------------------------------------------------------------------

const PRESET_LABELS: Record<string, string> = {
  hourly: "Hourly",
  daily: "Daily",
  weekly: "Weekly",
};

function formatUtc(iso: string | null): string {
  if (!iso) return "never";
  // new Date(...) never throws (it yields "Invalid Date"), so no try/catch is needed.
  return new Date(iso + (iso.endsWith("Z") ? "" : "Z")).toUTCString();
}

function presetSummary(s: Schedule): string {
  if (!s.preset) return "unknown preset";
  if (s.preset === "hourly") return "Every hour";
  if (s.preset === "daily") return `Daily (times are UTC)`;
  if (s.preset === "weekly") return `Weekly (times are UTC)`;
  return s.preset;
}

// ---------------------------------------------------------------------------
// ScheduleControl — rendered inside the schedule slot for schedulable profiles
// ---------------------------------------------------------------------------

type ScheduleControlProps = {
  profileName: string;
  schedule: Schedule | null;
  token: string;
  palette: typeof NEUTRAL_SCALE.dark | typeof NEUTRAL_SCALE.light;
  onScheduleChange: () => void;
};

type CreateState = {
  preset: "hourly" | "daily" | "weekly";
  at_hour: number;
  at_minute: number;
  weekday: number;
};

function ScheduleControl({
  profileName,
  schedule,
  token,
  palette,
  onScheduleChange,
}: ScheduleControlProps) {
  const [creating, setCreating] = useState(false);
  const [createState, setCreateState] = useState<CreateState>({
    preset: "daily",
    at_hour: 6,
    at_minute: 0,
    weekday: 0,
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCreate = async () => {
    setBusy(true);
    setError(null);
    try {
      const body: ScheduleCreate = {
        profile: profileName,
        preset: createState.preset,
        at_hour: createState.preset !== "hourly" ? createState.at_hour : undefined,
        at_minute: createState.preset !== "hourly" ? createState.at_minute : undefined,
        weekday: createState.preset === "weekly" ? createState.weekday : undefined,
      };
      await createSchedule(body, token);
      setCreating(false);
      onScheduleChange();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to create schedule");
    } finally {
      setBusy(false);
    }
  };

  const handleToggleEnabled = async () => {
    if (!schedule) return;
    setBusy(true);
    setError(null);
    try {
      const body: ScheduleUpdate = { enabled: !schedule.enabled };
      await updateSchedule(schedule.id, body, token);
      onScheduleChange();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to update schedule");
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async () => {
    if (!schedule) return;
    setBusy(true);
    setError(null);
    try {
      await deleteSchedule(schedule.id, token);
      onScheduleChange();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to delete schedule");
    } finally {
      setBusy(false);
    }
  };

  const labelStyle = {
    color: palette.textSecondary,
    fontSize: "12px",
    textTransform: "none" as const,
    letterSpacing: "0",
  };

  const valueStyle = {
    color: palette.textPrimary,
    fontSize: "12px",
    fontWeight: 500,
  };

  if (!schedule && !creating) {
    // No schedule yet — show a "Create schedule" prompt
    return (
      <div>
        <p style={{ ...labelStyle, marginBottom: "8px" }}>
          No active schedule. Times are UTC.
        </p>
        <button
          type="button"
          onClick={() => setCreating(true)}
          style={{
            padding: "4px 12px",
            borderRadius: "4px",
            backgroundColor: BRAND_TEAL,
            color: "#fff",
            fontSize: "12px",
            border: "none",
            cursor: "pointer",
          }}
        >
          Create schedule
        </button>
        {error && (
          <p style={{ color: STATUS_PALETTE.FAILED, fontSize: "12px", marginTop: "4px" }}>
            {error}
          </p>
        )}
      </div>
    );
  }

  if (creating) {
    // Preset picker form
    const WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
        <p style={{ ...labelStyle, marginBottom: "0" }}>
          Choose a schedule preset. Times are UTC.
        </p>

        {/* Preset buttons */}
        <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
          {(["hourly", "daily", "weekly"] as const).map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => setCreateState((s) => ({ ...s, preset: p }))}
              style={{
                padding: "3px 10px",
                borderRadius: "4px",
                fontSize: "12px",
                border: `1px solid ${createState.preset === p ? BRAND_TEAL : palette.borderSubtle}`,
                backgroundColor: createState.preset === p ? `${BRAND_TEAL}1A` : "transparent",
                color: createState.preset === p ? BRAND_TEAL : palette.textSecondary,
                cursor: "pointer",
              }}
            >
              {PRESET_LABELS[p]}
            </button>
          ))}
        </div>

        {/* Hour picker — shown for daily and weekly */}
        {createState.preset !== "hourly" && (
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={labelStyle}>Hour (UTC):</span>
            <select
              value={createState.at_hour}
              onChange={(e) =>
                setCreateState((s) => ({ ...s, at_hour: parseInt(e.target.value, 10) }))
              }
              style={{
                fontSize: "12px",
                padding: "2px 4px",
                borderRadius: "4px",
                border: `1px solid ${palette.borderSubtle}`,
                backgroundColor: palette.surfaceElevated,
                color: palette.textPrimary,
              }}
            >
              {Array.from({ length: 24 }, (_, i) => (
                <option key={i} value={i}>
                  {String(i).padStart(2, "0")} UTC
                </option>
              ))}
            </select>
            <span style={labelStyle}>Minute:</span>
            <select
              value={createState.at_minute}
              onChange={(e) =>
                setCreateState((s) => ({ ...s, at_minute: parseInt(e.target.value, 10) }))
              }
              style={{
                fontSize: "12px",
                padding: "2px 4px",
                borderRadius: "4px",
                border: `1px solid ${palette.borderSubtle}`,
                backgroundColor: palette.surfaceElevated,
                color: palette.textPrimary,
              }}
            >
              {[0, 5, 10, 15, 20, 30, 45].map((m) => (
                <option key={m} value={m}>
                  {String(m).padStart(2, "0")}
                </option>
              ))}
            </select>
          </div>
        )}

        {/* Weekday picker — shown for weekly */}
        {createState.preset === "weekly" && (
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={labelStyle}>Day:</span>
            <select
              value={createState.weekday}
              onChange={(e) =>
                setCreateState((s) => ({ ...s, weekday: parseInt(e.target.value, 10) }))
              }
              style={{
                fontSize: "12px",
                padding: "2px 4px",
                borderRadius: "4px",
                border: `1px solid ${palette.borderSubtle}`,
                backgroundColor: palette.surfaceElevated,
                color: palette.textPrimary,
              }}
            >
              {WEEKDAY_NAMES.map((d, i) => (
                <option key={i} value={i}>
                  {d}
                </option>
              ))}
            </select>
          </div>
        )}

        <div style={{ display: "flex", gap: "6px" }}>
          <button
            type="button"
            onClick={handleCreate}
            disabled={busy}
            style={{
              padding: "4px 12px",
              borderRadius: "4px",
              backgroundColor: BRAND_TEAL,
              color: "#fff",
              fontSize: "12px",
              border: "none",
              cursor: busy ? "not-allowed" : "pointer",
              opacity: busy ? 0.6 : 1,
            }}
          >
            {busy ? "Saving..." : "Save"}
          </button>
          <button
            type="button"
            onClick={() => { setCreating(false); setError(null); }}
            disabled={busy}
            style={{
              padding: "4px 12px",
              borderRadius: "4px",
              backgroundColor: "transparent",
              color: palette.textSecondary,
              fontSize: "12px",
              border: `1px solid ${palette.borderSubtle}`,
              cursor: "pointer",
            }}
          >
            Cancel
          </button>
        </div>

        {error && (
          <p style={{ color: STATUS_PALETTE.FAILED, fontSize: "12px" }}>
            {error}
          </p>
        )}
      </div>
    );
  }

  // Schedule exists — show status + controls
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={valueStyle}>{presetSummary(schedule!)}</span>
        <span
          style={{
            fontSize: "11px",
            padding: "1px 6px",
            borderRadius: "4px",
            backgroundColor: schedule!.enabled ? `${BRAND_TEAL}1A` : `${palette.textSecondary}1A`,
            color: schedule!.enabled ? BRAND_TEAL : palette.textSecondary,
          }}
        >
          {schedule!.enabled ? "Active" : "Paused"}
        </span>
      </div>

      <p style={labelStyle}>
        Last run: {formatUtc(schedule!.last_run_at)} (UTC)
      </p>
      <p style={labelStyle}>
        Next run: {formatUtc(schedule!.next_run_at)} (UTC)
      </p>

      {error && (
        <p style={{ color: STATUS_PALETTE.FAILED, fontSize: "12px" }}>
          {error}
        </p>
      )}

      <div style={{ display: "flex", gap: "6px", marginTop: "2px" }}>
        <button
          type="button"
          onClick={handleToggleEnabled}
          disabled={busy}
          style={{
            padding: "3px 10px",
            borderRadius: "4px",
            fontSize: "12px",
            border: `1px solid ${palette.borderSubtle}`,
            backgroundColor: "transparent",
            color: palette.textSecondary,
            cursor: busy ? "not-allowed" : "pointer",
            opacity: busy ? 0.6 : 1,
          }}
        >
          {schedule!.enabled ? "Pause" : "Resume"}
        </button>
        <button
          type="button"
          onClick={handleDelete}
          disabled={busy}
          style={{
            padding: "3px 10px",
            borderRadius: "4px",
            fontSize: "12px",
            border: `1px solid ${STATUS_PALETTE.FAILED}66`,
            backgroundColor: "transparent",
            color: STATUS_PALETTE.FAILED,
            cursor: busy ? "not-allowed" : "pointer",
            opacity: busy ? 0.6 : 1,
          }}
        >
          Delete
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main SettingsPage
// ---------------------------------------------------------------------------

export default function SettingsPage() {
  const { theme, setTheme } = useTheme();
  const { profiles, selectedProfile, setSelectedProfile, profilesLoading, profilesError } = useRunContext();
  const { token } = useAuth();
  const dark = theme === "dark";
  const palette = dark ? NEUTRAL_SCALE.dark : NEUTRAL_SCALE.light;

  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [schedulesLoading, setSchedulesLoading] = useState(false);
  const [schedulesError, setSchedulesError] = useState<string | null>(null);

  const loadSchedules = useCallback(() => {
    if (!token) return;
    setSchedulesLoading(true);
    setSchedulesError(null);
    listSchedules(token)
      .then((s) => { setSchedules(s); setSchedulesLoading(false); })
      .catch((e: unknown) => {
        setSchedulesError(e instanceof Error ? e.message : "Failed to load schedules");
        setSchedulesLoading(false);
      });
  }, [token]);

  useEffect(() => {
    loadSchedules();
  }, [loadSchedules]);

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
            Loading profiles...
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
          <div className="space-y-3">
            {profiles.map((p) => {
              const active = selectedProfile === p.name;
              // Find the schedule for this profile (if any)
              const sched = schedules.find((s) => s.profile === p.name) ?? null;

              return (
                <div key={p.name}>
                  <button
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

                  {/* Capability indicator — rendered below the select button row */}
                  {p.website_schedulable ? (
                    <div
                      style={{
                        marginTop: "4px",
                        marginLeft: "22px",
                        padding: "10px 12px",
                        borderRadius: "6px",
                        backgroundColor: `${BRAND_TEAL}0A`,
                        border: `1px solid ${BRAND_TEAL}33`,
                      }}
                    >
                      <p
                        className="text-caption"
                        style={{
                          color: BRAND_TEAL,
                          fontWeight: 500,
                          textTransform: "none",
                          letterSpacing: "0",
                          marginBottom: "8px",
                        }}
                      >
                        Schedulable from the dashboard
                      </p>

                      {schedulesLoading ? (
                        <p style={{ color: palette.textSecondary, fontSize: "12px" }}>
                          Loading schedule...
                        </p>
                      ) : schedulesError ? (
                        <p style={{ color: STATUS_PALETTE.FAILED, fontSize: "12px" }}>
                          {schedulesError}
                        </p>
                      ) : (
                        <ScheduleControl
                          profileName={p.name}
                          schedule={sched}
                          token={token ?? ""}
                          palette={palette}
                          onScheduleChange={loadSchedules}
                        />
                      )}
                    </div>
                  ) : (
                    <div
                      style={{
                        marginTop: "4px",
                        marginLeft: "22px",
                        padding: "8px 12px",
                        borderRadius: "6px",
                        backgroundColor: palette.surfaceBg,
                        border: `1px solid ${palette.borderSubtle}`,
                      }}
                    >
                      <p
                        className="text-caption"
                        style={{
                          color: palette.textSecondary,
                          fontWeight: 500,
                          textTransform: "none",
                          letterSpacing: "0",
                          marginBottom: "4px",
                        }}
                      >
                        Not schedulable from the dashboard
                      </p>
                      <p
                        className="text-caption"
                        style={{
                          color: palette.textSecondary,
                          textTransform: "none",
                          letterSpacing: "0",
                          marginBottom: "6px",
                        }}
                      >
                        This profile points at data the hosted runner cannot reach (for example a
                        local SQLite file). Schedule it from your own environment instead.
                      </p>
                      <a
                        href="/docs/client-lane"
                        style={{
                          color: BRAND_TEAL,
                          fontSize: "12px",
                          textDecoration: "underline",
                          cursor: "pointer",
                        }}
                      >
                        How to schedule from the client lane
                      </a>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
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
