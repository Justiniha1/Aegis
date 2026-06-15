import { describe, it, expect } from "vitest";
import { parseServerTime, formatClock, formatDate, formatRunTimeShort } from "./time";

describe("parseServerTime", () => {
  it("treats an unzoned server timestamp as UTC (the core fix)", () => {
    // Naive UTC string (no 'Z'), as the backend emits it.
    expect(parseServerTime("2026-06-14T12:00:00").getTime()).toBe(Date.UTC(2026, 5, 14, 12, 0, 0));
  });

  it("does not double-apply when a 'Z' is already present", () => {
    expect(parseServerTime("2026-06-14T12:00:00Z").getTime()).toBe(Date.UTC(2026, 5, 14, 12, 0, 0));
  });

  it("respects an explicit numeric offset", () => {
    // 12:00 at +02:00 is 10:00 UTC.
    expect(parseServerTime("2026-06-14T12:00:00+02:00").getTime()).toBe(Date.UTC(2026, 5, 14, 10, 0, 0));
  });

  it("handles fractional seconds", () => {
    expect(parseServerTime("2026-06-14T12:00:00.500000").getTime()).toBe(Date.UTC(2026, 5, 14, 12, 0, 0, 500));
  });
});

describe("formatClock / formatDate (local, zero-padded)", () => {
  // Construct from local components so getters are timezone-independent.
  const d = new Date(2026, 0, 5, 9, 7); // Jan 5 2026, 09:07 local
  it("formats HH:mm", () => { expect(formatClock(d)).toBe("09:07"); });
  it("formats MM/DD/YY", () => { expect(formatDate(d)).toBe("01/05/26"); });
});

describe("formatRunTimeShort", () => {
  it("says 'Now' for a timestamp under 10s old", () => {
    const justNow = new Date(Date.now() - 3000).toISOString().replace("Z", ""); // naive-UTC, 3s ago
    expect(formatRunTimeShort(justNow)).toBe("Now");
  });

  it("returns empty string for an invalid timestamp", () => {
    expect(formatRunTimeShort("not-a-date")).toBe("");
  });
});
