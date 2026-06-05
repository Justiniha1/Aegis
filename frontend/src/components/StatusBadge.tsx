import {
  STATUS_PALETTE,
  SEVERITY_COLORS,
  STATUS_LABELS,
  SEVERITY_LABELS,
  TYPE_LABELS,
  TYPE_PILL_COLORS,
} from "@/lib/constants";

/* ── StatusBadge — pass/fail/error/skip outcome badge ─────────────────── */
/* Per UI-SPEC.md §Color: status palette is dashboard-layer only.
   Per UI-SPEC.md §Component shape rules: 4px radius (small surface). */
export function StatusBadge({ status }: { status: string }) {
  const color = STATUS_PALETTE[status] || "#6B7280";
  return (
    <span
      className="inline-flex items-center text-[11px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded"
      style={{ backgroundColor: `${color}1A`, color, borderRadius: "4px" }}
    >
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}

/* ── SeverityBadge — critical/high/medium/low ────────────────────────── */
export function SeverityBadge({ severity }: { severity: string }) {
  const color = SEVERITY_COLORS[severity] || "#6B7280";
  return (
    <span
      className="inline-flex items-center text-[11px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded"
      style={{ backgroundColor: `${color}1A`, color, borderRadius: "4px" }}
    >
      {SEVERITY_LABELS[severity] ?? severity}
    </span>
  );
}

/* ── TypePill — per-test-type colored pill (8 builtin types) ─────────── */
/* Per UI-SPEC.md §"Per-test-type pill palette": 8 entries pinned.
   Renders the user-facing label from TYPE_LABELS (system enum transform, not user-supplied — D-10 verbatim rule does NOT apply: the type field is a system enum). */
export function TypePill({ type }: { type: string }) {
  const color = TYPE_PILL_COLORS[type] || "#6B7280";
  const label = TYPE_LABELS[type] ?? type;
  return (
    <span
      className="inline-flex items-center text-[11px] font-medium px-2 py-0.5"
      style={{
        backgroundColor: `${color}1A`,
        color,
        borderRadius: "4px",
        border: `1px solid ${color}33`,
      }}
      title={label}
    >
      {label}
    </span>
  );
}

/* ── StatusDot — 7px solid status dot for the results table leftmost column ─ */
/* Per UI-SPEC.md §"Results table": "7px solid status dot in leftmost column" */
export function StatusDot({ status }: { status: string }) {
  const color = STATUS_PALETTE[status] || "#6B7280";
  return (
    <span
      aria-label={STATUS_LABELS[status] ?? status}
      title={STATUS_LABELS[status] ?? status}
      style={{
        display: "inline-block",
        width: "7px",
        height: "7px",
        borderRadius: "9999px",
        backgroundColor: color,
      }}
    />
  );
}
