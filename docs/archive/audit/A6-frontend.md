# A6 — Frontend Audit (Comet dashboard)

Area: entire `frontend/` Next.js (App Router) + TypeScript + React 19 SPA.
Read-only audit. No source files were modified.

## Summary

The frontend is a single-client-render SPA: every page is `"use client"`, there are no
Server Components, no `middleware.ts`, no route handlers, and no server-side auth. The whole
app is gated entirely in the browser, and the JWT plus client identity are persisted in
`localStorage` (`dqf_auth`). That is the single biggest risk: the bearer token is readable by
any injected script and survives until explicit logout, with no refresh/expiry handling.
Functionally the code is in good shape — the run-polling lifecycle, History join, and metric
math are carefully written and centralized in `lib/`. The most serious correctness bug is a
stale-closure race in the run-polling effect (`run-context.tsx`) that can leak a `setInterval`
and keep polling a stale run. There is a hard data-race between the two pages that both write
the same `lastCompleted`-keyed fetch and the global badge fetch (three uncoordinated reads of
`/api/v1/results` with different limits). Notifications settings are dead placeholder UI, and a
`/docs/client-lane` link points at a route that does not exist in this app. Test coverage is
zero: `vitest` is configured in `package.json` but there are no test files and no vitest config,
so the "skip the *.test.ts files" guidance in the brief is moot — nothing is covered. Config is
mostly default Next 16 scaffolding; `next.config.ts` is empty (no security headers). The
`AGENTS.md` claim that this is a "modified Next.js" with breaking changes is unsubstantiated:
`node_modules` is not even installed, the referenced `node_modules/next/dist/docs/` path does
not exist, and the code uses entirely standard App Router APIs (`next/navigation`,
`next/font/google`, `next/link`). Treat that file as misleading.

## Findings

### [Critical] JWT + client identity stored in localStorage (XSS-exfiltratable, no expiry)
- Location: `frontend/src/lib/auth.tsx:30,49` (read/write `dqf_auth`); consumed app-wide via `useAuth()` and passed as a bearer token in `frontend/src/lib/api.ts:7`.
- What & why: The access token is written to `localStorage` and re-hydrated on mount. `localStorage` is readable by any JavaScript running on the origin, so a single XSS (or a malicious dependency) can exfiltrate the token; the token also persists indefinitely with no refresh, rotation, or expiry check on the client. Current best practice for SPAs is an `HttpOnly; Secure; SameSite` cookie (token unreadable by JS) or an in-memory access token paired with an HttpOnly refresh cookie. See sources below.
- Recommendation: Move the token to an HttpOnly cookie set by the API and add CSRF protection (SameSite=Lax/Strict + anti-CSRF token), or hold the access token in memory only and use a refresh cookie. This is an API + frontend contract change.
- Disposition: `ask-first` (changes the auth transport and the backend contract; alters behavior).

### [High] Stale-closure race in the run-polling effect can leak the interval and poll a dead run
- Location: `frontend/src/lib/run-context.tsx:94-119`.
- What & why: The poll effect depends on `[runId, token]` but reads `runStatusRef.current` and calls `getRun(runId, …)`. The early-return guard at line 96 uses the ref, but once the interval is created it is only torn down by (a) the cleanup when `runId`/`token` change, or (b) the in-callback `clearInterval` when status becomes COMPLETE/FAILED. If `trigger()` sets a new `runId` while a prior interval's async `getRun` is in flight, React runs cleanup for the old effect (good), but the in-flight `await` from the old tick still resolves and calls `setRunStatus`/`setLastCompleted` against the new run's UI — there is no per-interval "cancelled" flag and no abort. The result is a transient wrong status and a possible double-increment of `lastCompleted` (which fans out to three refetches). The `// eslint-disable-line react-hooks/exhaustive-deps` hides that the effect closes over setters/ref by design but does not guard the resolved-after-unmount write.
- Recommendation: Add a `let cancelled = false;` captured per effect run, check it after each `await` before calling setters, and set it in cleanup. Optionally pass an `AbortSignal` to `getRun`. Keep behavior identical otherwise.
- Disposition: `auto-fix-safe` (guard only suppresses writes from a superseded effect; observable behavior is corrected, not changed).

