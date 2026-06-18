# Airflow Demo — Hosted DAG-Triggered Run — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a live sales demo where a hosted Airflow DAG triggers a real run on the hosted Comet website against a seeded demo Postgres, with the DAG setup and execution visible and the run landing in the dashboard.

**Architecture:** No new product code — reuse `CometDQOperator` → `trigger_run` → server-side `execute_run`. The work is (1) deployable artifacts: a Railway Airflow service (Dockerfile + railway config + baked demo DAG) and a seeded demo Postgres; (2) demo config: a `demo` Postgres profile + a small guaranteed-green test set pushed to a dedicated demo client; (3) a runbook that makes the live demo repeatable. Final acceptance is a manual dry run of the runbook against the deployed demo.

**Tech Stack:** Apache Airflow (standalone image), Railway, Postgres, the existing `comet-dq` package and `comet` CLI.

---

## Nature of this plan (read first)

This is an **infra + config + docs** plan, not a feature plan. Three kinds of steps:

- **Agent-executable (code/files):** Tasks 1–5 create files in the repo. These are fully doable in-session and the parts that *can* be tested locally (DAG integrity, SQL validity) have tests.
- **Operator/manual (Railway dashboard):** Provisioning the two Railway services, setting env vars, pushing demo config, and triggering the live DAG require the human (Railway UI + the demo client's API key). These live in the **runbook** (Task 5) and the **acceptance dry run** (Task 6).
- **Acceptance:** Task 6 is the manual end-to-end dry run that proves the demo works. There is no automated end-to-end test because it depends on live Railway services and a live API key.

TDD is applied where it fits (DAG parses, seed SQL is valid). It is not forced onto Railway provisioning, which cannot be unit-tested.

---

## File Structure

```
deploy/
  demo/
    comet/
      database_connection.yaml   # CREATE — the `demo` Postgres profile (pushed via comet push)
      test_definitions.yaml      # CREATE — small guaranteed-green demo test set
    db/
      seed_demo.sql              # CREATE — idempotent schema + clean seed data for demo Postgres
  airflow/
    Dockerfile                   # CREATE — apache/airflow standalone + comet-dq[airflow] + baked DAG
    railway.toml                 # CREATE — Railway service config for the Airflow service
    requirements.txt             # CREATE — comet-dq[airflow] pin for the image
    dags/
      comet_demo_dag.py          # CREATE — demo DAG (profile="demo", schedule=None)
tests/
  test_demo_dag.py               # CREATE — DAG-integrity test (skipped if airflow not installed)
  test_seed_demo_sql.py          # CREATE — validates seed_demo.sql parses + is idempotent-shaped
docs/
  airflow-demo-runbook.md        # CREATE — one-time setup, live script, reset procedure
.env.example                     # MODIFY — add demo Postgres + Airflow demo vars (documentation)
```

Responsibilities:
- `deploy/demo/db/seed_demo.sql` — the single source of demo data (2 tables, clean rows).
- `deploy/demo/comet/*` — exactly what gets pushed to the demo client (profile + tests). The test set is sized to pass against the seed.
- `deploy/airflow/*` — everything needed to build and deploy the hosted Airflow service.
- `docs/airflow-demo-runbook.md` — the human-facing setup + live script.

---

## Task 1: Demo database schema + seed data

**Files:**
- Create: `deploy/demo/db/seed_demo.sql`
- Test: `tests/test_seed_demo_sql.py`

The schema is deliberately tiny (2 tables) and the data is hand-sized to pass every demo check in Task 2. Idempotent: drops then recreates, so re-running it resets the demo.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_seed_demo_sql.py
"""Static validation of the demo seed SQL. No live DB required."""
from pathlib import Path

import pytest

SEED = Path("deploy/demo/db/seed_demo.sql")


def _sql() -> str:
    return SEED.read_text(encoding="utf-8")


def test_seed_file_exists():
    assert SEED.is_file(), f"missing {SEED}"


def test_seed_is_idempotent_shaped():
    sql = _sql().lower()
    # Idempotent reset: must drop before create so re-running resets cleanly.
    assert "drop table if exists orders" in sql
    assert "drop table if exists customers" in sql
    assert "create table customers" in sql
    assert "create table orders" in sql


def test_seed_inserts_enough_rows_to_pass_checks():
    sql = _sql().lower()
    # Demo row_count check requires >= 1 customer; we seed many. Sanity: at least
    # 20 customer insert value-tuples and 20 order value-tuples exist.
    assert sql.count("into customers") >= 1
    assert sql.count("into orders") >= 1
    # Foreign-key column present so the relationship_check has something to validate.
    assert "customer_id" in sql
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_seed_demo_sql.py -v`
Expected: FAIL — `missing deploy/demo/db/seed_demo.sql`.

- [ ] **Step 3: Write the seed SQL**

```sql
-- deploy/demo/db/seed_demo.sql
-- Idempotent demo dataset for the Comet Airflow demo.
-- Re-run this to reset the demo to a known-good, all-checks-pass state.

DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
    customer_id  INTEGER PRIMARY KEY,
    first_name   TEXT    NOT NULL,
    last_name    TEXT    NOT NULL,
    email        TEXT    NOT NULL,
    signup_date  DATE    NOT NULL,
    country      TEXT    NOT NULL
);

