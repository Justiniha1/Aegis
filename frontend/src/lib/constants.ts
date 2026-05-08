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