### [High] Three uncoordinated reads of `/api/v1/results` with conflicting limits and no cancellation
- Location: `frontend/src/lib/run-context.tsx:83` (`limit=500`), `frontend/src/app/dashboard/page.tsx:138` (`limit=500`), `frontend/src/app/dashboard/history/page.tsx:94` (`limit=1000`).
- What & why: The badge fetch in `RunProvider`, the Dashboard fetch, and the History fetch all hit the same endpoint independently, keyed on `lastCompleted`, with different `limit`s. `latestRunResults`/`prevSummary` assume the array is "newest-first" and assume the latest run's rows fit within the limit (line `run-views.ts` and `format.ts:29-34`). If a single run has > limit rows, or runs interleave, the badge counts (500) and the dashboard "previous run" delta (500) can disagree with History (1000) and with each other. None of these fetches are abortable, so a fast logout/navigation can resolve a fetch after the component unmounts (React 19 will warn) and a `lastCompleted` bump triggers all three simultaneously.
- Recommendation: Centralize a single results fetch (e.g. in `RunProvider` or a `useResults` hook) with one limit, share via context, and add abort on unmount/dep-change. At minimum align the limits and document the newest-first ordering contract the backend must honor.
- Disposition: `ask-first` (consolidation changes data-flow/architecture; the abort guards alone are `auto-fix-safe`).

### [High] No client-side token expiry / 401 handling — silent broken sessions
- Location: `frontend/src/lib/api.ts:16-19` (throws generic `Error` on any non-2xx); consumers e.g. `frontend/src/app/dashboard/page.tsx:147`, `history/page.tsx:97`, `tests/page.tsx:54`.
- What & why: Pages treat *any* rejected fetch as "redirect to /login" (`.catch(() => router.push("/login"))`), but `logout()` is never called, so the expired/invalid token remains in `localStorage` and the user is bounced to login while still "authenticated" in context — `page.tsx` (`/`) will then `router.replace("/dashboard")` because `token` is still truthy, producing a redirect loop or a flash. There is no distinction between 401 (expired token → clear auth) and a transient 500/network error (should retry/toast, not logout). History added a comment about a 422 causing "spurious logout" (`history/page.tsx:91`) — that is the same root cause surfacing.
- Recommendation: Have `request()` surface the HTTP status (e.g. throw a typed `ApiError` with `.status`). On 401, call `logout()` and redirect; on network/5xx, show a toast and keep the session. Centralize so each page does not re-implement the catch.
- Disposition: `ask-first` (changes error semantics and the logout/redirect behavior).

### [Medium] Dead/placeholder Notifications UI ships as if real
- Location: `frontend/src/app/dashboard/settings/page.tsx:733-783` (three `ToggleRow`s, all `disabled`, "Coming soon").
- What & why: Three notification toggles render as interactive-looking switches but are hardcoded `enabled={false} disabled`. They do nothing. This is incomplete feature surface presented in the product UI.
- Recommendation: Either gate behind a feature flag / remove until implemented, or keep but clearly mark as not-yet-available (the "Coming soon" caption helps but the switches still read as actionable).
- Disposition: `ask-first` (product decision).

### [Medium] Broken link to a non-existent route `/docs/client-lane`
- Location: `frontend/src/app/dashboard/settings/page.tsx:601-611`.
- What & why: "How to schedule from the client lane" links to `/docs/client-lane`. There is no such route/page in `src/app/` (no `docs/` segment). It is a plain `<a href>` so it will navigate to a 404 inside the SPA.
- Recommendation: Point at the real docs location (e.g. external docs URL) or remove the link until the page exists.
- Disposition: `auto-fix-safe` if the correct URL is known; otherwise `ask-first`.