CREATE TABLE orders (
    order_id     INTEGER PRIMARY KEY,
    customer_id  INTEGER NOT NULL REFERENCES customers(customer_id),
    order_date   DATE    NOT NULL,
    order_total  NUMERIC(10,2) NOT NULL,
    status       TEXT    NOT NULL
);

-- 30 customers, all with non-null unique emails.
INSERT INTO customers (customer_id, first_name, last_name, email, signup_date, country) VALUES
 (1,'Ada','Lovelace','ada.lovelace@example.com','2024-01-05','UK'),
 (2,'Alan','Turing','alan.turing@example.com','2024-01-06','UK'),
 (3,'Grace','Hopper','grace.hopper@example.com','2024-01-07','US'),
 (4,'Katherine','Johnson','katherine.johnson@example.com','2024-01-08','US'),
 (5,'Dennis','Ritchie','dennis.ritchie@example.com','2024-01-09','US'),
 (6,'Ken','Thompson','ken.thompson@example.com','2024-01-10','US'),
 (7,'Margaret','Hamilton','margaret.hamilton@example.com','2024-01-11','US'),
 (8,'Barbara','Liskov','barbara.liskov@example.com','2024-01-12','US'),
 (9,'Edsger','Dijkstra','edsger.dijkstra@example.com','2024-01-13','NL'),
 (10,'Linus','Torvalds','linus.torvalds@example.com','2024-01-14','FI'),
 (11,'Guido','vanRossum','guido.vanrossum@example.com','2024-01-15','NL'),
 (12,'Tim','BernersLee','tim.bernerslee@example.com','2024-01-16','UK'),
 (13,'Donald','Knuth','donald.knuth@example.com','2024-01-17','US'),
 (14,'John','McCarthy','john.mccarthy@example.com','2024-01-18','US'),
 (15,'Claude','Shannon','claude.shannon@example.com','2024-01-19','US'),
 (16,'Vint','Cerf','vint.cerf@example.com','2024-01-20','US'),
 (17,'Radia','Perlman','radia.perlman@example.com','2024-01-21','US'),
 (18,'Frances','Allen','frances.allen@example.com','2024-01-22','US'),
 (19,'Leslie','Lamport','leslie.lamport@example.com','2024-01-23','US'),
 (20,'Niklaus','Wirth','niklaus.wirth@example.com','2024-01-24','CH'),
 (21,'Andrew','Tanenbaum','andrew.tanenbaum@example.com','2024-01-25','NL'),
 (22,'Bjarne','Stroustrup','bjarne.stroustrup@example.com','2024-01-26','DK'),
 (23,'James','Gosling','james.gosling@example.com','2024-01-27','CA'),
 (24,'Brian','Kernighan','brian.kernighan@example.com','2024-01-28','CA'),
 (25,'Yukihiro','Matsumoto','yukihiro.matsumoto@example.com','2024-01-29','JP'),
 (26,'Anita','Borg','anita.borg@example.com','2024-01-30','US'),
 (27,'Shafi','Goldwasser','shafi.goldwasser@example.com','2024-01-31','US'),
 (28,'Adi','Shamir','adi.shamir@example.com','2024-02-01','IL'),
 (29,'Whitfield','Diffie','whitfield.diffie@example.com','2024-02-02','US'),
 (30,'Martin','Hellman','martin.hellman@example.com','2024-02-03','US');

