# Comet Master Audit & Triage

> PROGRESS (updated 2026-06-15): Tier A backend done (8 checks -> `_common.py`,
> `dashboard_api/constants.py`, scheduler print->logging). Frontend dedup candidates
> verified as NON-ISSUES (A6 was unreliable: wrong about zero-tests, node_modules,
> AGENTS.md; the extract helpers are not duplicates; theme palette duplication is
> intentional/documented). **Tier C #1 SQL parameterization: DONE** — C1/C2/H1/H2 fixed
> (`safe_identifier` allowlist + bind params + AST assertion evaluator).
> **Tier C #2 credential/token security: PARTIAL** — H4 (JWT swallow) + H3 (reject literal
> secrets at upload, ${ENV}-only) DONE; C3 (localStorage->cookie) DEFERRED, plan in
> `C3-token-storage-migration.md`.
> **Tier C #4 CLI correctness: DONE (scoped)** — H11 friendly errors (`CometAPIError`)
> across all commands. H10 found to be a NON-BUG (init's type/path sqlite profile is
> valid; the divergent bundled connection_url template is just unused). Client-merge +
> POST-retry skipped (risky / could double-trigger runs). 161 py tests pass.
> Remaining Tier C: concurrency races (H5/H8/H9). Plus deferred C3 + assorted Med/Low.

Branch: `refactor/codebase-audit-cleanup` | Date: 2026-06-15
Source reports: `A1-backend-core.md`, `A2-api-security.md`, `A3-api-routers.md`,
`A4-scheduler-execution.md`, `A5-cli-sdk.md`, `A6-frontend.md`. Baseline: `_baseline.md`.

Goal recap: same functionality, more human-readable, fewer/better-structured files,
following best practices, with bugs/security/incomplete-features found and fixed.
Workflow: tests-first, then refactor; auto-fix safe items, ask first on risky ones.

---

## 1. Headline numbers

| Area | Crit | High | Med | Low |
|---|---|---|---|---|
| A1 backend engine | 2 | 4 | 5 | 6 |
| A2 api security | 0 | 2 | 3 | 3 |
| A3 api routers | 0 | 3 | 4 | 6 |
| A4 scheduler/exec | 0 | 2 | 3 | 5 |
| A5 cli/sdk | 0 | 2 | 5 | 5 |
| A6 frontend | 1 | 3 | 3 | 5 |

Two structural verdicts from the agents worth stating up front:
- The codebase is **not** as over-fragmented as it feels. The API router-per-resource
  split (A3), the scheduler 3-file split (A4), and the CLI command modules (A5) are all
  judged *idiomatic and worth keeping*. The real problem is **duplication**, not file count.
- The genuine consolidation wins are: the 8 builtin checks (A1), the two parallel HTTP
  clients (A5), and the uncoordinated results-fetching on the frontend (A6).

---

## 2. Critical & High findings (the work that matters)

### CRITICAL
- **C1 — SQL identifier injection in all 8 builtin checks** (A1). `table`/`column`/
  `date_column` are f-string-interpolated into SQL with no quoting/allowlisting
  (`backend/tests/builtin/*`). Config can arrive over the network via
  `load_config_from_api`, so this is a real injection surface, not just operator-trust.
- **C2 — `custom_sql` runs `eval()` on a config-supplied assertion** (`custom_sql.py:25`).
  Emptied `__builtins__` is not a real sandbox.
- **C3 — JWT + client identity stored in browser `localStorage`** (`frontend/src/lib/auth.tsx:30,49`).
  XSS-exfiltratable, no expiry/refresh.

### HIGH
- **H1 — `range_check` interpolates min/max unquoted** (`range_check.py:20-31`): second
  injection vector; also breaks on string/date bounds.
- **H2 — `row_count` silently returns all-rows for unsupported dialects** (`row_count.py:4-32`):
  `_date_where` yields empty WHERE on e.g. Snowflake -> silently wrong count, no error.
- **H3 — Connection-config secrets stored in cleartext at rest** (`models.py:80-86`,
  `routers/profiles.py:37-57`). `${ENV}`-only is a convention, not enforced; a literal
  password in uploaded YAML persists in plaintext.
- **H4 — `get_client_any_auth` swallows invalid/expired JWTs** (`auth.py:87-110`):
  `except PyJWTError: pass` conflates bad-credential with no-credential.
- **H5 — Read-modify-write race on `Run.completed_tests`** (`routers/results.py:73-74`):
  concurrent result batches lose increments -> runs stuck "incomplete".
- **H6 — `datetime.utcnow()` deprecated project-wide** (models defaults + 5 routers +
  scheduler). Naive-vs-aware fragility feeding scheduler comparisons. (A3, A4)
- **H7 — Mass-assignment in tests router** (`routers/tests.py:48,74`):
  `TestDefinition(**body.model_dump())` and unconditional `setattr` loop.
- **H8 — Non-atomic active-run guard race** (`scheduler.py:74-85` vs `runs.py:100-117`):
  poller vs manual-trigger can start two concurrent runs for one client. Fix belongs in DB
  (partial unique index).
- **H9 — Scheduler awaits dispatch per row** (`scheduler.py:88-94`): one slow client delays
  dispatch + `next_run_at` advance for all due clients; different concurrency semantics from
  the manual `BackgroundTasks` path.
- **H10 — `comet init` writes a connection template that `push` rejects**
  (`cli/commands/init.py:8-25` uses `type/path`; contract expects `connection_url:`).
  Fresh init -> push uploads an invalid profile.
