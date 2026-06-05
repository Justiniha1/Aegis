# Airflow Demo Runbook - Hosted DAG-Triggered Run

A live sales demo: an Airflow DAG triggers a real Aegis run on the hosted website
against a seeded demo Postgres. The prospect sees the DAG definition, watches it run
green, then sees the run land in the Aegis dashboard.

## What it proves
"You orchestrate Aegis from your own pipeline - a few lines of DAG, pointed at your
Aegis account, and your data-quality gate runs in our hosted engine."

## Architecture
Airflow runs the DAG, which uses AegisDQOperator(profile="demo") to call trigger_run on
the hosted Aegis API. The hosted engine runs the checks against the demo Postgres and the
run shows up in the dashboard. Where Airflow itself runs (your laptop via Docker, or a
hosted Railway service) does not change this - the run always executes on the hosted site.

> IMPORTANT - where Airflow runs: the recommended demo setup runs Airflow **locally via
> Docker** (Method A below). A full Airflow webserver needs ~1.5-2 GB RAM; the Railway
> Hobby plan caps a service at 1 GB, which is NOT enough and causes an OOM crash loop.
> Only host Airflow on Railway if you give the service a 2 GB+ instance (Method B,
> optional). The run still fires on the hosted website either way.

---

## One-time setup (shared by both methods)

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
On the api service, set these variables (use Railway reference variables to demo-db's
INTERNAL values, since the api reaches it over the private network):
   DEMO_DB_HOST     = ${{demo-db.PGHOST}}
   DEMO_DB_NAME     = ${{demo-db.PGDATABASE}}
   DEMO_DB_USER     = ${{demo-db.PGUSER}}
   DEMO_DB_PASSWORD = ${{demo-db.PGPASSWORD}}
The api service redeploys automatically.

### 3. Create a demo client and push the demo config
1. Create a demo client account and copy its API key (POST /api/v1/clients; see DEPLOY.md).
   The api_key is shown once - save it.
2. Push the demo profile and tests to that client. The CLI reads ./aegis/* relative to the
   working directory, so push from deploy/demo. Set BOTH env vars in the SAME shell so the
   repo-root .env (which points at localhost) does not override them:
     cd deploy/demo
     $env:AEGIS_API_KEY = "<demo client key>"
     $env:AEGIS_API_URL = "https://aegis-production-fa56.up.railway.app"
     aegis push
     cd ..\..
   This uploads the demo Postgres profile and the 5 guaranteed-green checks.

---

## Method A (recommended): run the demo Airflow locally via Docker

Reliable, free, and uses the exact image we ship. Needs Docker Desktop running and ~2 GB
free (any normal laptop is fine).

1. Start Docker Desktop and wait until it reports Running.
2. Build the image (first build ~3-5 min, one time), from the repo root:
     docker build -f deploy/airflow/Dockerfile -t aegis-demo-airflow .
3. Run it (paste the demo client key):
     docker run --rm -p 8080:8080 `
       -e AEGIS_API_KEY="<demo client key>" `
       -e AIRFLOW__CORE__LOAD_EXAMPLES="False" `
       -e AIRFLOW__WEBSERVER__WORKERS="1" `
       aegis-demo-airflow
   - No AEGIS_API_URL needed: the baked default points at the hosted api, so the run fires
     on the website. (Same "client only sets the API key" story.)
   - Boot takes ~1-2 minutes. The webserver prints a lot of "Added Permission..." lines,
     then goes quiet - that is normal, it is NOT stuck. Wait for the webserver to finish.
4. Get the admin password (the standalone admin password is generated and stored in the
   container). In another terminal:
     docker exec <container-name> cat /opt/airflow/standalone_admin_password.txt
   (Find <container-name> with: docker ps. On Git Bash, prefix the exec with
   MSYS_NO_PATHCONV=1 so the /opt path is not rewritten.)
5. Open http://localhost:8080 and log in as admin with that password.
6. Stop the demo afterward with Ctrl+C in the run terminal.

---

## Live demo script
1. Open the Airflow UI (http://localhost:8080 for Method A), go to DAGs, open aegis_demo.
2. Unpause aegis_demo (toggle on the left) if it is paused.
3. Open the Code tab: "This is the whole integration - one operator, pointed at your
   Aegis account."
4. Click Trigger DAG. Switch to the Graph (or Grid) view and watch
   run_demo_quality_checks go green (about 5-10 seconds).
5. Switch to the Aegis dashboard, log in as the demo client, open Runs: the new run
   appears with status COMPLETE and all 5 checks passed.

## Reset between demos
- Re-run the seed loader (step 1.2: python deploy/demo/db/load_seed.py) if data changed.
- Re-trigger the DAG.

## Troubleshooting
- aegis push connects to localhost:8000: AEGIS_API_URL was not set in the shell and the
  repo .env points at localhost. Set $env:AEGIS_API_URL in the same shell before pushing.
- Airflow UI looks frozen on "Added Permission..." lines: it is not frozen; the webserver
  is still booting. Confirm with: docker ps (status should be Up) and
  curl http://localhost:8080/health (expect HTTP 200). Wait for it to finish.
- Run shows FAILED in the dashboard with a connection error: the api service cannot reach
  the demo Postgres; recheck the DEMO_DB_ variables on the api service.

---

## Method B (optional): host Airflow on Railway

Only viable if you give the Airflow service a 2 GB+ instance. On the 1 GB plan the
webserver gets OOM-killed in a boot loop (this was confirmed: memory climbs to ~1.5 GB,
the container is killed, restarts, and never serves). If you have the headroom:

1. + New, then GitHub Repo (same repo). In Settings -> Source set:
   - Root Directory = / (repo root, so the Docker build context includes aegis_dq/)
   - Config-as-code file path = deploy/airflow/railway.toml
2. Variables:
   - AEGIS_API_KEY = the demo client key
   - AIRFLOW__CORE__LOAD_EXAMPLES = False
   - AIRFLOW__WEBSERVER__WORKERS = 1
   - AIRFLOW__DATABASE__SQL_ALCHEMY_CONN =
       postgresql+psycopg2://${{demo-db.PGUSER}}:${{demo-db.PGPASSWORD}}@${{demo-db.PGHOST}}:5432/${{demo-db.PGDATABASE}}
     (Postgres metadata makes the permission-sync fast and persistent across restarts; do
     NOT rely on the default SQLite on Railway - it has no persistent disk.)
   - _AIRFLOW_WWW_USER_USERNAME = admin
   - _AIRFLOW_WWW_USER_PASSWORD = a stable password you choose
3. Settings -> Networking: generate a public domain, set target port = 8080.
4. Bump the service Memory to 2 GB+. Deploy. Boot takes ~2-3 minutes the first time.