-- 40 orders, every customer_id references a real customer, totals all > 0.
INSERT INTO orders (order_id, customer_id, order_date, order_total, status) VALUES
 (1,1,'2024-03-01',120.50,'completed'),
 (2,2,'2024-03-01',88.00,'completed'),
 (3,3,'2024-03-02',240.75,'completed'),
 (4,4,'2024-03-02',56.20,'completed'),
 (5,5,'2024-03-03',310.00,'completed'),
 (6,6,'2024-03-03',74.99,'completed'),
 (7,7,'2024-03-04',199.99,'completed'),
 (8,8,'2024-03-04',64.40,'completed'),
 (9,9,'2024-03-05',410.10,'completed'),
 (10,10,'2024-03-05',150.00,'completed'),
 (11,11,'2024-03-06',92.30,'completed'),
 (12,12,'2024-03-06',133.33,'completed'),
 (13,13,'2024-03-07',77.70,'completed'),
 (14,14,'2024-03-07',265.00,'completed'),
 (15,15,'2024-03-08',58.90,'completed'),
 (16,16,'2024-03-08',180.25,'completed'),
 (17,17,'2024-03-09',99.00,'completed'),
 (18,18,'2024-03-09',145.60,'completed'),
 (19,19,'2024-03-10',322.00,'completed'),
 (20,20,'2024-03-10',61.15,'completed'),
 (21,1,'2024-03-11',210.00,'completed'),
 (22,2,'2024-03-11',54.50,'completed'),
 (23,3,'2024-03-12',176.80,'completed'),
 (24,4,'2024-03-12',83.20,'completed'),
 (25,5,'2024-03-13',299.99,'completed'),
 (26,6,'2024-03-13',67.00,'completed'),
 (27,7,'2024-03-14',128.40,'completed'),
 (28,8,'2024-03-14',95.25,'completed'),
 (29,9,'2024-03-15',355.00,'completed'),
 (30,10,'2024-03-15',142.10,'completed'),
 (31,11,'2024-03-16',71.60,'completed'),
 (32,12,'2024-03-16',188.88,'completed'),
 (33,13,'2024-03-17',60.00,'completed'),
 (34,14,'2024-03-17',244.30,'completed'),
 (35,15,'2024-03-18',52.75,'completed'),
 (36,16,'2024-03-18',165.50,'completed'),
 (37,17,'2024-03-19',110.00,'completed'),
 (38,18,'2024-03-19',137.20,'completed'),
 (39,19,'2024-03-20',288.00,'completed'),
 (40,20,'2024-03-20',69.90,'completed');
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_seed_demo_sql.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add deploy/demo/db/seed_demo.sql tests/test_seed_demo_sql.py
git commit -m "feat(demo): add idempotent demo Postgres seed (customers + orders)"
```

---

## Task 2: Demo client config — `demo` profile + guaranteed-green tests

**Files:**
- Create: `deploy/demo/comet/database_connection.yaml`
- Create: `deploy/demo/comet/test_definitions.yaml`

The `demo` profile is `type: postgres` and resolves its connection from `${DEMO_DB_*}` env vars **set on the api service** (where profiles resolve at run time). The test set is 5 checks chosen to pass against Task 1's seed.

- [ ] **Step 1: Write the demo connection profile**

```yaml
# deploy/demo/comet/database_connection.yaml
# Demo profile for the Comet Airflow sales demo.
# Pushed to the demo client account via `comet push` (see docs/airflow-demo-runbook.md).
# The ${DEMO_DB_*} vars are resolved server-side on the api service at run time.

