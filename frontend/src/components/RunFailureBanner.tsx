"use client";

import { useTheme } from "@/lib/theme";
import { NEUTRAL_SCALE, STATUS_PALETTE } from "@/lib/constants";
import type { Run } from "@/lib/types";

/** Run-level failure banner. Renders only when the run FAILED. Surfaces the
 *  sanitized error reason, which test it died on, the profile, and progress —
 *  the detail that is otherwise invisible for runs that produced no results. */
export function RunFailureBanner({ run }: { run: Run }) {
  const { theme } = useTheme();
  const dark = theme === "dark";
  const palette = dark ? NEUTRAL_SCALE.dark : NEUTRAL_SCALE.light;

  if (run.status !== "FAILED") return null;

  const reason = run.error?.reason;
  const atTest = run.error?.at_test ?? null;

  return (
    <div
      className="px-4 py-3"
      style={{
        backgroundColor: `${STATUS_PALETTE.FAILED}14`,
        borderBottom: `1px solid ${STATUS_PALETTE.FAILED}`,
        borderTopLeftRadius: "8px",
        borderTopRightRadius: "8px",
      }}
      role="alert"
    >
      <p className="text-body font-semibold" style={{ color: STATUS_PALETTE.FAILED }}>
        Run #{run.id} failed
        {atTest != null ? ` at test ${atTest}` : ""}
      </p>
      <p className="text-caption mt-1" style={{ color: palette.textSecondary, textTransform: "none", letterSpacing: "0" }}>
        profile: {run.profile} · ran {run.completed_tests} of {run.total_tests} test
        {run.total_tests !== 1 ? "s" : ""} before failing
      </p>
      {reason && (
        <p
          className="text-caption mt-1 font-mono"
          style={{ color: palette.textPrimary, textTransform: "none", letterSpacing: "0" }}
        >
          {reason}
        </p>
      )}
    </div>
  );
}
