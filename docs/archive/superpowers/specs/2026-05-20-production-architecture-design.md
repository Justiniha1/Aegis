# Comet — Production Architecture & Distribution Design

**Date:** 2026-05-20
**Status:** Approved
**Supersedes:** `2026-05-18-airflow-integration-design.md` (earlier draft — this document replaces it)

---

## Context

Comet has a first potential client who wants to use it in Airflow. The goal is to get a production-ready version in front of them within 3 weeks. This document covers the full production architecture: what Comet hosts, what the client installs, how everything connects, and the delivery order.

---

## Hosting Model

**One shared instance to start.** All clients share one hosted deployment, separated by `client_id` in the database. No per-client deployments. When there are enough clients to justify it, revisit.

**Client creation is manual for now.** No self-service signup page. You create clients via script and email them credentials. Self-service signup is an important future milestone — design for it, but don't build it yet.

---

## Infrastructure

```
Client's machine
  comet-dq (pip package — CLI only, no engine)
    comet/
      config.yaml              ← API URL, default profile (no secrets)
      test_definitions.yaml    ← test definitions, syncs with dashboard
    .env                       ← COMET_API_KEY (gitignored)

  comet push / pull / run      ← CLI calls the Comet API, nothing runs locally

Comet infrastructure (Railway + Vercel)
  app.comet-dq.com  →  Vercel     (Next.js frontend)
  api.comet-dq.com  →  Railway    (FastAPI + engine code, same container)
                    →  Railway    (Postgres — stores tests, results, credentials)
```

**The engine runs on Railway, not on the client's machine.** The client's laptop can be off. Nothing about Comet requires the client to keep a machine running.

**DB credentials** are entered once in the dashboard Settings page, stored encrypted in Postgres on Railway. The engine reads them at run time. This is the standard model for data SaaS tools (Fivetran, dbt Cloud, Airbyte Cloud).

**Requirement:** The client's database must be reachable over the internet. This is true for all cloud databases (Snowflake, RDS, Redshift, BigQuery, Postgres on any cloud provider). On-prem databases behind a private firewall are not supported in v1.

**Database:** Postgres on Railway for production. SQLite stays for local development only. The switch is a `DATABASE_URL` env var change — the SQLAlchemy abstraction already supports both.

**Domain:** `comet-dq.com` (not yet registered — reserve before deployment).

---

## Client-Side Setup — `comet-dq` Package

The CLI is a sync tool and a remote trigger. It does not run the engine locally.

### Installation

```bash
pip install git+https://github.com/your-org/comet.git  # private beta
# pip install comet-dq                                  # once on PyPI
```

### `comet init` creates

```
comet/
  config.yaml              ← API URL, default profile (version-controlled, no secrets)
  test_definitions.yaml    ← all test definitions (version-controlled)
  profiles/
    dev.yaml               ← dev DB connection label (actual credentials in dashboard)
    production.yaml        ← prod DB connection label (actual credentials in dashboard)
.env                       ← COMET_API_KEY (gitignored — never in comet/)
```

`config.yaml` example:
```yaml
api_url: https://api.comet-dq.com   # or set COMET_API_URL env var
default_profile: production
```

### CLI commands

```bash
comet init                      # scaffold the comet/ directory above
comet push                      # upload local test_definitions.yaml to dashboard
comet pull                      # download current tests from dashboard to local file
comet run                       # trigger a run on Comet servers via API
comet run --profile production  # run one profile only
comet run --suite daily_checks  # run one named suite only
comet status                    # print last run summary (pass/fail counts)
```

### Bidirectional sync

`test_definitions.yaml` stays in sync with the dashboard in both directions — the same pattern that already exists in the app today:

- **Local → dashboard:** Client edits YAML in their IDE → `comet push` → API parses and saves to Postgres → dashboard reflects changes immediately
- **Dashboard → local:** Client edits tests in the UI → `comet pull` → CLI fetches YAML from API → writes to local file

When settings are updated in the dashboard (schedule, default profile), `comet pull` writes them back to `config.yaml`. *(Scheduler UI is a future milestone — infrastructure supports it from day one.)*

---

## How a Run Works (End-to-End)

### Triggered from the UI

1. Client clicks "Run" on the dashboard
2. Frontend calls `POST /api/v1/runs` with `{profile, suite}`
3. API creates a run record in Postgres (`status=QUEUED`) and fires a background task
4. Background task (running on Railway):
   - Loads test definitions from Postgres for this client
   - Loads and decrypts connection credentials from Postgres
   - Instantiates the engine and runs all enabled tests against the client's DB
   - Updates status: `QUEUED → RUNNING → COMPLETE` (or `FAILED`)
   - Stores all results in Postgres