### [Medium] `next.config.ts` sets no security headers (CSP/HSTS/X-Frame-Options)
- Location: `frontend/next.config.ts:3-7` (empty config).
- What & why: Given tokens live in `localStorage` (Critical above), the absence of a Content-Security-Policy is compounding — there is nothing limiting script injection sources. No `headers()` for CSP, `X-Frame-Options`/`frame-ancestors`, `Referrer-Policy`, or HSTS.
- Recommendation: Add a `headers()` block with a baseline CSP and the standard hardening headers. (Defense-in-depth; does not by itself fix token storage.)
- Disposition: `ask-first` (CSP can break inline styles/Recharts; needs tuning + testing).

### [Medium] Heavy use of inline `style` + JS hover handlers instead of CSS; large client bundles
- Location: pervasive — e.g. `frontend/src/app/dashboard/page.tsx` (~970 lines, all client), `tests/page.tsx` (~1000 lines, all client), `ResultRow.tsx:35-36`, `dashboard/layout.tsx:170-171` (`onMouseEnter`/`onMouseLeave` mutating `style.backgroundColor`).
- What & why: Theming is done by branching `dark ? NEUTRAL_SCALE.dark : NEUTRAL_SCALE.light` in every component and writing hex into inline styles, while `globals.css` *already* defines the same tokens as CSS custom properties (`--color-surface-bg`, etc.) that switch on `[data-theme]`. The duplication means the JS palette and the CSS palette are two sources of truth that must be kept in sync by hand (the comment at `constants.ts:43` acknowledges this). Hover is implemented with imperative DOM mutation rather than `:hover`. Everything is a Client Component, so none of this can be server-rendered or tree-shaken out of the client bundle.
- Recommendation: Prefer the existing CSS variables + Tailwind utilities for theme-driven color and `:hover`; reserve the JS palette only for Recharts (which genuinely needs JS strings, per the constants comment). Convert purely-presentational wrappers (layout shell chrome, badges) toward CSS classes. This is a large refactor — see Simplification.
- Disposition: `ask-first` (broad refactor; must preserve exact rendered output).

### [Low] `ChartTooltip` and `DrillBarChart` use `any` and untyped Recharts props
- Location: `frontend/src/app/dashboard/page.tsx:72` (`function ChartTooltip({ ... }: any)`), `:571` (`data.map((d: any, …)`).
- What & why: `any` defeats `strict` mode locally and hides shape drift in chart data. `tsconfig` has `strict: true`, so these are the only soft spots.
- Recommendation: Type the tooltip props (Recharts exports `TooltipProps`) and the cell datum.
- Disposition: `auto-fix-safe`.

### [Low] Theme provider returns `null` until mounted — full blank-screen flash on first paint
- Location: `frontend/src/lib/theme.tsx:39` (`if (!mounted) return null;`).
- What & why: Because `ThemeProvider` wraps the entire app in `layout.tsx`, returning `null` before the mount effect runs means the whole app renders nothing on the server/first client paint, then pops in. This avoids a wrong-theme flash but causes a blank flash and harms LCP. The standard App Router pattern is an inline `<script>` in the layout that sets `data-theme` before hydration, so children render immediately.
- Recommendation: Set the theme attribute via a small blocking inline script in `layout.tsx` (`<head>`) reading `localStorage`, and render children unconditionally.
- Disposition: `ask-first` (changes first-paint behavior; inline script interacts with any future CSP).

### [Low] Duplicated `extractTable`/`extractColumns` and the non-metric key set
- Location: `frontend/src/app/dashboard/page.tsx:712-718`, `frontend/src/app/dashboard/tests/page.tsx:20-28`, and the inlined filter `["table","column","columns","query"]` at `tests/page.tsx:213-215` which duplicates `NON_METRIC_KEYS` in `frontend/src/lib/error-model.ts:6-8`.
- What & why: Same extraction/filter logic copy-pasted across pages with subtle differences (the tests page filter omits `expected_columns` that `error-model.ts` includes). Drift risk.
- Recommendation: Move `extractTable`/`extractColumns` and the config-key filter into `lib/` (alongside `error-model.ts`) and reuse.
- Disposition: `auto-fix-safe` (pure extraction; verify the `expected_columns` discrepancy is intentional before unifying — that part is `ask-first`).

