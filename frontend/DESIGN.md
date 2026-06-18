# Comet Design Language

**Locked in Phase 1.1 (2026-05-17). Phase 2 and beyond consume these tokens — do not re-derive.**

Source contract: `.planning/phases/01-1-frontend-design-pass/01-1-UI-SPEC.md` (approved).

## Where the tokens live

- **CSS custom properties** in `frontend/src/app/globals.css` under `@theme inline` — consumed by Tailwind 4 utilities (`bg-brand-navy`, etc.) and direct `var(--color-…)` references.
- **JS-side mirrors** in `frontend/src/lib/constants.ts` — consumed by Recharts (which needs string hex values) and any inline `style={{}}` props.

If you find yourself typing a hex value, stop — import the constant or use the CSS variable.

## Color

### Brand
- Navy `#042C53` (`BRAND_NAVY`, `--color-brand-navy`) — sidebar background (both themes), primary CTA solid fill, focus rings on primary controls.
- Teal `#1D9E75` (`BRAND_TEAL`, `--color-brand-teal`) — "Ae" logo monogram, active-nav left accent, positive-trend line, focus rings on secondary controls.

### Neutrals (cool-leaning, 5 steps; `NEUTRAL_SCALE.{light,dark}`)
| Token | Light | Dark | Use |
|-------|-------|------|-----|
| `surfaceBg` | `#F7F9FB` | `#0B1220` | Page canvas |
| `surfaceElevated` | `#FFFFFF` | `#0F1A2E` | Cards, top bar, footer |
| `borderSubtle` | `#E4E8EE` | `#1E2A40` | Card / table / chrome borders |
| `textSecondary` | `#5A6577` | `#8B95A8` | Muted labels, breadcrumbs |
| `textPrimary` | `#0E1626` | `#E8ECF3` | Body copy, headings |

### Status (`STATUS_PALETTE`) — dashboard-layer only; never appears in chrome
- PASSED `#22C55E`, ERROR `#F59E0B`, FAILED `#EF4444`, SKIPPED `#6B7280`

### Destructive
- `#D9544F` (`DESTRUCTIVE`) — reserved; no destructive flows yet.

### Per-test-type pills (`TYPE_PILL_COLORS`, 8 entries — used by `<TypePill>` in result-table rows)
- `null_check` `#3B82F6` · `duplicate_check` `#F59E0B` · `schema_check` `#1D9E75` · `range_check` `#EF4444` · `row_count` `#A855F7` · `unique_check` `#7C3AED` · `relationship_check` `#06B6D4` · `custom_sql` `#475569`

### Sidebar active state
- Background `#0B3A66` (`SIDEBAR_ACTIVE_BG`) + 2px left border in `BRAND_TEAL` + 120ms ease transition.

## Typography

- **Inter** — body, headings, captions, breadcrumb, buttons. CSS: `var(--font-inter)` (Tailwind: `font-sans`).
- **JetBrains Mono** — metric hero numbers, test names (rendered verbatim per Phase 1 D-05), SQL/code, user-supplied identifiers in tables. CSS: `var(--font-jetbrains-mono)` (Tailwind: `font-mono`).

Scale — 4 sizes, 2 weights, uniform across pages (utility classes declared in `globals.css`; never inline these sizes):

| Role | Class | Size | Weight | Line height | Use |
|------|-------|------|--------|-------------|-----|
| Caption | `.text-caption` | 11px | 600 | 1.4 | Uppercase tracked-out 0.08em column headers, group labels |
| Body | `.text-body` | 14px | 400 | 1.5 | Default body, table cells, breadcrumb, buttons |
| Heading | `.text-heading` | 20px | 600 | 1.3 | Page titles, card titles, section headers |
| Display | `.text-display` | 28px | 600 | 1.2 | Metric hero numbers (JetBrains Mono), login brand line |

Metric-card labels: `.text-body` weight 400, `textSecondary` — render label text as written (Title Case e.g. "Total Tests" / "Passed" / "Failed" / "Errors"; do not force `text-transform`).

When a cell needs caption *sizing* but not its case/letter-spacing (e.g., mono identifier cells, descriptions, error spans), apply `.text-caption` then override `textTransform: "none"` + `letterSpacing: "0"` inline. Pattern repeats across all five page restyles.

## Component shape rules

