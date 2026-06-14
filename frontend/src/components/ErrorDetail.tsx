"use client";

import { useTheme } from "@/lib/theme";
import { NEUTRAL_SCALE, STATUS_PALETTE, formatConfigKey } from "@/lib/constants";
import { formatMetricValue } from "@/lib/format";
import { failureKind, metricEntriesOf } from "@/lib/error-model";
import type { TestResult } from "@/lib/types";

/** Expandable per-test detail body. Shared by the Dashboard results table,
 *  the Dashboard drill-down detail list, and the History run panel. */
export function ErrorDetail({ result, sqlQuery }: { result: TestResult; sqlQuery?: string }) {
  const { theme } = useTheme();
  const dark = theme === "dark";
  const palette = dark ? NEUTRAL_SCALE.dark : NEUTRAL_SCALE.light;
  const kind = failureKind(result);
  const metricEntries = metricEntriesOf(result);
  const isCustomSql = result.test_type === "custom_sql";

  const cardStyle: React.CSSProperties = {
    backgroundColor: palette.surfaceElevated,
    border: `1px solid ${palette.borderSubtle}`,
    borderRadius: "8px",
  };

  return (
    <div className="space-y-3">
      {result.message && (
        <p
          className="text-body"
          style={{ color: kind === "data" ? STATUS_PALETTE.FAILED : palette.textSecondary }}
        >
          {result.message}
        </p>
      )}

      {kind === "execution" && (
        <p className="text-caption" style={{ color: palette.textSecondary, textTransform: "none", letterSpacing: "0" }}>
          The test itself could not run — this is a configuration or connection problem, not a data
          failure. Fix the test setup and re-run.
        </p>
      )}

      {isCustomSql && sqlQuery && (
        <div className="overflow-hidden" style={cardStyle}>
          <div
            className="px-4 py-2 font-mono text-xs"
            style={{ borderBottom: `1px solid ${palette.borderSubtle}`, color: palette.textSecondary }}
          >
            query
          </div>
          <pre
            className="px-4 py-3 font-mono text-xs overflow-x-auto whitespace-pre max-h-64 overflow-y-auto"
            style={{ color: palette.textPrimary }}
          >
            <code>{sqlQuery}</code>
          </pre>
        </div>
      )}

      {metricEntries.length > 0 && (
        // 3-column metric grid: standardized across Dashboard + History (was 4-col in the old ResultsTable expand).
        <div className="grid grid-cols-3 gap-3">
          {metricEntries.map(([key, val]) => (
            <div key={key} className="px-3 py-2" style={cardStyle}>
              <p className="text-caption" style={{ color: palette.textSecondary }}>{formatConfigKey(key)}</p>
              <p
                className="text-body font-medium mt-0.5 truncate"
                style={{ color: palette.textPrimary }}
                title={typeof val === "object" ? JSON.stringify(val) : String(val)}
              >
                {formatMetricValue(val)}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
