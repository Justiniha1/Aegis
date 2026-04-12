"use client";

import { useTheme } from "@/lib/theme";

export default function SettingsPage() {
  const { theme, setTheme } = useTheme();

  return (
    <div className="max-w-2xl mx-auto space-y-8">
      <div>
        <h1 className={`text-2xl font-bold ${theme === "dark" ? "text-white" : "text-gray-900"}`}>
          Settings
        </h1>
        <p className={`text-sm mt-1 ${theme === "dark" ? "text-gray-400" : "text-gray-600"}`}>
          Customize your dashboard experience
        </p>
      </div>

      {/* Appearance */}
      <section className={`rounded-xl border p-6 ${theme === "dark" ? "bg-gray-900 border-gray-800" : "bg-white border-gray-200"}`}>
        <h2 className={`text-lg font-semibold mb-1 ${theme === "dark" ? "text-white" : "text-gray-900"}`}>
          Appearance
        </h2>
        <p className={`text-sm mb-5 ${theme === "dark" ? "text-gray-400" : "text-gray-600"}`}>
          Choose how the dashboard looks
        </p>

        <div className="grid grid-cols-2 gap-4">
          {/* Dark mode card */}
          <button
            onClick={() => setTheme("dark")}
            className={`rounded-xl border-2 p-4 transition-all text-left ${
              theme === "dark"
                ? "border-blue-500 ring-1 ring-blue-500/30"
                : "border-gray-200 hover:border-gray-300"
            }`}
          >
            <div className="bg-gray-900 rounded-lg p-3 mb-3 border border-gray-700">
              <div className="flex gap-2 mb-2">
                <div className="w-8 h-2 rounded bg-gray-700" />
                <div className="w-12 h-2 rounded bg-gray-700" />
              </div>
              <div className="space-y-1.5">
                <div className="h-2 rounded bg-green-500/40 w-3/4" />
                <div className="h-2 rounded bg-red-500/40 w-1/2" />
                <div className="h-2 rounded bg-yellow-500/40 w-2/3" />
              </div>
            </div>
            <p className={`font-medium text-sm ${theme === "dark" ? "text-white" : "text-gray-900"}`}>
              Dark
            </p>
            <p className={`text-xs mt-0.5 ${theme === "dark" ? "text-gray-400" : "text-gray-500"}`}>
              Easy on the eyes
            </p>
          </button>

          {/* Light mode card */}
          <button
            onClick={() => setTheme("light")}
            className={`rounded-xl border-2 p-4 transition-all text-left ${
              theme === "light"
                ? "border-blue-500 ring-1 ring-blue-500/30"
                : theme === "dark"
                ? "border-gray-700 hover:border-gray-600"
                : "border-gray-200 hover:border-gray-300"
            }`}
          >
            <div className="bg-gray-50 rounded-lg p-3 mb-3 border border-gray-200">
              <div className="flex gap-2 mb-2">
                <div className="w-8 h-2 rounded bg-gray-200" />
                <div className="w-12 h-2 rounded bg-gray-200" />
              </div>
              <div className="space-y-1.5">
                <div className="h-2 rounded bg-green-500/40 w-3/4" />
                <div className="h-2 rounded bg-red-500/40 w-1/2" />
                <div className="h-2 rounded bg-yellow-500/40 w-2/3" />
              </div>
            </div>
            <p className={`font-medium text-sm ${theme === "dark" ? "text-white" : "text-gray-900"}`}>
              Light
            </p>
            <p className={`text-xs mt-0.5 ${theme === "dark" ? "text-gray-400" : "text-gray-500"}`}>
              Classic bright mode
            </p>
          </button>
        </div>
      </section>

      {/* Account info (placeholder) */}
      <section className={`rounded-xl border p-6 ${theme === "dark" ? "bg-gray-900 border-gray-800" : "bg-white border-gray-200"}`}>
        <h2 className={`text-lg font-semibold mb-1 ${theme === "dark" ? "text-white" : "text-gray-900"}`}>
          Notifications
        </h2>
        <p className={`text-sm mb-5 ${theme === "dark" ? "text-gray-400" : "text-gray-600"}`}>
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
        <p className={`text-xs mt-4 italic ${theme === "dark" ? "text-gray-600" : "text-gray-400"}`}>
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
  onChange,
}: {
  label: string;
  description: string;
  enabled: boolean;
  disabled?: boolean;
  theme: string;
  onChange?: (v: boolean) => void;
}) {
  return (
    <div className={`flex items-center justify-between py-2 ${disabled ? "opacity-50" : ""}`}>
      <div>
        <p className={`text-sm font-medium ${theme === "dark" ? "text-white" : "text-gray-900"}`}>
          {label}
        </p>
        <p className={`text-xs ${theme === "dark" ? "text-gray-400" : "text-gray-500"}`}>
          {description}
        </p>
      </div>
      <button
        disabled={disabled}
        onClick={() => onChange?.(!enabled)}
        className={`w-10 h-6 rounded-full relative transition-colors ${
          enabled ? "bg-blue-500" : theme === "dark" ? "bg-gray-700" : "bg-gray-300"
        }`}
      >
        <div
          className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${
            enabled ? "left-5" : "left-1"
          }`}
        />
      </button>
    </div>
  );
}