5. Frontend polls `GET /api/v1/runs/{run_id}` every 2 seconds
6. On `COMPLETE` — dashboard re-fetches results and updates

Client's machine plays no role after clicking the button.

### Triggered from the CLI

`comet run` calls `POST /api/v1/runs` — identical flow above. CLI polls and prints progress to the terminal. Returns exit code `0` (all pass) or `1` (any failures) — useful for CI pipelines.

### Triggered from Airflow

`CometRunOperator` calls `POST /api/v1/runs` — identical flow above. The Airflow server only orchestrates timing; execution happens on Railway. Operator polls until complete, raises `AirflowException` on failure.

---

## Airflow Integration — `airflow-provider-comet`

Separate pip package following the Apache Airflow provider naming convention.

### Installation

```bash
pip install airflow-provider-comet
```

### Architecture: Hook + Operator

```
CometHook
  └── handles: Airflow Connection lookup, auth headers, HTTP to api.comet-dq.com

CometRunOperator
  └── uses: CometHook
  └── does: POST /api/v1/runs → poll GET /api/v1/runs/{id} → raise on failure
```

### Client configuration

Credentials go in Airflow's **Connections UI** — not env vars. This is the Airflow-native pattern clients expect:

```
Connection ID:   comet_default
Connection Type: HTTP
Host:            api.comet-dq.com
Password:        <COMET_API_KEY>
```

### Operator usage

```python
from comet.airflow.operators import CometRunOperator

dq_check = CometRunOperator(
    task_id="data_quality_gate",
    suite="daily_checks",      # optional — omit to run all enabled tests
    profile="production",
    fail_on="critical_only",   # "any_failure" | "critical_only"
    timeout=600,
    conn_id="comet_default",   # default if omitted
)
```

### Operator behaviour

1. POST `/api/v1/runs` with `{profile, suite}` → receives `run_id`
2. Poll `GET /api/v1/runs/{run_id}` every 5 seconds
3. On `COMPLETE`: check results against `fail_on` — raise `AirflowException` if threshold exceeded
4. On `FAILED`: raise `AirflowException` with the engine's error message
5. On timeout: raise `AirflowException`
6. Push `run_id` and result summary to XCom for downstream tasks

### Sample DAGs (ship with the package)

**Scheduled daily check:**
```python
with DAG("comet_daily_check", schedule="0 6 * * *", ...) as dag:
    CometRunOperator(task_id="dq_check", profile="production", fail_on="any_failure")
```

**Pipeline gate (after dbt):**
```python
with DAG("etl_with_dq_gate", schedule="0 6 * * *", ...) as dag:
    dbt_run = BashOperator(task_id="dbt_run", bash_command="dbt run")
    dq_gate = CometRunOperator(task_id="dq_gate", profile="production", fail_on="critical_only")
    dbt_run >> dq_gate
```

**v1 is synchronous polling.** Deferrable operator is the right long-term upgrade — ship sync first.

---

## Authentication & Security

### How auth works end-to-end

Two separate auth paths — one for humans, one for machines:

```
Human (dashboard user)
  POST /api/v1/auth/login  {email, password}
  ← JWT token (24h expiry)
  All subsequent requests: Authorization: Bearer <token>

Machine (CLI or Airflow operator)
  All requests: Authorization: Bearer <api_key>
  API key created when account is created (manual setup)
  Client sees their API key in Settings → copies into .env / Airflow Connection
```

Both paths are handled by the existing `get_client_any_auth` dependency. Already implemented.

### Production security requirements

**JWT secret key — critical fix before deployment.**
Current code generates a random `JWT_SECRET_KEY` at import time if the env var is absent — every Railway deploy invalidates all sessions. Set `JWT_SECRET_KEY` as a fixed Railway environment variable:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

**Connection credential encryption.**
Client DB credentials stored in Postgres must be encrypted at rest. Use Fernet symmetric encryption (`cryptography` library). Encryption key stored as a Railway environment variable — never in code or the database.

**HTTPS** — Vercel and Railway provision TLS automatically. No extra work.

**API key in Settings** — client must be able to see (and copy) their API key in the Settings page. Masked by default, revealed on click. Required before first client onboards.

**Password reset** — no reset flow exists. Handle manually for private beta. Add before self-service signup.