- **H11 — Raw `requests.HTTPError` surfaced to CLI users** (`cli/api_client.py:11` + all
  commands): users see `401 Client Error...` instead of an actionable message.
- **H12 — Run-polling stale-closure race** (`frontend/src/lib/run-context.tsx:94-119`):
  superseded effect ticks write stale status, double-bump `lastCompleted`, leak an interval.
- **H13 — Uncoordinated results fetching** (frontend): 3 `/results` fetches with conflicting
  limits (500/500/1000), no cancellation; layered on a logout-on-any-error redirect path
  (redirect-loop risk; also H: 401-vs-network not distinguished).

---

## 3. Cross-cutting themes (fix once, applies everywhere)

1. **Secrets handling** — plaintext creds at rest (H3), world-readable `.env` from CLI (A5),
   JWT in localStorage (C3). Treat as one security workstream.
2. **SQL construction** — no parameter-binding path in `execute_query`
   (`database_connector.py:100`) forces every check to string-format (C1/H1/H2).
3. **`datetime.utcnow()`** — single sweep to timezone-aware UTC, test-guarded (H6).
4. **`delete_client` orphans** `Run`/`Schedule`/`ConnectionConfig` rows (A2 + A3): breaks on
   Postgres FKs, leaves schedules firing + cleartext creds behind.
5. **Duplication to consolidate** — 8 builtin checks share an identical `_error`/result/scalar
   plumbing (A1); two HTTP clients (A5); frontend results fetching + dual theme palette (A6);
   tenant-404 fetch boilerplate across routers (A3).

---

## 4. Disposition triage

### Tier A — `auto-fix-safe` (behavior-preserving, low risk; do under green tests)
- Extract `backend/tests/builtin/_common.py` (`_result/_error/_scalar_count`) — pure dedup.
- De-duplicate the 8-test-type frozenset + tenant-404 fetch into `queries.py`/`constants.py`.
- Replace scheduler `print()` with `logging` (A4).
- Remove dead code: `rstrip("/")` (`connection_source.py:97`), unused `interval_seconds`/`cron`
  surface (A4), dead `prefers-color-scheme` CSS + duplicated extract helpers (A6).
- Fix misleading `frontend/AGENTS.md` + broken `/docs/client-lane` link (A6).
- Add explanatory comment on SHA-256 API-key hashing rationale (A2).
- Collapse duplicated theme palette to one source (A6).

### Tier B — `test-guarded` (mechanical but behavior-adjacent; write characterization tests first)
- `datetime.utcnow()` -> `datetime.now(UTC)` sweep (H6) — verify comparisons unchanged.
- Consolidate the two HTTP clients so CLI reuses the SDK client (A5) — preserve timeouts.
- Centralize frontend results fetching into one abortable hook (H13) — preserve rendered data.

### Tier C — `ask-first` (changes behavior / security / interfaces / deploy — needs your sign-off)
- SQL parameterization + identifier allowlisting (C1/H1/H2) — changes query construction.
- `custom_sql` eval() replacement (C2) — may restrict allowed assertions.
- Encrypt connection creds at rest OR enforce `${ENV}`-only at upload (H3).
- JWT hardening: stop swallowing errors (H4), add claims/revocation/logout (A2 Med).
- Move browser token off `localStorage` to httpOnly cookie / in-memory + refresh (C3).
- DB-level active-run guard / partial unique index (H8) + async dispatch fan-out (H9).
- `Run.completed_tests` race fix (H5) — needs atomic update or row lock.
- Mass-assignment lockdown in tests router (H7).
- `delete_client` cascade (theme 4) — data-model change.
- `comet init` template fix (H10) + CLI HTTPError UX (H11) + retry/backoff (A5).
- CORS tightening + JWT-secret hard-fail in prod (A2).
- Frontend CSP/security headers in `next.config.ts` (A6).

---

## 5. Test-coverage reality (corrected)

Baseline (verified by running suites): **Python 83 passed / 1 skipped; frontend 27 passed
across 6 files.** (A6's "zero frontend tests" claim is wrong — `*.test.tsx/*.test.ts` exist
for ErrorDetail, RunFailureBanner, Toast, error-model, run-views, time.)

Coverage is nonetheless **partial**. Untested before-refactor priorities:
- Backend: all 8 builtin checks, `TestEngine`, both config loaders, `result_handler`
  (np.int64 sanitization), `row_count` silent-all-rows behavior. (~35 tests proposed, A1)
- API: results/runs/clients/auth/tests routers (profiles+schedules already covered). (A3)
- Scheduler: poller-vs-trigger race, multi-client tick, overdue roll-forward, mid-run crash,
  persist-failure-still-COMPLETE. (9 tests proposed, A4)
- CLI/SDK: CLI poll-to-completion render, `init` scaffold, HTTP-error UX. (9 tests, A5)
- Frontend: run-context polling, auth flow, results fetching, the untested components/pages.

These characterization tests are the safety net that makes the Tier B/C refactors safe.

---

## 6. Recommended sequence

1. **Tests-first:** write the high-value characterization tests above (lock current behavior).
2. **Tier A** auto-fixes under green tests (atomic commits).
3. **Tier B** test-guarded refactors.
4. **Tier C** one workstream at a time, each presented for approval before changes.
   Suggested order by risk/value: (a) SQL parameterization, (b) credential/token security,
   (c) scheduler race + completed_tests race, (d) CLI correctness, (e) remaining hardening.
5. Re-run both suites, diff against baseline, confirm functionality unchanged.
