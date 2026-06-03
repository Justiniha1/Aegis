"use client";

import { useTheme } from "@/lib/theme";
import { useRunContext } from "@/lib/run-context";
import { NEUTRAL_SCALE, BRAND_TEAL, STATUS_PALETTE } from "@/lib/constants";

export default function SettingsPage() {
  const { theme, setTheme } = useTheme();
  const { profiles, selectedProfile, setSelectedProfile, profilesLoading, profilesError } = useRunContext();
  const dark = theme === "dark";
  const palette = dark ? NEUTRAL_SCALE.dark : NEUTRAL_SCALE.light;

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
          <div className="space-y-3">
            {profiles.map((p) => {
              const active = selectedProfile === p.name;
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
                        padding: "8px 12px",
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
                          marginBottom: "4px",
                        }}
                      >
                        Schedulable from the dashboard
                      </p>
                      {/* Wave C mounts the real schedule control into this slot */}
                      <div
                        data-schedule-slot={p.name}
                        style={{
                          color: palette.textSecondary,
                          fontSize: "12px",
                          fontStyle: "italic",
                        }}
                      >
                        Recurring schedule — configure below
                      </div>
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
