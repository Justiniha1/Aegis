import type { RunStatus } from "@/lib/types";
import { NEUTRAL_SCALE, STATUS_PALETTE, RUN_STATUS_PALETTE } from "@/lib/constants";

const ENGINE_STATES: Record<string, { label: string; color: string; pulse: boolean }> = {
  QUEUED:   { label: "Engine: queued",   color: RUN_STATUS_PALETTE.QUEUED,   pulse: false },
  RUNNING:  { label: "Engine: running",  color: RUN_STATUS_PALETTE.RUNNING,  pulse: true  },
  COMPLETE: { label: "Engine: finished", color: STATUS_PALETTE.PASSED,       pulse: false },
  FAILED:   { label: "Engine: failed",   color: STATUS_PALETTE.FAILED,       pulse: false },
};

export function StatusFooter({ dark, runStatus }: { dark: boolean; runStatus?: RunStatus | null }) {
  const palette = dark ? NEUTRAL_SCALE.dark : NEUTRAL_SCALE.light;

  const state = runStatus ? ENGINE_STATES[runStatus] : null;
  const dotColor = state ? state.color : STATUS_PALETTE.SKIPPED;
  const label    = state ? state.label : "Engine: idle";
  const pulse    = state?.pulse ?? false;

  return (
    <footer
      className="flex items-center px-6"
      style={{
        height: "32px",
        backgroundColor: palette.surfaceElevated,
        borderTop: `1px solid ${palette.borderSubtle}`,
      }}
    >
      <span className="flex items-center gap-2 text-[13px]" style={{ color: palette.textSecondary }}>
        <span
          style={{
            display: "inline-block",
            width: "6px",
            height: "6px",
            borderRadius: "9999px",
            backgroundColor: dotColor,
            animation: pulse ? "pulse 1.5s ease-in-out infinite" : "none",
            transition: "background-color 300ms",
          }}
        />
        {label}
      </span>
    </footer>
  );
}