**CORS** — currently hardcoded to `localhost:3000`. Update to `https://app.comet-dq.com` via env var before deployment. Keep `localhost:3000` for local dev.

### What the client stores locally

```bash
# .env (gitignored)
COMET_API_KEY=<their key — visible in Settings page>
```

DB credentials are entered in the dashboard, not stored locally.

---

## API Changes Required

**Connection profile storage** — new `ConnectionProfile` model in Postgres. Stores the client's DB connection string, encrypted with Fernet. The engine reads from this model instead of a local YAML file at run time.

**Engine config loading** — `config_loader.py` needs a "load from DB" path. When a run is triggered via the API, the engine loads test definitions and connection info from Postgres rather than local YAML files. The existing local YAML path stays for local development.

**Job queue** — `POST /api/v1/runs` already creates a run record and fires a background task (Phase 2). Needs the engine background task updated to use DB-stored credentials.

**Run status endpoint** — `GET /api/v1/runs/{run_id}` already exists (Phase 2). Must be stable — the CLI and Airflow operator both poll it.

---

## Website — What Needs to Be Built

**Must-have for first client:**

| Item | Status | Notes |
|---|---|---|
| Run from UI (TopBar button wired) | Incomplete — Phase 2 gaps | Backend ready; frontend wiring unfinished |
| Auto-refresh after run completes | Incomplete — Phase 2 gaps | No polling in dashboard/page.tsx |
| Profile chooser before run | Missing | API exists, no UI |
| API key visible in Settings | Missing | Client needs this to configure CLI and Airflow |
| Connection profile management in Settings | Missing | Client enters DB connection string here |

**Deferred (structure for, don't build yet):**

| Item | Notes |
|---|---|
| Scheduler UI in Settings | Set run frequency in the dashboard. Infrastructure ready; UI is future milestone |
| Self-service signup `/register` | Important future milestone — currently manual |
| Public landing page `comet-dq.com` | Pre-login marketing page |
| Empty state / onboarding flow | First login with no tests |
| CLI parity (add/delete tests from terminal) | `comet tests add/list/delete` etc. |
| Deferrable Airflow operator | Upgrade after v1 ships |

---

## Delivery Plan (3 weeks, Airflow first)

| Week | Work |
|---|---|
| **1** | `pyproject.toml` + package structure; `comet init` scaffolding; `comet push/pull/run/status` CLI wired; `ConnectionProfile` model + credential encryption on API; engine config loader updated to read from DB |
| **2** | `CometHook` + `CometRunOperator` + Airflow Connection type; 2 sample DAGs; end-to-end test (install from GitHub → configure in dashboard → trigger from Airflow DAG → watch results appear) |
| **3** | Postgres migration + deploy to Railway + deploy to Vercel; UI fixes (Phase 2 run-trigger gaps + API key in Settings + connection profile UI) |

---

## Decisions

| Decision | Rationale |
|---|---|
| Engine runs on Railway, not client's machine | Clients cannot be required to keep a machine running 24/7. This matches the standard SaaS model (dbt Cloud, Fivetran, Airbyte Cloud). |
| One shared hosted instance | Fastest path; one server to pay for. Revisit when scale or security demands it. |
| Vercel + Railway | Zero-config Next.js on Vercel; Railway gives Postgres + FastAPI in one project; both free to start. Switch to AWS when scale or enterprise compliance demands it. |
| Postgres for production | SQLite can't persist across container restarts on Railway. Config change only — SQLAlchemy abstraction already supports both. |
| DB credentials stored in Comet Postgres (encrypted) | Client has no always-on machine to store credentials. Industry standard for data SaaS. Fernet encryption at rest. |
| Manual client creation for now | One client; no signup page needed yet. Self-service signup is an explicit future milestone. |
| `comet/` directory with profiles/ subdirectory | More than 2 flat files (feels like a real project) but not GX-level complexity. |
| CLI is sync + remote trigger only | No local engine execution. Keeps the CLI simple and removes the need for clients to manage a running process. |
| Airflow Hook + Operator pattern | Apache provider convention; credentials in Airflow Connections UI; clean separation of auth vs. orchestration. |
| v1 synchronous Airflow operator | Deferrable operator is best practice for long runs but adds complexity. Ship sync first, upgrade after client feedback. |
| `comet_default` Airflow Connection ID | Standard provider convention. Clients familiar with other Airflow providers will expect this. |
| GitHub install first, PyPI later | Faster for private beta. Graduate to PyPI after first client onboarding is validated. |
