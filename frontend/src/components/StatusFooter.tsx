import { NEUTRAL_SCALE, STATUS_PALETTE } from "@/lib/constants";

/* StatusFooter — static "Engine: idle" strip (D-05, UI-SPEC §"Status footer")
   Pinned below the main content area.
   Height: 32px. Background: surface-elevated. 1px top border.
   Content: 6px neutral indicator dot + "Engine: idle" body text.
   No pulse, no live-signal timestamp copy, no chromatic accent. */

export function StatusFooter({ dark }: { dark: boolean }) {
  const palette = dark ? NEUTRAL_SCALE.dark : NEUTRAL_SCALE.light;
  const neutral = STATUS_PALETTE.SKIPPED;

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
            backgroundColor: neutral,
          }}
        />
        Engine: idle
      </span>
    </footer>
  );
}
