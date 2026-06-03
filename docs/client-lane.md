# Client-Lane Runbook

The Aegis platform offers two scheduling lanes:

- **Website lane** — the hosted scheduler on Railway triggers runs for cloud-reachable
  database profiles (PostgreSQL, MySQL, Snowflake without an IP allowlist). You manage
  schedules from the Settings page.
- **Client lane** — your own environment (Airflow, cron, or any scheduler) runs the
  engine and posts results to the hosted dashboard. Use this when the hosted runner
  cannot reach your database.

This runbook covers the client lane.

---

## When to use the client lane

Use the client lane when your data is not reachable from the hosted Railway runner:

- **Local SQLite databases** — a file on disk is never reachable from a remote runner.
- **On-premises or private-network databases** — databases behind a corporate firewall or
  VPN that the Railway runner cannot reach.
- **Snowflake instances with an IP allowlist** — Railway egress IPs are not static and
  cannot be reliably added to a Snowflake network policy. See the
  [Snowflake IP allowlist note](#snowflake-ip-allowlist) below.
- **MSSQL (SQL Server)** — the hosted engine image does not include the system ODBC
  libraries required by `pyodbc`. Run MSSQL checks from your own environment where you
  control the driver installation.

The dashboard ingests run results from both lanes via the same REST API — there is no
difference in what you see.

---

## Self-run the engine against the hosted dashboard

You only need two things: an `AEGIS_API_KEY` and a `database_connection.yaml`. No
`aegis/config.yaml` is required — the CLI defaults `api_url` to the hosted dashboard
automatically.

### 1. Install the engine

Install the `aegis-dq` package with the extras matching your database type:

```bash
# PostgreSQL
pip install "aegis-dq[postgres]"

# MySQL / MariaDB
pip install "aegis-dq[mysql]"

# Snowflake
pip install "aegis-dq[snowflake]"

# MSSQL (requires unixodbc + Microsoft ODBC driver on the host)
pip install "aegis-dq[mssql]"

# All supported cloud drivers
pip install "aegis-dq[all-db]"
```

### 2. Set AEGIS_API_KEY

Add your API key to a `.env` file in your project directory (or export it directly):

```
AEGIS_API_KEY=<your-api-key>
```

Your API key is displayed once when you create your account via `POST /api/v1/clients`.
It is stored as a hash — retrieve it from the Railway Variables for the `api` service if
you have not saved it.

### 3. Provide your database_connection.yaml

Create `aegis/database_connection.yaml` with your connection profile. Secrets are
referenced as `${ENV_VAR}` — never hardcoded:

```yaml
my_warehouse:
  type: snowflake
  account: org-myaccount
  database: ANALYTICS
  username: ${SNOWFLAKE_USER}
  password: ${SNOWFLAKE_PASSWORD}
  warehouse: COMPUTE_WH
  role: ANALYST

my_postgres:
  type: postgresql
  host: ${DB_HOST}
  port: 5432
  database: analytics
  username: ${DB_USER}
  password: ${DB_PASSWORD}
```

Add the corresponding variables to your `.env`:

```
SNOWFLAKE_USER=myuser
SNOWFLAKE_PASSWORD=mypassword
DB_HOST=your-postgres-host.com
DB_USER=readonly_user
DB_PASSWORD=yourpassword
```

No `aegis/config.yaml` is needed. The CLI always talks to the hosted dashboard at
`https://api.aegis-dq.com` — the API URL is fixed and not a client-facing setting.

### 4. Push your profile and run

```bash
# Upload your connection profile to the dashboard
aegis push

# Trigger a run (pass --profile; defaults to "dev" if omitted)
aegis run --profile my_warehouse
```

Results appear on the dashboard immediately.

---

## Schedule from your own environment via AegisDQOperator

For recurring runs, use the `AegisDQOperator` in an Airflow DAG. The operator calls the
Aegis API to trigger a run and polls for completion.

### Prerequisites

Install the Airflow extra:

```bash
pip install "aegis-dq[airflow]"
```

Set these variables in your Airflow environment (or `.env`):

```
AEGIS_API_URL=https://api.aegis-dq.com
AEGIS_API_KEY=<your-api-key>
```

### Example DAG

```python
from datetime import datetime
from airflow import DAG
from aegis_dq.operators.airflow_operator import AegisDQOperator

with DAG(
    dag_id="aegis_daily_checks",
    start_date=datetime(2026, 1, 1),
    schedule_interval="0 6 * * *",  # daily at 06:00 UTC
    catchup=False,
) as dag:
    run_checks = AegisDQOperator(
        task_id="run_aegis_checks",
        profile="my_warehouse",
    )
```

The operator uses `AEGIS_API_URL` and `AEGIS_API_KEY` from the environment. No DAG code
change is needed if you rotate the API key — update the Airflow variable or secret.

For profiles that cannot be reached from the website lane (SQLite, on-prem, Snowflake
behind an IP allowlist), this is the recommended scheduling approach.

---

## Snowflake IP allowlist

If your Snowflake account enforces a network policy (IP allowlist), the hosted Railway
scheduler cannot reliably reach it. Railway egress IPs are not static — they can change
with platform updates and cannot be added to a Snowflake network policy in a stable way.

Options:

1. **Use the client lane** (this runbook). Your Airflow workers or local machines
   already have allowlisted IPs; schedule from there using `AegisDQOperator`.
2. **Remove the IP restriction for the Aegis service account.** If the account is
   read-only and scoped to only the data quality role, this reduces the risk surface.
   Consult your Snowflake administrator.

The hosted scheduler will fire the run and it will fail with a clear error in run
history if the Snowflake instance is unreachable. No silent failures.

---

## Reference

| What | Where |
|------|-------|
| Full deploy guide | [DEPLOY.md](../DEPLOY.md) |
| Hosted scheduler caveats | [DEPLOY.md — Hosted scheduler](../DEPLOY.md#hosted-scheduler) |
| Connection profile format | `aegis/database_connection.yaml` (scaffolded by `aegis init`) |
| API key management | `POST /api/v1/clients` response; stored in Railway Variables |
