export const STATUS_COLORS: Record<string, string> = {
  PASSED: "#22c55e",
  FAILED: "#ef4444",
  ERROR: "#f59e0b",
  SKIPPED: "#6b7280",
};

export const SEVERITY_COLORS: Record<string, string> = {
  CRITICAL: "#dc2626",
  HIGH: "#ef4444",
  MEDIUM: "#f59e0b",
  LOW: "#3b82f6",
};

export const TYPE_LABELS: Record<string, string> = {
  null_check: "Null Check",
  duplicate_check: "Duplicate Check",
  unique_check: "Unique Check",
  row_count: "Row Count",
  schema_check: "Schema Check",
  range_check: "Range Check",
  relationship_check: "Relationship Check",
  custom_sql: "Custom SQL",
};

export const SEVERITY_LABELS: Record<string, string> = {
  CRITICAL: "Critical",
  HIGH: "High",
  MEDIUM: "Medium",
  LOW: "Low",
};

export const STATUS_LABELS: Record<string, string> = {
  PASSED: "Passed",
  FAILED: "Failed",
  ERROR: "Error",
  SKIPPED: "Skipped",
};

// Title-case a snake_case config key for user-visible labels.
// Example: "min_value" → "Min Value", "expected_count" → "Expected Count".
// Falls through to the raw key for non-snake-case input.
export function formatConfigKey(key: string): string {
  return key
    .split("_")
    .map(part => part.length === 0 ? part : part[0].toUpperCase() + part.slice(1))
    .join(" ");
}

/* ── Phase 1.1 design tokens — mirrors of CSS custom properties in globals.css ── */
/* These exist so Recharts (which takes JS strings, not CSS vars) and inline-style
   props use the same hex values as Tailwind utilities. Single source of truth
   for the locked palette per UI-SPEC.md §Color (D-13). */

export const BRAND_NAVY = "#042C53";
export const BRAND_TEAL = "#1D9E75";

export const NEUTRAL_SCALE = {
  light: {
    surfaceBg: "#F7F9FB",
    surfaceElevated: "#FFFFFF",
    borderSubtle: "#E4E8EE",
    textSecondary: "#5A6577",
    textPrimary: "#0E1626",
  },
  dark: {
    surfaceBg: "#0B1220",
    surfaceElevated: "#0F1A2E",
    borderSubtle: "#1E2A40",
    textSecondary: "#8B95A8",
    textPrimary: "#E8ECF3",
  },
} as const;

export const STATUS_PALETTE: Record<string, string> = {
  PASSED: "#22C55E",
  FAILED: "#EF4444",
  ERROR: "#F59E0B",
  SKIPPED: "#6B7280",
};

export const DESTRUCTIVE = "#D9544F";

/* 8 entries — one per builtin test type, matches keys in TYPE_LABELS.
   Hex values pinned in UI-SPEC.md §Per-test-type pill palette. */
export const TYPE_PILL_COLORS: Record<string, string> = {
  null_check: "#3B82F6",
  duplicate_check: "#F59E0B",
  schema_check: "#1D9E75",
  range_check: "#EF4444",
  row_count: "#A855F7",
  unique_check: "#7C3AED",
  relationship_check: "#06B6D4",
  custom_sql: "#475569",
};

export const SIDEBAR_ACTIVE_BG = "#0B3A66";