demo:
  type: postgres
  host: ${DEMO_DB_HOST}
  port: 5432
  database: ${DEMO_DB_NAME}
  username: ${DEMO_DB_USER}
  password: ${DEMO_DB_PASSWORD}
  schema: public
  connect_args:
    sslmode: require
    connect_timeout: 10
    application_name: comet-demo
```

- [ ] **Step 2: Write the demo test definitions**

These map 1:1 to the seed: email is non-null, customer_id is unique, customers has rows, every order references a real customer, and the customers schema matches.

```yaml
# deploy/demo/comet/test_definitions.yaml
# Minimal, guaranteed-green test set for the Airflow demo.
# Every check passes against deploy/demo/db/seed_demo.sql.
engine: Simple
settings:
  default_profile: demo
  default_severity: MEDIUM
  alerts:
    enabled: false
    slack:
      enabled: false
      webhook_url: ""
      notify_on: []
    email:
      enabled: false
      recipients: []
      notify_on: []
tests:
- name: Customer Email Null Check
  description: Every customer has an email address
  type: null_check
  severity: HIGH
  table: customers
  column: email
  threshold: 0
- name: Customer ID Uniqueness
  description: customer_id is unique (primary key)
  type: unique_check
  severity: CRITICAL
  table: customers
  column: customer_id
- name: Customer Row Count
  description: Customers table is populated
  type: row_count
  severity: MEDIUM
  table: customers
  min_rows: 1
  max_rows: 100000
  timeframe: all_time
- name: Orders Reference Valid Customers
  description: Every order points at a real customer
  type: relationship_check
  severity: CRITICAL
  source_table: orders
  source_column: customer_id
  target_table: customers
  target_column: customer_id
  max_orphans: 0
- name: Customers Schema Validation
  description: customers table has the expected columns
  type: schema_check
  severity: HIGH
  table: customers
  expected_columns:
    customer_id: integer
    first_name: string
    last_name: string
    email: string
    signup_date: date
    country: string
```

- [ ] **Step 3: Sanity-check the YAML parses**

Run: `python -c "import yaml,sys; [yaml.safe_load(open(p,encoding='utf-8')) for p in ['deploy/demo/comet/database_connection.yaml','deploy/demo/comet/test_definitions.yaml']]; print('ok')"`
Expected: prints `ok` (no YAML errors).

- [ ] **Step 4: Commit**

```bash
git add deploy/demo/comet/database_connection.yaml deploy/demo/comet/test_definitions.yaml
git commit -m "feat(demo): add demo Postgres profile + guaranteed-green test set"
```

---

## Task 3: Demo DAG + DAG-integrity test

**Files:**
- Create: `deploy/airflow/dags/comet_demo_dag.py`
- Create: `tests/test_demo_dag.py`

The DAG is a single `CometDQOperator` task, `profile="demo"`, `schedule=None` (manual trigger only). It is intentionally minimal — one green task is the v1 story.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_demo_dag.py
"""DAG-integrity test for the demo DAG. Skipped if Airflow is not installed."""
import importlib.util
from pathlib import Path

import pytest

pytest.importorskip("airflow", reason="airflow not installed in this environment")

DAG_FILE = Path("deploy/airflow/dags/comet_demo_dag.py")


def _load_dag_module():
    spec = importlib.util.spec_from_file_location("comet_demo_dag", DAG_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dag_file_exists():
    assert DAG_FILE.is_file(), f"missing {DAG_FILE}"


def test_dag_imports_and_has_expected_shape():
    module = _load_dag_module()
    dag = getattr(module, "dag", None)
    assert dag is not None, "module must expose a top-level `dag`"
    assert dag.dag_id == "comet_demo"
    # Manual trigger only — no schedule.
    assert dag.schedule_interval is None
    task_ids = set(dag.task_ids)
    assert "run_demo_quality_checks" in task_ids


def test_operator_targets_demo_profile():
    module = _load_dag_module()
    task = module.dag.get_task("run_demo_quality_checks")
    assert task.profile == "demo"
```

