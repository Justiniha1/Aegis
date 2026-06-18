# Comet — Launch Checklist (1-2 clients)

Do these in order. Steps 2-3 are the real gate to being safe for clients.

## 1. Review and commit the work
All current changes are on branch `refactor/codebase-audit-cleanup`, uncommitted. Review the
diff, commit, and merge when ready. (Nothing is pushed automatically.)

## 2. Set the Railway environment variables (the launch gate)
On the **API service** -> Variables:

| Variable | Value |
|---|---|
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` — verify it is set; this is what persists data across redeploys |
| `JWT_SECRET_KEY` | a strong secret: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `COMET_ADMIN_TOKEN` | another generated secret (gates client provisioning) |
| `COMET_ENV` | `production` (arms the boot guardrails) |
| `ALLOWED_ORIGINS` | `https://<your-dashboard-domain>` |

If any old `AEGIS_*` variables exist, rename them to `COMET_*` (same values) — the code now
reads the `COMET_` names (`COMET_API_KEY`, `COMET_ADMIN_TOKEN`, `COMET_ENV`,
`COMET_SCHEDULER_ENABLED`).

## 3. Redeploy
If anything in step 2 is missing or unsafe, the API refuses to start and logs exactly what is
wrong (insecure JWT secret / ephemeral SQLite / missing admin token). A clean boot means you
are configured safely.

## 4. Register the CLI command locally
```
pip install -e .
```
This replaces the old `aegis` command with `comet` (the entry point name changed).

## 5. Provision your first client
```
COMET_API_URL=https://aegis-production-fa56.up.railway.app \
COMET_ADMIN_TOKEN=<the token from step 2> \
python Scripts/provision_client.py --name "Client Co" --email them@co.com --password "<temp>"
```
Prints the client's API key (once) and login. They:
- log into the dashboard with the email/password, and
- put the API key in their environment as `COMET_API_KEY` for the CLI/engine.

## Optional (anytime, not required to launch)
- Rename the Railway **service** (changes the URL) -> then update `DEFAULT_API_URL` in
  `comet_dq/_client.py`.
- Rename the repo **root folder** from `Aegis` to `Comet` and update the git remote.
- Add the frontend Settings field for the alert webhook (today the operator sets it via
  `PATCH /api/v1/clients/me`).
- Wire the Resend email alert channel (hook point is stubbed in `dashboard_api/alerts.py`).
