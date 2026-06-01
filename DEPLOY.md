# Deploying Aegis to Railway

This is an **owner-operated, single-instance** deploy guide. There is no public
"Deploy on Railway" one-click button (D-07) — you deploy Aegis once for your own
hosted instance and occasionally re-deploy. The goal: stand the stack up from
scratch in **under 15 minutes** by following this runbook.

The deploy is **three services plus a managed database**:

| Service    | Source            | Role                                          |
|------------|-------------------|-----------------------------------------------|
| `api`      | repo root         | FastAPI backend (REST API + auth)             |
| `frontend` | `frontend/`       | Next.js dashboard                             |
| `engine`   | `backend/`        | Data-quality engine — **ships idle** (D-04)   |
| Postgres   | Railway managed   | Database (provisioned via the dashboard)      |

**Prerequisites:** a Railway account, this repo pushed to GitHub, and optionally
the Railway CLI (`npm i -g @railway/cli`).

> **Config-as-code on Railway is PER-SERVICE.** Each service reads its **own**
> `railway.toml`:
> - `api` → repo-root `railway.toml`
> - `frontend` → `frontend/railway.toml`
> - `engine` → `backend/railway.toml`

---

## 1. Create the Railway project and Postgres

1. Create a **New Project** in Railway from this GitHub repo.
2. Add the database: **+ New → Database → PostgreSQL**. Railway fully manages it;
   you do **not** set any env vars on the database itself (D-01).
3. No migration step is needed — tables auto-create on first `api` boot via
   SQLAlchemy `create_all` in `dashboard_api/main.py`. **There is no Alembic and
   no manual init step.**

---

## 2. Configure the three services

Add three services from the same repo, each pointing at its own config so Railway
reads the correct `railway.toml`:

| Service    | Root Directory | Config / Dockerfile                          |
|------------|----------------|----------------------------------------------|
| `api`      | repo root (`/`)| root `railway.toml` → `dashboard_api/Dockerfile` |
| `frontend` | `frontend/`    | `frontend/railway.toml` → `Dockerfile`       |
| `engine`   | `backend/`     | `backend/railway.toml` → `Dockerfile` (idle) |

Setting each service's **Root Directory** (and config file path) is a one-time
per-service dashboard setting.

---

## 3. Set environment variables

Set these in each service's **Variables** tab. **No secrets ever go into the
`railway.toml` files** — they are build/deploy directives only.

### `api` service

| Variable | Value | Notes |
|----------|-------|-------|
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` | **Reference variable** — links to the managed Postgres. |
| `JWT_SECRET_KEY` | 32+ char random | Use Railway's **CMD+K → "Generate secret"**. Must be **stable across restarts** — if it changes, every existing login is invalidated on each redeploy. |
| `AEGIS_ENCRYPTION_KEY` | a **valid Fernet key** | Do **NOT** use Railway's secret generator (it produces hex, which Fernet rejects at decrypt time). Generate it yourself — see below. |
| `ALLOWED_ORIGINS` | `https://<frontend>.railway.app` | Exact frontend URL, **no wildcard** (`*` is forbidden — it breaks credentialed CORS). Set this in step 5 once the frontend domain exists. |
| `DQF_YAML_PATH` | `/tmp/test_definitions.yaml` | Optional. Railway has no persistent volume, so don't rely on disk paths. |

Generate the Fernet key locally and paste the output:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### `frontend` service

| Variable | Value | Notes |
|----------|-------|-------|
| `NEXT_PUBLIC_API_URL` | _see step 4_ | Build-time variable. Do **not** set it yet — the API domain must exist first. |

### `engine` service

Leave `DQF_API_URL` and `DQF_API_KEY` **unset**. The engine ships idle (D-04);
production engines run on the client's own infrastructure (see the checklist).

---

## 4. Deploy the API and wire the frontend URL (two-step)

`NEXT_PUBLIC_API_URL` is baked into the frontend at **build time**, and reference
variables resolve to an empty string before the API domain exists. So the order
matters (D-03):

1. **Deploy the `api` service.**
2. Generate its public domain: **Settings → Networking → Generate Domain**.
3. On the `frontend` service, set the build-time variable:
   ```
   NEXT_PUBLIC_API_URL=https://${{api.RAILWAY_PUBLIC_DOMAIN}}
   ```
   The `https://` prefix is **required** — Railway returns the bare domain without a scheme.
4. **Deploy the `frontend` service.** The build ARG now resolves because the API domain exists.

> **Fallback:** if the reference variable resolves empty at build, hardcode
> `NEXT_PUBLIC_API_URL=https://<api-domain>.railway.app` on the frontend and redeploy.

---

## 5. Set `ALLOWED_ORIGINS` and redeploy the API

Now that the frontend domain exists, set on the `api` service:

```
ALLOWED_ORIGINS=https://<frontend>.railway.app
```

Then **redeploy the `api` service**. Without this, the browser will get CORS
errors when the dashboard calls the API.

---

## Post-Deploy Checklist

Run these against the live instance:

1. **Health check:**
   ```bash
   curl https://<api>.railway.app/api/v1/health
   ```
   Expect `{"status":"ok"}`.

2. **Create the first client account.** `POST /api/v1/clients` is unauthenticated
   (open registration by design for a private instance) and returns the `api_key`
   **once**:
   ```bash
   curl -X POST https://<api>.railway.app/api/v1/clients \
     -H "Content-Type: application/json" \
     -d '{"name":"owner","email":"owner@example.com","password":"<strong-password>"}'
   ```
   **Save the `api_key`** from the `201` response — it is **shown once only** and is
   the `DQF_API_KEY` your Airflow worker will need.

3. **Confirm login:** open `https://<frontend>.railway.app`, log in with that
   email/password. The dashboard should load with **no console CORS errors**.

4. **Point an Airflow worker at the live API.** The engine runs on the client's own
   infra (D-04). In the Airflow environment / `.env` used by the `aegis-dq` SDK, set:
   ```
   DQF_API_URL=https://<api>.railway.app
   DQF_API_KEY=<api_key saved in step 2>
   ```
   No DAG code change is needed — `aegis_dq/_client.py` reads these at import.

---

## Security notes

- **Secrets live only in Railway Variables** — never commit them to git. The
  `railway.toml` files contain no secrets.
- `POST /api/v1/clients` is unauthenticated by design for a private instance.
  After registering, treat the API URL as semi-private and keep `ALLOWED_ORIGINS`
  locked to your exact frontend domain.
- `AEGIS_ENCRYPTION_KEY` **must** be a real Fernet key, or connection-profile
  decryption fails at runtime.

---

## Re-deploy / take down and bring back up

- Pushing to the connected branch redeploys automatically. Secrets persist in
  Railway Variables across redeploys.
- If you fully recreate the `api` service, regenerate its domain and re-point
  `NEXT_PUBLIC_API_URL` (and `ALLOWED_ORIGINS`).
- **Engine idle fallback (A1):** if `sleep infinity` is unavailable in the engine
  image, use `python -c "import time; time.sleep(float('inf'))"` in
  `backend/railway.toml` instead.
