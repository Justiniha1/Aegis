import { STATUS_COLORS, SEVERITY_COLORS } from "@/lib/constants";

export function StatusBadge({ status }: { status: string }) {
  const color = STATUS_COLORS[status] || "#6b7280";
  return (
    <span
      className="text-xs px-2 py-0.5 rounded-full"
      style={{ backgroundColor: `${color}20`, color }}
    >
      {status}
    </span>
  );
}

export function SeverityBadge({ severity }: { severity: string }) {
  const color = SEVERITY_COLORS[severity] || "#6b7280";
  return (
    <span
      className="text-xs px-2 py-0.5 rounded-full"
      style={{ backgroundColor: `${color}20`, color }}
    >
      {severity}
    </span>
  );
}