### [Low] `AnimatedNumber` interval and toast timer are correct, but worth noting; `prefers-color-scheme` block is dead
- Location: `frontend/src/app/dashboard/page.tsx:54-68` (interval cleaned up correctly); `frontend/src/components/Toast.tsx:24` (timer cleared on replace/dismiss correctly); `frontend/src/app/globals.css:90-95`.
- What & why: No leak in the animator or toast (both clean up). However the `@media (prefers-color-scheme: dark)` block in `globals.css` only sets `--background`/`--foreground`, which the explicit `[data-theme]` system overrides everywhere — it is effectively dead and can mislead.
- Recommendation: Remove the dead media block or wire it into the no-JS default; leave the timers as-is.
- Disposition: `auto-fix-safe` (CSS dead-code removal).

### [Low] Misleading `AGENTS.md` "modified Next.js" instruction
- Location: `frontend/AGENTS.md` (referenced via `frontend/CLAUDE.md`).
- What & why: It states the repo uses a Next.js with breaking changes and instructs reading `node_modules/next/dist/docs/`. `node_modules` is not installed and that docs path does not exist; the source uses standard, current App Router APIs only (`next@16.2.3`, `react@19.2.4`). Following it would waste effort or invent non-existent APIs.
- Recommendation: Correct or delete the instruction; pin the real Next/React versions and link upstream docs.
- Disposition: `ask-first` (doc/process change).

## Simplification & structure

- Centralize data fetching. Three components fetch `/api/v1/results` independently
  (`run-context.tsx:83`, `dashboard/page.tsx:138`, `history/page.tsx:94`) with three different
  limits and no sharing. A single `useResults`/context-provided results array (one limit,
  abortable, keyed on `lastCompleted`) would remove the largest correctness risk and a lot of
  duplicate code. This is the biggest single simplification opportunity.
- Collapse the dual theme palette. `NEUTRAL_SCALE` (JS) and the `globals.css` custom properties
  encode the same hexes twice (`constants.ts:43` admits it). Drive presentation from the CSS
  variables / Tailwind utilities and keep the JS palette only for Recharts. This also removes the
  `dark ? …dark : …light` branch repeated in nearly every component.
- `dashboard/page.tsx` is ~970 lines and `tests/page.tsx` ~1000 lines, each holding the page plus
  many sub-components (charts, tables, cards, the create form, YAML editor). Extract the
  drill-down chart machinery and `ResultsTable`/`DetailCard` into `components/`, and the
  `CreateTestForm`/`YamlEditor`/`buildYamlPreview` into their own modules. The five drill-state
  variables in the dashboard (`selectedType`, `selectedTable`, `selectedTableFirst`,
  `selectedTypeSecond`, plus `drillMode`) and the parallel `type`/`table` chart-data memos are a
  state machine that would be far clearer as a single reducer.
- Lift `extractTable`/`extractColumns` and the non-metric key filter into `lib/error-model.ts`
  (see Low finding) so Dashboard and Tests share one definition.
- `buildYamlPreview` (`tests/page.tsx:595`) re-implements the backend's YAML serialization in the
  client and must stay in lockstep with `_db_test_to_yaml_dict`. Note it as a known coupling; if
  the API can return a preview, prefer that over duplicating serialization logic.

## Test gaps & proposed tests

There are **no tests at all**: `vitest` + Testing Library are in `devDependencies` and
`package.json` declares `test`/`test:run` scripts, but there are zero `*.test.ts(x)` files and no
`vitest.config.*`. The pure `lib/` functions are the highest-value, lowest-cost place to start,
and they should be locked down *before* any refactor (especially the data-fetch consolidation and
theme-palette work).

