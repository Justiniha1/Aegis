"use client";

import { useTheme } from "@/lib/theme";
import { NEUTRAL_SCALE, BRAND_TEAL } from "@/lib/constants";
import { StatusBadge, SeverityBadge, TypePill, StatusDot } from "@/components/StatusBadge";
import { ErrorDetail } from "@/components/ErrorDetail";
import type { TestResult } from "@/lib/types";

/** A single test result as a clickable list row with an animated expand body.
 *  Shared by the Dashboard results list and the History run panel so the two
 *  surfaces stay identical. Renders an <li>; wrap calls in a <ul>.
 *
 *  `sqlQuery` is optional: the Dashboard joins it from the test definition for
 *  custom_sql tests; History does not have it (TestResult carries no query). */
export function ResultRow({
  result: r, expanded, onToggle, sqlQuery,
}: {
  result: TestResult; expanded: boolean; onToggle: () => void; sqlQuery?: string;
}) {
  const { theme } = useTheme();
  const dark = theme === "dark";
  const palette = dark ? NEUTRAL_SCALE.dark : NEUTRAL_SCALE.light;
  const hoverBg = dark ? "rgba(232,236,243,0.04)" : "rgba(14,22,38,0.035)";

  return (
    <li style={{ borderTop: `1px solid ${palette.borderSubtle}` }}>
      <div
        role="button"
        tabIndex={0}
        aria-expanded={expanded}
        onClick={onToggle}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onToggle(); } }}
        className="w-full grid items-center gap-x-3 px-6 py-3 cursor-pointer transition-colors duration-150 motion-reduce:transition-none focus-visible:outline-2 focus-visible:-outline-offset-2"
        style={{ gridTemplateColumns: "10px minmax(0,1fr) auto auto auto 16px", outlineColor: BRAND_TEAL }}
        onMouseEnter={(e) => ((e.currentTarget as HTMLDivElement).style.backgroundColor = hoverBg)}
        onMouseLeave={(e) => ((e.currentTarget as HTMLDivElement).style.backgroundColor = "transparent")}
      >
        <StatusDot status={r.status} />
        <div className="min-w-0">
          <p className="truncate" style={{ fontFamily: "var(--font-jetbrains-mono)", fontSize: "13px", color: palette.textPrimary }} title={r.test_name}>
            {r.test_name}
          </p>
          {(() => {
            const meta = [r.table, r.column].filter(Boolean).join(" · ");
            if (!meta && !r.message) return null;
            return (
              <p className="truncate" style={{ fontSize: "12px", color: palette.textSecondary, marginTop: "2px" }} title={[meta, r.message].filter(Boolean).join("  ·  ")}>
                {meta && <span style={{ fontFamily: "var(--font-jetbrains-mono)" }}>{meta}</span>}
                {meta && r.message && <span>{"  ·  "}</span>}
                {r.message}
              </p>
            );
          })()}
        </div>
        <TypePill type={r.test_type} />
        <SeverityBadge severity={r.severity} />
        <StatusBadge status={r.status} />
        <span
          aria-hidden="true"
          className="justify-self-end transition-transform duration-200 motion-reduce:transition-none"
          style={{ color: palette.textSecondary, fontSize: "10px", transform: expanded ? "rotate(90deg)" : "rotate(0deg)" }}
        >
          ▶
        </span>
      </div>
      {/* Animated expand: grid-rows 0fr -> 1fr keeps height transitions smooth. */}
      <div
        className="grid transition-[grid-template-rows] duration-200 ease-out motion-reduce:transition-none"
        style={{ gridTemplateRows: expanded ? "1fr" : "0fr" }}
      >
        <div className="overflow-hidden">
          <div className="px-6 pb-4 pl-[3.25rem]" style={{ backgroundColor: palette.surfaceBg }}>
            <div className="pt-4">
              <ErrorDetail result={r} sqlQuery={sqlQuery} />
            </div>
          </div>
        </div>
      </div>
    </li>
  );
}
