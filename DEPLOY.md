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
per-service dashboard setting. Once Root Directory is set, Railway auto-detects
that folder's `railway.toml` and the **Build → Builder** will switch to
`Dockerfile` on the next deploy. (If it stays on Railpack, set **Settings →
Config-as-code → Add File Path = `railway.toml`** to force it.)

> **Name the `api` service exactly `api`.** Railway auto-creates the first service
> from your repo name (e.g. `aegis`). Either rename it to `api` here, or be ready to
> use the **literal** API domain in step 4 — the cross-service reference variable
> `${{api.RAILWAY_PUBLIC_DOMAIN}}` only resolves if a service is literally named `api`.

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
| `PORT` | `3000` | Pin the port. Next.js (`next start`) listens on 3000; without this you may get **"Application failed to respond"** because Railway's domain routes to a different port. Make sure the frontend domain's **target port is also 3000** (see step 4). |

### `engine` service

Leave `DQF_API_URL` and `DQF_API_KEY` **unset**. The engine ships idle (D-04);
production engines run on the client's own infrastructure (see the checklist).

---

## 4. Deploy the API and wire the frontend URL (two-step)

`NEXT_PUBLIC_API_URL` is compiled into the frontend's JavaScript at **build time**
(the Dockerfile bakes it via `ARG`/`ENV` before `npm run build`). So the API must
have a domain *before* the frontend builds, and any change to this value requires a
**full rebuild** — not just a restart. Order matters (D-03):

1. **Deploy the `api` service.** (If the API healthcheck fails, the start command
   must run through a shell so `$PORT` expands — the repo's root `railway.toml`
   already wraps it in `sh -c '...'`.)
2. Generate its public domain: **api → Settings → Networking → Generate Domain**
   (enter `8080` if asked for a port). **Copy the domain** — e.g.
   `aegis-production-fa56.up.railway.app`.
3. On the `frontend` service → **Variables**, set the build-time variable to the
   **literal API domain** you just copied (recommended — works regardless of service name):
   ```
   NEXT_PUBLIC_API_URL=https://aegis-production-fa56.up.railway.app
   ```
   - **No trailing slash** — the app builds requests as `${NEXT_PUBLIC_API_URL}/api/v1/...`.
   - The `https://` prefix is **required**.
   - *Alternative:* if (and only if) your API service is named exactly `api`, you may
     instead use the reference variable `https://${{api.RAILWAY_PUBLIC_DOMAIN}}`.
4. **Generate the frontend domain:** **frontend → Settings → Networking → Generate
   Domain**, and set its **target port to `3000`** (matches the `PORT=3000` from step 3).
   Copy this domain — it's your dashboard URL.
5. **Deploy / redeploy the `frontend` service** so it rebuilds with the API URL baked in.
   Wait for green, then **hard-refresh** the page (Ctrl+Shift+R) to clear cached JS.

> **If login later says "Can't reach the server" with `ERR_NAME_NOT_RESOLVED` in the
> browser console (F12 → Network → the `login` request → Request URL):** the frontend
> baked a bad/old `NEXT_PUBLIC_API_URL`. Fix the variable to the literal API domain and
> **redeploy the frontend again** (a full rebuild) — then hard-refresh.

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
   **On Windows PowerShell**, `curl` is an alias for `Invoke-WebRequest` and rejects
   `-H`/`-d`. Use `Invoke-RestMethod` with a single-quoted body instead (no escaping):
   ```powershell
   $body = '{"name":"owner","email":"owner@example.com","password":"<strong-password>"}'
   $resp = Invoke-RestMethod -Uri "https://<api>.railway.app/api/v1/clients" -Method Post -ContentType "application/json" -Body $body
   $resp | ConvertTo-Json
   ```
   **Save the `api_key`** from the `201` response — it is **shown once only** and is
   the `AEGIS_API_KEY` your Airflow worker will need.

3. **Confirm login:** open `https://<frontend>.railway.app`, log in with that
   email/password. The dashboard should load with **no console CORS errors**.

4. **Point an Airflow worker at the live API.** The engine runs on the client's own
   infra (D-04). In the Airflow environment / `.env` used by the `aegis-dq` SDK, set:
   ```
   AEGIS_API_URL=https://<api>.railway.app
   AEGIS_API_KEY=<api_key saved in step 2>
   ```
   No DAG code change is needed — `aegis_dq/_client.py` reads these at import.
   (Note: these are the **SDK** variables `AEGIS_API_URL`/`AEGIS_API_KEY` — not the
   backend engine's `DQF_API_URL`/`DQF_API_KEY`, which are a different integration.)

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