Proposed tests, in priority order (write before refactoring):

1. `lib/run-views.ts` — `buildRunViews`:
   - results bucketed correctly by `run_id`; results with `run_id == null` dropped (`:18`).
   - runs returned newest-first by `id` regardless of input order (`:23`).
   - a FAILED run with zero matching results still appears with empty `results` and zeroed counts.
   - results referencing an unknown run are dropped.
2. `lib/format.ts`:
   - `countByStatus` tallies each status and `total === results.length` including unknown statuses.
   - `latestRunResults` prefers `run_id` grouping; falls back to `run_at` when `run_id` is null
     (`:31-33`); returns `[]` for empty input.
   - `formatMetricValue` renders (0,1) as a percentage, `>=1` with locale grouping, passes
     non-numbers through, and the boundary `1` and `0` cases (`:40`).
3. `lib/time.ts`:
   - `parseServerTime` appends `Z` when unzoned and leaves zoned strings untouched (`:14`).
   - `formatRunTimeShort` returns "Now" under 10s, `HH:mm` same-day, `MM/DD/YY` prior day; returns
     "" for invalid input (`:34`). Use fake timers / fixed `Date.now`.
4. `lib/error-model.ts` — `failureKind` maps FAILED/ERROR/SKIPPED/other; `metricEntriesOf` filters
   `NON_METRIC_KEYS` and tolerates missing `metrics`.
5. `lib/constants.ts` — `formatConfigKey` title-cases snake_case, handles empty segments and
   non-snake input; assert `TYPE_PILL_COLORS`/`TYPE_LABELS` key sets match (8 entries, no drift).
6. `lib/auth.tsx` (component test): login stores expected shape; corrupt `localStorage` JSON is
   cleared without throwing (`:34`); `logout` clears state and storage. This pins behavior before
   any move off `localStorage`.
7. `lib/run-context.tsx` (component test with fake timers + mocked `getRun`): polling stops on
   COMPLETE/FAILED and clears the interval; a superseded `runId` does not let an old tick write
   stale status (covers the High race finding once fixed).
8. Component tests for shared UI: `StatusBadge`/`SeverityBadge`/`TypePill`/`StatusDot` render the
   right label/color and fall back for unknown keys; `RunFailureBanner` renders only when FAILED
   and shows reason/at_test/progress; `ResultRow` toggles `aria-expanded` on Enter/Space.

Also add a minimal `vitest.config.ts` with the `@` path alias and jsdom environment, and a
`setupTests` importing `@testing-library/jest-dom`, since none exist yet.

## Notes on the "no behavior change" constraint

- `auto-fix-safe` items above are limited to: suppressing writes from superseded/aborted effects
  (the *intended* behavior), type tightening (`any` → typed), and dead-code (CSS media block,
  duplicate helpers) — none change observable output.
- The unification of `extractColumns`/non-metric keys is only safe if the `expected_columns`
  discrepancy between `tests/page.tsx:213` and `error-model.ts:7` is confirmed intentional; flag
  before merging.
- Token-storage, error/redirect semantics, data-fetch consolidation, theme first-paint, and CSP
  all change behavior and are marked `ask-first`.

## Sources (token-storage benchmark)

- [Stop Using LocalStorage for JWTs in Your SPA (2025)](https://medium.com/lets-code-future/stop-using-localstorage-for-jwts-in-your-spa-heres-the-safer-smarter-alternative-in-2025-ece409045978)
- [Secure JWT Storage: Best Practices — Syncfusion](https://www.syncfusion.com/blogs/post/secure-jwt-storage-best-practices)
- [JWT Token Storage Strategy: Cookie vs LocalStorage & XSS](https://openillumi.com/en/en-jwt-token-storage-strategy-cookie-localstorage-xss-security/)
- [The Developer's Guide to JWT Storage — Descope](https://www.descope.com/blog/post/developer-guide-jwt-storage)
