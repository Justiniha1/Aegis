# Comet — Project Summary

> Product/brand: **Comet** ("Comet-dq" for the package and the login wordmark; "Comet"
> everywhere else). The repository root folder is still named `Aegis` on disk and the live
> API hostname is still `aegis-production-fa56.up.railway.app` — see "Naming notes" below.

## 1. What Comet is
Comet is a multi-tenant data-quality platform. It runs configurable data-quality checks
against a client's database — on demand or on a schedule — and surfaces results in a web
dashboard. Target users are data operators and client teams who own a dataset's health;
they open Comet to answer one question fast: *"is my data OK right now, and if not, what
broke?"* Design ethos: calm operator precision — legible, status-first, WCAG AA.

Two execution lanes:
- **Hosted/website lane** — the dashboard's runner executes checks against cloud-reachable
  client databases.
- **Client-side lane** — the client runs the engine on their own infrastructure (e.g.,
  Airflow via the SDK) and posts results back to the hosted dashboard.

## 2. Architecture
Five codebases in one repo (~5,500 LOC Python + a Next.js frontend), deployed on Railway
(API service + managed Postgres + frontend):

| Component | Role |
|---|---|
| `backend/` | Data-quality engine — config, DB connections, the 8 checks, result reporting |
| `dashboard_api/` | Hosted FastAPI service — multi-tenant API, auth, storage, scheduler, run executor |
| `cli/` | The `comet` CLI (Typer) — `init/push/pull/run/status` |
| `comet_dq/` | Public Python SDK + Airflow operator |
| `frontend/` | Next.js 16 / React 19 / TypeScript dashboard |

## 3. Components in detail
- **Engine (`backend/`):** `config_loader` (DQFConfig/TestDefinition, YAML-or-API loading,
  `${ENV}` resolution), `database_connector` (`build_connection_url` for
  sqlite/postgres/mysql/mssql/snowflake + `DatabaseConnector`), `test_engine`
  (orchestration, dynamic check import by type, fail-safe `on_result` callback),
  `result_handler` (dashboard reporting + numpy sanitization), and the 8 checks sharing
  `tests/builtin/_common.py`.
- **Dashboard API (`dashboard_api/`):** `models` (Client, Run, TestResult, TestDefinition,
  ConnectionConfig, Schedule), `auth` (API-key for engine, JWT for frontend, bcrypt),
  routers (`auth_routes`, `clients`, `profiles`, `results`, `runs`, `schedules`, `tests`),
  `scheduler` (APScheduler poller), `run_executor` (engine bridge), `schedule_logic`,
  `connection_source`, `queries`, `limiter`, `constants`, `runtime_checks` (production boot
  guardrails), `alerts` (webhook failure alerting), and `main` (wiring + lifespan).
- **CLI/SDK:** the `comet` CLI with `CometClient`; SDK `CometAPIClient` + `run_checks()` +
  Airflow operator. Two distinct credentials — a server-side JWT signing secret vs a
  per-client API key.
- **Frontend:** App Router (`login`, `dashboard` + `history`/`settings`/`tests`),
  components (StatusBadge, ResultRow, StatusFooter, TopBar, Toast, ErrorDetail,
  RunFailureBanner), lib (api, auth, run-context, theme, etc.). 27 Vitest tests.

## 4. End-to-end flow
Operator provisions a client -> client receives an API key + dashboard login -> `comet init`
scaffolds config -> `comet push` uploads tests + connection profiles -> the engine runs
checks (hosted or client-side) -> results POST to the API -> the dashboard shows
health/history -> schedules auto-trigger runs and alert the client on failure.

## 5. The 8 builtin checks
`null_check`, `duplicate_check`, `unique_check`, `range_check`, `row_count`
(daily/weekly/monthly timeframes), `schema_check` (column presence + type aliasing),
`relationship_check` (FK orphans), `custom_sql` (query + assertion). Uniform result dict:
`test_id, name, type, status (PASSED/FAILED/ERROR/SKIPPED), severity, metrics, message`.

## 6. Hardening and quality work done
Performed as an audit -> refactor -> launch-readiness program on branch
`refactor/codebase-audit-cleanup`. Highlights:
- **SQL injection closed** across all 8 checks (identifier allowlist + bound parameters);
  `custom_sql`'s `eval()` replaced by a restricted AST evaluator.
- **Credential handling**: connection YAML rejects literal secrets at upload (`${ENV}`-only);
  JWT auth no longer silently swallows invalid tokens.
- **Production boot guardrails** (`runtime_checks`): in production the API refuses to start
  without a real JWT secret, a persistent (non-SQLite) database, and an admin token.
- **Client provisioning** gated behind an admin token (+ `Scripts/provision_client.py`).
- **Concurrency**: one-active-run-per-client enforced by a DB partial unique index; the
  run progress counter increments atomically.
- **Failure alerting** (webhook): scheduled runs that fail or find failing tests notify the
  client; per-client webhook + `PATCH /api/v1/clients/me`. Email (Resend) is stubbed for later.
- **Data residency** (connected, read-only "agentless" model): checks emit only
  metadata/metrics; `custom_sql` emits pass/fail only (no result value); `schema_check`
  reports only the client-declared columns; read-only least-privilege credentials are required.
  See `data-residency.md` and `connecting-your-database.md`.
- **Dedup/readability**: the 8 checks share `_common.py`; shared API constants; friendly CLI
  error messages.
- Test suite grew from 83 to **191 passing** (+1 skipped); frontend 27 passing.

The full audit and triage are archived in `docs/archive/audit/` (`MASTER-AUDIT.md` + per-area reports).

## 7. Current state and what remains
- All work is on `refactor/codebase-audit-cleanup` (review/commit/merge at your discretion);
  full suite **191 passing, 1 skipped**; frontend 27 passing.
- **To launch:** set the Railway environment variables (see `LAUNCH.md`) and have each client
  provision read-only, least-privilege credentials (see `connecting-your-database.md`).
- **Next up (planned):**
  - Redesign `custom_sql` output handling (currently emits pass/fail only — no value surfaced).
  - Optional code-level read-only enforcement (read-only connection mode + reject write SQL in
    `custom_sql`) as defense-in-depth on top of the read-only credential requirement.
  - Frontend Settings field for the alert webhook; Resend email channel.
  - Onboarding hardening: key-pair/OAuth auth option; dedicated service-user guidance.
- **Deferred (non-blocking):** agent / in-VPC tier (the strict "data never leaves" option;
  plan in `docs/archive/audit/C3-token-storage-migration.md`), Alembic migrations,
  `delete_client` orphan cleanup, scheduler dispatch parallelism, CSP/accessibility polish.

## 8. Naming notes (Aegis -> Comet)
The product was renamed from Aegis to Comet. Two things intentionally keep the old name:
- **Live API hostname** `aegis-production-fa56.up.railway.app` (in `comet_dq/_client.py` and
  `cli/config.py`) — it maps to the real Railway service. It only changes if you rename the
  Railway service, then update `DEFAULT_API_URL`.
- **The repo root folder** is still `Aegis\` on disk — rename it in your file explorer / Git
  host when convenient.
