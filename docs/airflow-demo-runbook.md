# Airflow Demo Runbook — Hosted DAG-Triggered Run

A live sales demo: an Airflow DAG triggers a real Aegis run on the hosted website
against a seeded demo Postgres. The prospect sees the DAG definition, watches it run
green, then sees the run land in the Aegis dashboard.

## What it proves
"You orchestrate Aegis from your own pipeline — a few lines of DAG, pointed at your
Aegis account, and your data-quality gate runs in our hosted engine."

## Architecture
Airflow (Railway, standalone) triggers AegisDQOperator(profile="demo"), which calls
trigger_run on the hosted Aegis API; the hosted execute_run runs against the demo
Postgres, and the run is visible in the dashboard.

## One-time setup

### 1. Create the demo Postgres (Railway)
1. In the Aegis Railway project: + New, then Database, then PostgreSQL. Name it demo-db.
2. Load the seed using the Python loader (works without psql). Use the demo-db PUBLIC
   URL (host ends in .proxy.rlwy.net), not the internal *.railway.internal host:
     python -m pip install psycopg2-binary
     $env:DEMO_DATABASE_URL = "<demo-db PUBLIC URL>"
     python deploy/demo/db/load_seed.py
   Expect: OK: loaded demo data -> customers=30, orders=40
   Re-running this resets the demo to a known-good state.
   (Alternative if you have psql: psql "<demo-db PUBLIC URL>" -f deploy/demo/db/seed_demo.sql)

### 2. Point the API service at the demo Postgres
On the api service, set these variables (values from the demo-db service):
DEMO_DB_HOST, DEMO_DB_NAME, DEMO_DB_USER, DEMO_DB_PASSWORD.
Use Railway reference variables to the demo-db service where possible.

### 3. Create a demo client and push the demo config
1. Create a demo client account and copy its API key (see DEPLOY.md "Seed a client").
2. Push the demo profile and tests to that client:
   cd deploy/demo
   AEGIS_API_KEY="<demo client key>" AEGIS_API_URL="<hosted api url>" aegis push
   This uploads the demo Postgres profile and the guaranteed-green test set.

### 4. Deploy the Airflow service (Railway)
1. + New, then GitHub Repo (same repo). Set Root Directory to deploy/airflow so
   Railway reads deploy/airflow/railway.toml.
2. Set service variables:
   - AEGIS_API_URL = hosted api base URL
   - AEGIS_API_KEY = the demo client key
   - _AIRFLOW_WWW_USER_USERNAME = admin
   - _AIRFLOW_WWW_USER_PASSWORD = a stable password you choose
3. Set the service's target port to 8080 (Airflow standalone serves the UI there).
4. Deploy. When healthy, open the Airflow URL and log in with the pinned admin creds.

## Live demo script
1. Open the Airflow UI, go to DAGs, open aegis_demo.
2. Open the Code tab: "This is the whole integration — one operator, pointed at your
   Aegis account."
3. Click Trigger DAG (manual). Switch to the Graph (or Grid) view and watch
   run_demo_quality_checks go green.
4. Switch to the Aegis dashboard, open Runs: the new run appears with all checks passed.

## Reset between demos
- Re-run the seed loader (step 1.2: python deploy/demo/db/load_seed.py) if data changed.
- Re-trigger the DAG. Run history in Airflow is ephemeral on Railway and resets on
  redeploy — this is expected and harmless.

## Troubleshooting
- DAG fails immediately with a credentials error: AEGIS_API_URL or AEGIS_API_KEY not
  set on the Airflow service.
- Run shows FAILED in the dashboard with a connection error: the api service cannot
  reach the demo Postgres; recheck the DEMO_DB_ variables on the api service.
- Airflow login rejected after redeploy: _AIRFLOW_WWW_USER_PASSWORD not set (the
  standalone auto-password regenerates on restart without it).