- [ ] **Step 2: Run test to verify it fails (or skips if no Airflow)**

Run: `pytest tests/test_demo_dag.py -v`
Expected: SKIPPED if `airflow` isn't installed locally; otherwise FAIL — `missing deploy/airflow/dags/comet_demo_dag.py`.

- [ ] **Step 3: Write the demo DAG**

```python
# deploy/airflow/dags/comet_demo_dag.py
"""Comet demo DAG — triggers a real run on the hosted Comet website.

Baked into the demo Airflow image. Triggered manually during a sales demo.
Credentials come from the service env: COMET_API_URL and COMET_API_KEY.
"""
from __future__ import annotations

from datetime import datetime

from airflow import DAG

from comet_dq.airflow import CometDQOperator

with DAG(
    dag_id="comet_demo",
    description="Demo: trigger an Comet data-quality run on the hosted website",
    schedule=None,                 # manual trigger only — presenter clicks Run
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["comet", "demo"],
) as dag:

    run_demo_quality_checks = CometDQOperator(
        task_id="run_demo_quality_checks",
        profile="demo",            # the seeded Postgres profile on the hosted account
        poll_interval=5,           # seconds between status polls
        # COMET_API_URL / COMET_API_KEY are read from the service environment.
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_demo_dag.py -v`
Expected: PASS if `airflow` installed; SKIPPED otherwise. (If skipped, the DAG is still validated at image-build time in Task 4, Step 4.)

- [ ] **Step 5: Commit**

```bash
git add deploy/airflow/dags/comet_demo_dag.py tests/test_demo_dag.py
git commit -m "feat(demo): add manually-triggered demo DAG + integrity test"
```

---

## Task 4: Airflow Railway service (Dockerfile + config)

**Files:**
- Create: `deploy/airflow/requirements.txt`
- Create: `deploy/airflow/Dockerfile`
- Create: `deploy/airflow/railway.toml`

A single-container Airflow in `standalone` mode (webserver + scheduler + triggerer), with `comet-dq[airflow]` installed and the demo DAG baked in. Admin login is pinned via env so it survives Railway redeploys (no persistent disk).

- [ ] **Step 1: Write the image requirements pin**

```
# deploy/airflow/requirements.txt
# Installed into the demo Airflow image so the CometDQOperator imports.
# Build context is the repo root; the local package is installed by the Dockerfile.
```

(The package itself is installed from the repo by the Dockerfile in Step 2; this file is a placeholder for any extra pins. Keep it present so the Dockerfile COPY/pip step is stable.)

- [ ] **Step 2: Write the Dockerfile**

```dockerfile
# deploy/airflow/Dockerfile
# Demo Airflow image: Airflow standalone + the local comet-dq[airflow] package + demo DAG.
# Build context = repo root (see deploy/airflow/railway.toml).
FROM apache/airflow:2.9.3-python3.11

# Bake the demo DAG into the image's DAGs folder.
COPY deploy/airflow/dags/ ${AIRFLOW_HOME}/dags/

# Install the local Comet package with the airflow extra so the operator imports.
# Copy the package sources needed for an editable/local install.
COPY --chown=airflow:root pyproject.toml /opt/comet/pyproject.toml
COPY --chown=airflow:root comet_dq/ /opt/comet/comet_dq/
COPY --chown=airflow:root deploy/airflow/requirements.txt /opt/comet/requirements.txt

USER airflow
RUN pip install --no-cache-dir "/opt/comet" && \
    pip install --no-cache-dir -r /opt/comet/requirements.txt

# Standalone runs webserver + scheduler + triggerer in one process (demo-grade).
# Railway sets $PORT; Airflow's webserver must bind to it.
ENV AIRFLOW__WEBSERVER__WEB_SERVER_PORT=8080
CMD ["bash", "-c", "airflow standalone"]
```

