import Link from "next/link";
import { BRAND_NAVY, STATUS_PALETTE, NEUTRAL_SCALE } from "@/lib/constants";

/* TopBar — shared dashboard chrome (D-04, UI-SPEC §"Top bar")
   Renders: breadcrumb (client / environment), inline pass/warning status badges,
   spacer, disabled outlined "Run all" (D-08 — no tooltip text), primary navy "New test" CTA.
   Height: 56px. Background: surface-elevated. 1px bottom border.

   Per CONVENTIONS.md §"Module Design": `dark` and `showNewTestButton` threaded
   explicitly — no useTheme()/usePathname() here. The layout owns route awareness. */

export function TopBar({
  breadcrumb,
  passingCount,
  warningCount,
  dark,
  showNewTestButton,
}: {
  breadcrumb: { client: string; environment: string };
  passingCount: number;
  warningCount: number;
  dark: boolean;
  showNewTestButton: boolean;
}) {
  const palette = dark ? NEUTRAL_SCALE.dark : NEUTRAL_SCALE.light;
  const passColor = STATUS_PALETTE.PASSED;
  const warnColor = STATUS_PALETTE.ERROR;

  return (
    <header
      className="flex items-center justify-between px-6"
      style={{
        height: "56px",
        backgroundColor: palette.surfaceElevated,
        borderBottom: `1px solid ${palette.borderSubtle}`,
      }}
    >
      {/* ── Left: breadcrumb + inline status badges ── */}
      <div className="flex items-center gap-4">
        <nav className="text-sm" style={{ color: palette.textSecondary }} aria-label="Breadcrumb">
          <span style={{ color: palette.textPrimary, fontWeight: 500 }}>{breadcrumb.client}</span>
          <span className="mx-2" style={{ color: palette.textSecondary }}>/</span>
          <span style={{ color: palette.textSecondary }}>{breadcrumb.environment}</span>
        </nav>

        <div className="flex items-center gap-2">
          <span
            className="inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider px-2 py-0.5"
            style={{
              backgroundColor: `${passColor}1A`,
              color: passColor,
              borderRadius: "4px",
            }}
          >
            <span style={{ display: "inline-block", width: "6px", height: "6px", borderRadius: "9999px", backgroundColor: passColor }} />
            {passingCount} passing
          </span>
          <span
            className="inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider px-2 py-0.5"
            style={{
              backgroundColor: `${warnColor}1A`,
              color: warnColor,
              borderRadius: "4px",
            }}
          >
            <span style={{ display: "inline-block", width: "6px", height: "6px", borderRadius: "9999px", backgroundColor: warnColor }} />
            {warningCount} warnings
          </span>
        </div>
      </div>

      {/* ── Right: disabled "Run all" + primary "New test" ── */}
      <div className="flex items-center gap-2">
        <button
          type="button"
          disabled
          aria-disabled="true"
          className="text-sm font-medium px-3 py-1.5"
          style={{
            height: "36px",
            border: `1px solid ${palette.borderSubtle}`,
            color: palette.textSecondary,
            backgroundColor: "transparent",
            borderRadius: "8px",
            opacity: 0.5,
            cursor: "not-allowed",
          }}
        >
          Run all
        </button>
        {showNewTestButton && (
          <Link
            href="/dashboard/tests"
            className="inline-flex items-center text-sm font-medium px-3"
            style={{
              height: "36px",
              backgroundColor: BRAND_NAVY,
              color: "#FFFFFF",
              border: "none",
              borderRadius: "8px",
              cursor: "pointer",
              textDecoration: "none",
            }}
          >
            New test
          </Link>
        )}
      </div>
    </header>
  );
}
