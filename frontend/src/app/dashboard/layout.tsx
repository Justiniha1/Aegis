"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useTheme } from "@/lib/theme";
import { RunProvider, useRunContext } from "@/lib/run-context";
import { TopBar } from "@/components/TopBar";
import { StatusFooter } from "@/components/StatusFooter";
import {
  BRAND_NAVY,
  BRAND_TEAL,
  SIDEBAR_ACTIVE_BG,
  NEUTRAL_SCALE,
} from "@/lib/constants";

const NAV_GROUPS: { label: string; items: { href: string; label: string }[] }[] = [
  {
    label: "Monitor",
    items: [
      { href: "/dashboard", label: "Dashboard" },
      { href: "/dashboard/history", label: "History" },
    ],
  },
  {
    label: "Configure",
    items: [
      { href: "/dashboard/tests", label: "Tests" },
      { href: "/dashboard/settings", label: "Settings" },
    ],
  },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <RunProvider>
      <DashboardLayoutInner>{children}</DashboardLayoutInner>
    </RunProvider>
  );
}

function DashboardLayoutInner({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { clientName, logout } = useAuth();
  const { theme, toggle } = useTheme();
  const { runStatus, runError, isTriggering, trigger, passingCount, warningCount, selectedProfile } = useRunContext();

  const dark = theme === "dark";
  const palette = dark ? NEUTRAL_SCALE.dark : NEUTRAL_SCALE.light;

  const handleLogout = () => {
    logout();
    router.push("/login");
  };

  const isRunActive = runStatus === "QUEUED" || runStatus === "RUNNING";

  return (
    <div
      className="h-screen flex"
      style={{ backgroundColor: palette.surfaceBg }}
      data-theme={dark ? "dark" : "light"}
    >
      {/* ── Sidebar (navy, both themes — UI-SPEC §Sidebar) ─────────────── */}
      <aside
        className="w-56 flex flex-col"
        style={{ backgroundColor: BRAND_NAVY, borderRight: "none" }}
      >
        <div className="px-5 py-6 flex items-center gap-3">
          <div
            className="flex items-center justify-center"
            style={{
              width: "32px",
              height: "32px",
              backgroundColor: BRAND_TEAL,
              borderRadius: "6px",
              fontFamily: "var(--font-jetbrains-mono)",
              fontSize: "14px",
              fontWeight: 600,
              color: "#FFFFFF",
              lineHeight: 1,
            }}
            aria-label="Aegis"
          >
            Ae
          </div>
          <h1
            className="text-lg font-semibold"
            style={{ color: "#FFFFFF", letterSpacing: "-0.01em" }}
          >
            Aegis
          </h1>
        </div>

        <nav
          className="flex-1 px-3 py-4 space-y-6 overflow-y-auto"
          aria-label="Primary"
        >
          {NAV_GROUPS.map((group) => (
            <div key={group.label}>
              <p
                className="px-3 mb-2 text-[11px] font-semibold uppercase"
                style={{ letterSpacing: "0.08em", color: "#8B95A8" }}
              >
                {group.label}
              </p>
              <div className="space-y-1">
                {group.items.map((item) => {
                  const active = pathname === item.href;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      className="block px-3 py-2 text-sm rounded-md transition-colors duration-[120ms] ease-in-out"
                      style={{
                        backgroundColor: active ? SIDEBAR_ACTIVE_BG : "transparent",
                        color: active ? "#FFFFFF" : "#8B95A8",
                        fontWeight: active ? 500 : 400,
                        borderLeft: active ? `2px solid ${BRAND_TEAL}` : "2px solid transparent",
                      }}
                    >
                      {item.label}
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        <div className="px-5 py-4" style={{ borderTop: "1px solid rgba(255,255,255,0.06)" }}>
          <div className="flex items-center justify-between">
            <p
              className="text-sm truncate"
              style={{ color: "#E8ECF3" }}
              title={clientName ?? undefined}
            >
              {clientName}
            </p>
            <button
              onClick={toggle}
              className="text-sm transition-colors"
              style={{ color: "#8B95A8" }}
              title={`Switch to ${dark ? "light" : "dark"} mode`}
              aria-label={`Switch to ${dark ? "light" : "dark"} mode`}
            >
              {dark ? "☀" : "☾"}
            </button>
          </div>
          <button
            onClick={handleLogout}
            className="text-xs mt-1 transition-colors"
            style={{ color: "#8B95A8" }}
            onMouseEnter={(e) => ((e.currentTarget as HTMLButtonElement).style.color = "#E8ECF3")}
            onMouseLeave={(e) => ((e.currentTarget as HTMLButtonElement).style.color = "#8B95A8")}
          >
            Sign out
          </button>
        </div>
      </aside>

      {/* ── Main column: TopBar + scrollable content + StatusFooter ─────── */}
      <div className="flex-1 flex flex-col min-w-0">
        <TopBar
          breadcrumb={{ client: clientName || "—", environment: selectedProfile || "—" }}
          passingCount={passingCount}
          warningCount={warningCount}
          dark={dark}
          showNewTestButton={pathname !== "/dashboard/tests"}
          onRun={trigger}
          runStatus={runStatus}
          runError={runError}
          isRunning={isRunActive || isTriggering}
        />
        <main className="flex-1 overflow-auto p-8" style={{ backgroundColor: palette.surfaceBg }}>
          {children}
        </main>
        <StatusFooter dark={dark} runStatus={runStatus} />
      </div>
    </div>
  );
}
