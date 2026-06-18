# Multi-Runner Execution & Per-Profile Scheduling — Design Spec

**Date:** 2026-06-02
**Milestone:** v1.3 (proposed) — delivered as a **single phase**
**Status:** Approved for planning

---

## Problem

Comet can run data-quality checks, but the story for *where the engine runs* and
*how runs get scheduled* is incomplete and inconsistent:

- The hosted dashboard can trigger a server-side run, but the api image only has
  the **Postgres** driver — MySQL/MSSQL generate URLs but can't connect, and
  **Snowflake isn't supported at all** (no dialect, no driver, no URL branch). The
  first real client uses Snowflake.
- There is **no scheduling** except via the client's own Airflow (`CometDQOperator`,
  built in Phases 3–4). A client who just wants "check my Snowflake every morning"
  has no path that doesn't require them to stand up Airflow.
- The Settings page is selector-only and says nothing about *whether* a profile can
  be scheduled, so the capability is invisible and confusing.

## Goals

1. Support all three engine placements (hosted cloud, client's always-on box/Airflow, laptop) with one portable engine.
2. Connect the DB types the product claims to support — **Postgres, MySQL, MSSQL, and Snowflake** — both in the engine and (for cloud-reachable types) in the hosted api image.
3. Add a **hosted scheduler** so cloud-reachable profiles can be scheduled from the website with zero client infrastructure.
4. Make scheduling capability **legible per profile** in the Settings UI, with honest notices that point to the right lane when the website can't schedule a profile.
5. **Simplify client setup:** `api_url` defaults to the hosted dashboard and `comet/config.yaml` is no longer required — a self-running client provides only their API key and their connection definitions.

## Non-Goals / Honest Constraints (do not re-litigate)

- **Laptop-local data + scheduled-while-off is impossible.** For local SQLite (and any
  data on a possibly-off machine) there is **no website scheduler** — run it manually,
  or via the client's own engine/Airflow when the machine is on. No attempt is made to
  schedule it from the hosted side.
- **Dashboard-triggered / website-scheduled runs only reach databases the hosted
  environment can reach** (cloud DBs with credentials). On-prem and local data stay in
  the client lane by design — the hosted side never tunnels into a client network.
- **The Airflow lane is client-owned.** Comet provides the operator + documentation,
  not the scheduler. Results from Airflow runs post up to the dashboard like any other run.

---

## Architecture

### Portable runner + two scheduling lanes

The engine is **one portable runner** (the existing Python package / `TestEngine`).
Wherever it executes, it reaches whatever *that location* can reach and posts results
to the hosted dashboard via the results API. There are two lanes that trigger it:

| Lane | Runs where | Reaches | Scheduled by |
|------|-----------|---------|--------------|
| **Website** (hosted) | The api service (in-process `execute_run`) | Cloud-reachable DBs only (Postgres, Snowflake, cloud MySQL/MSSQL) | The hosted scheduler (this phase) |
| **Client** (self-run) | Client's Airflow / engine / laptop | Anything that host reaches — incl. local SQLite & on-prem | The client's own Airflow / cron |

The **dashboard ingests results from both lanes** — this already works (results post via
the API regardless of trigger source).

### Per-profile capability model

Each connection profile's **DB type** determines whether the *website* lane can schedule
it. This is the simple, legible rule (chosen over an execution-mode model for clarity):

| Profile DB type | Website-schedulable? | Settings UI shows |
|-----------------|----------------------|-------------------|
| Postgres (cloud) | Yes | Real schedule toggle + cron picker |
| Snowflake | Yes (after driver added) | Real schedule toggle + cron picker |
| MySQL / MSSQL (cloud-reachable) | Yes | Real schedule toggle + cron picker |
| SQLite (local file) | No | Locked notice + pointer to the client lane |

> **Note on accuracy:** DB type is a *proxy* for "is this reachable by an always-on hosted
> runner." A SQLite file on a client's always-on server could technically be scheduled by a
> runner there — but that's the client lane (Airflow), not the website. The website rule
> stays type-based for simplicity; the UI notice explicitly names the client lane as the
> path for those cases, so it is never a dead end.

---

## Components & Data Flow (single phase, internal workstreams)

### A. Database driver & dialect coverage

- Extend `backend/core/database_connector.py::build_connection_url` with a `snowflake`
  branch (`snowflake://user:pass@account/db/schema?warehouse=…&role=…`) and confirm the
  existing `mysql`/`mssql` branches.
- Add driver dependencies: `snowflake-sqlalchemy` (Snowflake), `pymysql` (MySQL),
  `pyodbc` + system ODBC (MSSQL) — to the **engine** requirements and, for cloud-reachable
  use, the **hosted api image** (`dashboard_api/requirements.txt` + Dockerfile system libs).
  Consider optional extras so a laptop install stays lightweight.
- Update `database_connection.yaml` reference docs + `comet init` template with a Snowflake
  example using `${ENV}` secrets.

### B. Per-profile capability API + Settings UI

- `GET /api/v1/profiles` (or a sibling endpoint) returns, per profile, a
  `website_schedulable: bool` derived from DB type, plus the resolved `db_type`.
  Secrets never returned (unchanged).
- Settings → Active Environment: for each profile, render either
  (a) a **schedule control** (enable + cron/interval picker) when `website_schedulable`, or
  (b) a **locked notice** with copy + a "How to schedule this yourself" link to the
  Airflow/engine docs.

### C. Hosted scheduler (cloud profiles only)

- New `Schedule` table: `client_id`, `profile`, `cron`/`interval`, `enabled`,
  `last_run_at`, `next_run_at`.
- API: create / update / delete / list schedules (per authenticated client).
- A hosted **scheduler worker** evaluates due schedules and invokes the existing
  `execute_run(...)` server-side run path. Recommended start: **APScheduler in the api
  process** (simplest; no extra service) with a note that it can graduate to a dedicated
  worker/Railway-cron if scale demands. Document the Railway implication (in-process
  scheduler needs the api service always running — it is).
- Credentials resolve the same way server-side runs already resolve them: `${ENV}`
  variables set on the api service, resolved at run time. No new secret storage.
- Guardrails: a schedule for a non-`website_schedulable` profile is rejected by the API
  (defense in depth behind the UI gating).

### D. Airflow / client lane (docs + glue) + CLI config simplification

- **Simplify client config:** `api_url` defaults to the hosted dashboard URL, and the
  `comet` CLI no longer *requires* `comet/config.yaml` to exist. Rationale: `api_url` is a
  constant (your hosted site), not something each client should type or see. A self-running
  client then needs only their `COMET_API_KEY` (identity) + their `database_connection.yaml`
  (their connections); a dashboard-only client never touches a config file at all.
  - `cli/config.py::load_config` no longer `sys.exit(1)` when `comet/config.yaml` is absent —
    it falls back to the built-in default `api_url` and `default_profile`. The file becomes
    an optional override, not a requirement. `comet init` may still scaffold it, but nothing
    breaks without it.
- Document the client lane clearly: point the engine at the hosted instance (just
  `COMET_API_KEY` — `api_url` is automatic), and schedule via `CometDQOperator`.
- The Settings locked-notice links here.
- No new scheduler — this lane is client-owned.

---

## Error Handling

- Unsupported DB type at connection build → clear `Unsupported database type` error
  surfaced into `Run.error_reason` (existing pattern in `run_executor`).
- Missing driver in the hosted image → fail the run with an explicit
  "driver not installed for `<type>` on the hosted runner — use the client lane" reason
  (do not silently hang).
- Hosted-scheduled run whose `${ENV}` creds are unset → `Run.FAILED` with a reason naming
  the missing variable.
- Scheduler worker must never let one failing schedule kill the loop (per the engine's
  existing fail-safe philosophy).

## Testing

- Unit: `build_connection_url` for each DB type incl. Snowflake; `website_schedulable`
  derivation per type.
- API: schedule CRUD; rejection of schedules for non-schedulable profiles; profiles
  endpoint returns the capability flag and never secrets.
- Integration: a hosted-scheduled cloud-Postgres run executes and posts results (sample
  cloud PG or a container); a SQLite profile shows the locked notice and its schedule API
  is rejected.
- Manual/browser UAT: Settings shows toggle vs locked notice correctly per profile;
  scheduled run appears in run history.

---

## Open Decisions (resolve during planning)

1. Scheduler runtime: APScheduler in-process (recommended) vs dedicated worker service vs Railway cron.
2. Schedule granularity exposed to users: simple presets (hourly/daily/weekly) vs raw cron.
3. MSSQL system-ODBC bundling cost in the api image — include now or defer (no client needs it yet)?

## Delivery

Delivered as **one phase** (proposed v1.3 Phase 9: "Multi-Runner Execution & Per-Profile
Scheduling") with internal waves A→D. Route into a v1.3 milestone via `/gsd-new-milestone`.