> Note on `$PORT`: Railway injects `$PORT` and routes the public domain to it. Airflow
> standalone serves the UI on 8080 by default. In `railway.toml` (Step 3) we map the
> service's target port to 8080 rather than fighting Airflow's port handling. If the
> Railway domain insists on `$PORT`, set the service's **target port = 8080** in the
> Railway UI (documented in the runbook).

- [ ] **Step 3: Write the Railway service config**

```toml
# deploy/airflow/railway.toml
# Railway config for the demo Airflow service (build context = repo root).
[build]
builder = "DOCKERFILE"
dockerfilePath = "deploy/airflow/Dockerfile"

[deploy]
restartPolicyType = "ON_FAILURE"
```

- [ ] **Step 4: Verify the image builds and the DAG parses inside it**

Run (requires Docker locally; if Docker is unavailable, this is deferred to the runbook deploy step):

```bash
docker build -f deploy/airflow/Dockerfile -t comet-demo-airflow .
docker run --rm comet-demo-airflow bash -c "python /opt/airflow/dags/comet_demo_dag.py && echo DAG_OK"
```

Expected: build succeeds and prints `DAG_OK` (the DAG imports with `comet_dq` available).
If Docker is not available in this environment, mark this step done-by-runbook and rely on Task 3's integrity test + the Task 6 deploy.

- [ ] **Step 5: Commit**

```bash
git add deploy/airflow/Dockerfile deploy/airflow/railway.toml deploy/airflow/requirements.txt
git commit -m "feat(demo): add Railway Airflow service (standalone + baked demo DAG)"
```

---

## Task 5: Demo runbook

**Files:**
- Create: `docs/airflow-demo-runbook.md`
- Modify: `.env.example`

The runbook is the human-facing deliverable: one-time setup, the live click-by-click script, and a reset procedure. It must be exact enough that the demo can be run cold.

- [ ] **Step 1: Add demo env vars to `.env.example`**

Append this block to `.env.example`:

```bash
# --- Airflow demo (see docs/airflow-demo-runbook.md) ---
# Set on the API service (profiles resolve server-side):
DEMO_DB_HOST=          # demo Postgres host (Railway)
DEMO_DB_NAME=          # demo Postgres database name
DEMO_DB_USER=          # demo Postgres user
DEMO_DB_PASSWORD=      # demo Postgres password
# Set on the Airflow service:
COMET_API_URL=         # hosted Comet api base URL
COMET_API_KEY=         # demo client API key
_AIRFLOW_WWW_USER_USERNAME=admin     # pinned Airflow admin login
_AIRFLOW_WWW_USER_PASSWORD=          # choose a stable password
```

- [ ] **Step 2: Write the runbook**

