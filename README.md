# Aegis — Data Quality Framework

A data quality testing framework that runs checks against your databases and displays results on a live dashboard.

---

## Quick Start

**Prerequisites:** Docker Desktop, Python 3.9+

```bash
# 1. Copy the environment template
cp .env.example .env

# 2. Start the dashboard
make start

# 3. Load demo data and create your account
make seed

# 4. Open the dashboard
open http://localhost:3000
```

Log in with:
- **Email:** demo@dqf.dev
- **Password:** demo1234

---

## Running the Engine Against Your Database

The test engine runs your data quality checks and posts results to the dashboard.

**1. Configure your database connection** in `backend/config/database_connection.yaml`:

```yaml
my_db:
  type: postgres
  host: ${DB_HOST}
  port: 5432
  database: analytics
  username: ${DB_USER}
  password: ${DB_PASSWORD}
```

**2. Add credentials to your `.env` file:**

```
DB_HOST=your-database-host.com
DB_USER=readonly_user
DB_PASSWORD=your_password
```

**3. Define your tests** in `backend/config/test_definitions.yaml` — see the existing file for examples.

**4. Get your API key** — shown after running `make seed`. Add it to `.env`:

```
DQF_API_KEY=your-api-key-here
```

**5. Run the engine:**

```bash
make run
```

Results appear on the dashboard at http://localhost:3000.

---

## Commands

| Command | Description |
|---|---|
| `make start` | Start the dashboard (API + frontend) |
| `make seed` | Load demo data and run the engine once |
| `make run` | Run the test engine against your databases |
| `make stop` | Stop all services |
| `make build` | Rebuild containers after code changes |
| `make logs` | Tail service logs |
| `make clean` | Full teardown including database |

> **Windows:** `make` is available in Git Bash, which ships with [Git for Windows](https://git-scm.com/download/win).

---

## Services

| Service | URL | Description |
|---|---|---|
| Dashboard | http://localhost:3000 | Results UI |
| API | http://localhost:8000 | REST API |
| API Docs | http://localhost:8000/docs | Swagger UI |
