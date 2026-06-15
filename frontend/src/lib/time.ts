/* Server-timestamp handling.
 *
 * The backend records timestamps with datetime.utcnow() — naive UTC, no tzinfo
 * (see dashboard_api/schedule_logic.py). They serialize to ISO WITHOUT a "Z",
 * so `new Date(s)` would misread them as the browser's local time (shifting
 * every value by the local UTC offset). parseServerTime normalizes that: if the
 * string carries no timezone, it is treated as UTC. All formatting below then
 * renders in the user's local timezone via the Date instance's local getters. */

const pad2 = (n: number) => String(n).padStart(2, "0");

/** Parse a server timestamp as UTC-when-unzoned, so display is correct local time. */
export function parseServerTime(iso: string): Date {
  const hasTz = /[zZ]$|[+-]\d{2}:?\d{2}$/.test(iso);
  return new Date(hasTz ? iso : `${iso}Z`);
}

/** Local clock time, "HH:mm" (24-hour, zero-padded). */
export function formatClock(d: Date): string {
  return `${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
}

/** Local date, "MM/DD/YY" (zero-padded). */
export function formatDate(d: Date): string {
  return `${pad2(d.getMonth() + 1)}/${pad2(d.getDate())}/${pad2(d.getFullYear() % 100)}`;
}

/** Compact label for a run timestamp, in local time:
 *  - under 10s ago -> "Now"
 *  - earlier today -> "HH:mm"
 *  - any prior day -> "MM/DD/YY" */
export function formatRunTimeShort(iso: string): string {
  const d = parseServerTime(iso);
  if (Number.isNaN(d.getTime())) return "";
  if (Date.now() - d.getTime() < 10_000) return "Now";
  const now = new Date();
  const sameDay =
    d.getFullYear() === now.getFullYear() &&
    d.getMonth() === now.getMonth() &&
    d.getDate() === now.getDate();
  return sameDay ? formatClock(d) : formatDate(d);
}

/** Full run timestamp in local time, "MM/DD/YY HH:mm". For headers and tooltips. */
export function formatRunTimeFull(iso: string): string {
  const d = parseServerTime(iso);
  if (Number.isNaN(d.getTime())) return "";
  return `${formatDate(d)} ${formatClock(d)}`;
}