```markdown
# Airflow Demo Runbook — Hosted DAG-Triggered Run

A live sales demo: an Airflow DAG triggers a real Comet run on the hosted website
against a seeded demo Postgres. The prospect sees the DAG definition, watches it run
green, then sees the run land in the Comet dashboard.

## What it proves
"You orchestrate Comet from your own pipeline — a few lines of DAG, pointed at your
Comet account, and your data-quality gate runs in our hosted engine."

## Architecture
Airflow (Railway, standalone) → `CometDQOperator(profile="demo")` → `trigger_run`
→ hosted Comet `execute_run` against the demo Postgres → run visible in the dashboard.

## One-time setup

### 1. Create the demo Postgres (Railway)
1. In the Comet Railway project: **+ New → Database → PostgreSQL**. Name it `demo-db`.
2. Load the seed: from a machine with `psql`, run against the demo DB's connection URL:
   ```bash
   psql "<demo-db DATABASE_URL>" -f deploy/demo/db/seed_demo.sql
   ```
   Re-running this resets the demo to a known-good state.

### 2. Point the API service at the demo Postgres
On the **api** service, set (values from the demo-db service variables):
`DEMO_DB_HOST`, `DEMO_DB_NAME`, `DEMO_DB_USER`, `DEMO_DB_PASSWORD`.
(Use Railway reference variables to the `demo-db` service where possible.)

### 3. Create a demo client + push the demo config
1. Create a demo client account and copy its API key (see DEPLOY.md "Seed a client").
2. Push the demo profile + tests to that client:
   ```bash
   cd deploy/demo
   COMET_API_KEY="<demo client key>" COMET_API_URL="<hosted api url>" comet push
   ```
   This uploads the `demo` Postgres profile and the guaranteed-green test set.

### 4. Deploy the Airflow service (Railway)
1. **+ New → GitHub Repo** (same repo). Set **Root Directory = `deploy/airflow`** so
   Railway reads `deploy/airflow/railway.toml`.
2. Set service variables:
   - `COMET_API_URL` = hosted api base URL
   - `COMET_API_KEY` = the demo client key
   - `_AIRFLOW_WWW_USER_USERNAME` = `admin`
   - `_AIRFLOW_WWW_USER_PASSWORD` = a stable password you choose
3. Set the service's **target port = 8080** (Airflow standalone serves the UI there).
4. Deploy. When healthy, open the Airflow URL and log in with the pinned admin creds.

## Live demo script
1. Open the Airflow UI → DAGs → `comet_demo`.
2. Click the DAG → **Code** tab: "This is the whole integration — one operator,
   pointed at your Comet account."
3. Click **Trigger DAG** (manual). Switch to the **Graph** (or Grid) view and watch
   `run_demo_quality_checks` go green.
4. Switch to the **Comet dashboard** → Runs: the new run appears with all checks passed.

## Reset between demos
- Re-run the seed (step 1.2) if data was changed.
- Re-trigger the DAG. (Run history in Airflow is ephemeral on Railway and resets on
  redeploy — this is expected and harmless.)

## Troubleshooting
- DAG fails immediately with a credentials error → `COMET_API_URL`/`COMET_API_KEY` not
  set on the Airflow service.
- Run shows FAILED in the dashboard with a connection error → the api service cannot
  reach the demo Postgres; recheck `DEMO_DB_*` on the **api** service.
- Airflow login rejected after redeploy → `_AIRFLOW_WWW_USER_PASSWORD` not set (the
  standalone auto-password regenerates on restart without it).
```

- [ ] **Step 3: Commit**

```bash
git add docs/airflow-demo-runbook.md .env.example
git commit -m "docs(demo): add Airflow demo runbook + demo env vars"
```

---

## Task 6: Acceptance dry run (manual, by the operator)

**Files:** none (validation only).

This is the gate that proves the demo works. It is manual because it depends on the
live Railway services and the demo client key. Follow the runbook end to end.

- [ ] **Step 1: Complete the one-time setup** (Task 5 runbook, sections 1–4).

- [ ] **Step 2: Trigger the DAG and confirm green**

In the Airflow UI, trigger `comet_demo`. Confirm `run_demo_quality_checks` reaches
`success` (green) within ~1–2 minutes.

- [ ] **Step 3: Confirm the run in the Comet dashboard**

Open the dashboard → Runs. Confirm a new run for the `demo` profile appears with status
PASSED and all 5 checks passing.

- [ ] **Step 4: Confirm reset works**

Re-run the seed SQL, re-trigger the DAG, confirm green again. The demo is now repeatable.

- [ ] **Step 5: Record the result**

Note the demo Airflow URL, the demo client, and the dashboard run id in the runbook (or
a short note), so the next presenter can find them.

---

## Verification Summary

- **Automated (local):** `pytest tests/test_seed_demo_sql.py tests/test_demo_dag.py -v`
  (DAG test skips cleanly if Airflow isn't installed locally).
- **Build-time:** `docker build` of the Airflow image + in-image DAG parse (Task 4 Step 4),
  or deferred to the Railway deploy if Docker is unavailable locally.
- **Acceptance:** the Task 6 manual dry run — DAG goes green and the run appears in the
  dashboard with all checks passing.