- **Corner radius:** 8px (cards, buttons, pills, inputs). 4px (small badges, dots-and-pills).
- **Elevation:** border-first — every elevated surface uses `borderSubtle` 1px. Shadows reserved for transient overlays (`0 4px 12px rgb(0 0 0 / 0.08)` on tooltips, dropdowns).
- **Density:** table row 40px · button 36px · input 36px · top bar 56px · footer 32px.
- **Hover:** 4% `textPrimary` overlay tint — no chromatic accent.

## Charts (Recharts + custom Cell fills)

- **Bar fills encode outcome, not category.** Each bar's bucket is classified by `outcomeOf(items)` returning `PASSED | FAILED | MIXED`; `BAR_COLORS` maps those to `STATUS_PALETTE.PASSED` (green), `.FAILED` (red), `.ERROR` (amber). The x-axis label communicates which type/table the bar represents; the colour is reserved for "is this group healthy?". Do not bring per-type pill colours into the chart.
- Axis ticks: `textSecondary` + `var(--font-inter)` at 12px; axis line uses `borderSubtle`; tick line off.
- Tooltip: surface-elevated card with `borderSubtle` 1px, 8px radius, `0 4px 12px rgb(0 0 0 / 0.08)` shadow.

## Page-local form primitives (recipe)

For any page with a dense form, encapsulate input / select / label styling in three page-local sub-components — see `frontend/src/app/dashboard/tests/page.tsx` (`TestFormInput`, `TestFormSelect`, `TestFormLabel`). One styling change in one place propagates to every field. Sub-components stay page-local per `CONVENTIONS.md §"Module Design"`.

## Chrome (locked layout)

```
┌─────────┬──────────────────────────────────────────────────┐
│         │  TOP BAR (surfaceElevated, 56px, borderSubtle b) │
│ SIDEBAR ├──────────────────────────────────────────────────┤
│ (navy)  │  MAIN CONTENT (surfaceBg)                        │
│         ├──────────────────────────────────────────────────┤
│         │  STATUS FOOTER (surfaceElevated, 32px,           │
│         │   borderSubtle t, "Engine: idle")                │
└─────────┴──────────────────────────────────────────────────┘
```

- Sidebar always `BRAND_NAVY` (both themes). Two-group nav: **Monitor** (Dashboard, History), **Configure** (Tests, Settings).
- Top bar: breadcrumb (client / environment) · inline status pills (passing / warnings) · spacer · outlined disabled "Run all" (no tooltip — D-08) · primary navy **"New test"** CTA. Component: `frontend/src/components/TopBar.tsx`.
- Status footer: 6px neutral dot + "Engine: idle". Static placeholder; real liveness wires later. Component: `frontend/src/components/StatusFooter.tsx`.

## Phase 1 carry-forward locks (do not break)

- "Comet" everywhere user-visible. Logo monogram = "Ae" in teal square (D-09).
- `TYPE_LABELS` / `SEVERITY_LABELS` / `STATUS_LABELS` from `constants.ts` for system enum rendering.
- **User-supplied strings render verbatim** — no `.replace`, no auto-derivation of `{table}.{type}` from test names. Test names render in JetBrains Mono.
- Custom SQL renders as `<pre><code>` block in the Tests expand row.
- Sidebar does NOT scroll with main content (`h-screen` on outer dashboard shell).

## Copywriting Contract (locked)

Primary CTA `"New test"` · Disabled slot `"Run all"` (no tooltip) · Footer `"Engine: idle"` · Login error (credentials) `"Sign-in failed — check your email and password and try again."` · Login error (network) `"Can't reach the server. Try again, or check that the API is running."` · Empty state Tests `"No tests configured yet"` / `"Add a test in the YAML editor to start checking your data."` · Empty state Dashboard `"No tests have run yet"` / `"Run your tests to see results here. Use the YAML editor or trigger a run from the CLI."` · Empty state History `"No run history yet"` / `"Past runs will appear here once you trigger one."` · Loading `"Loading…"` · Save success `"Settings saved."`.

## Phase 2 inheritance directive

Phase 2's run-trigger UI surfaces (RUN-01..05) must consume these tokens directly. The visually-disabled "Run all" slot in the top bar is reserved — Phase 2 wires it without restructuring chrome. The TopBar's `passingCount` / `warningCount` placeholders and the StatusFooter's "Engine: idle" placeholder are also Phase 2's to wire live.
