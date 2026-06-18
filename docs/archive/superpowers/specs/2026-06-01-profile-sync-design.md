# Connection Profile Sync — Design Spec

> ⚠️ **SUPERSEDED (2026-06-02).** This spec describes the original
> structured-columns + encrypted-secret + two-way-CRUD design. That approach was
> **built and then reverted** during the Phase 8 session in favor of a simpler
> **file-driven** model:
> - Profiles are defined in `backend/config/database_connection.yaml` (one source
>   of truth); secrets stay as `${ENV}` refs resolved at run time — **no encryption
>   key, no DB-stored secrets**.
> - `comet push` uploads the whole YAML to `POST /api/v1/profiles/sync`, stored
>   per-client; the dashboard prefers the uploaded YAML over the on-disk file
>   (`dashboard_api/connection_source.py`).
> - `GET /api/v1/profiles` returns `{name, is_default}` only; the Settings page is
>   **selector-only** (no add/edit/delete).
> - Server-side runs resolve connections via the engine's own resolver
>   (`backend/core/config_loader.py`).
>
> Kept for historical context only. Do not implement from this document.

**Date:** 2026-06-01
**Milestone:** v1.2 — First Client Handoff (added as **Phase 8**)
**Status:** Superseded — see banner above

---

## Problem

Comet has **two disconnected connection-profile systems** that only sync one way, partially:

1. **Local YAML** (`backend/config/database_connection.yaml` for the engine; `comet/database_connection.yaml` for the CLI) — defines profiles (`dev`, `staging`, `prod_*`). Consumed by the CLI / local test engine via `backend/core/config_loader.py`. The dashboard never reads it.
2. **Dashboard DB** (`connection_profiles` table) — what the Settings → "Active Environment" page shows. `GET /api/v1/profiles` (`dashboard_api/routers/profiles.py`) reads **only** the database.

The only bridge is `comet push` (`cli/commands/push.py`), which is one-directional and incomplete:
- Reads `comet/database_connection.yaml`, converts each profile to a connection URL, POSTs it.
- **`comet pull` does not pull profiles back** (only test definitions).
- UI create/delete writes **only** to the DB, never back to YAML.

**Symptom:** the Settings page shows only `dev`, even though the YAML defines several profiles — because only `dev` (SQLite, literal path, no secret) ever lands in the DB.

**Two latent bugs in the current `push`:**
- It does **not** resolve `${ENV_VAR}` before building the connection URL, so `staging`/`prod_*` push a literally-broken URL string.
- It only ever **creates** (HTTP 409 ⇒ skip); it never **updates** or **deletes**, so it is not actually a mirror.

## Goal

A **two-way sync** of connection profiles between local YAML and the dashboard DB that:
- Keeps **secrets out of the tracked YAML file** (never plaintext-at-rest in the repo).
- Lets the user **`comet pull` and have it just work** for any profile whose secret they already hold.
- Makes the **UI explicit** about what a user must do locally when they create a profile in the browser.
- **Never silently overrides** local customizations (env-var names, structure) on either side.

## Non-Goals (YAGNI)

- Reversible secret escrow / key-management crypto (considered, rejected as over-engineered).
- Per-profile timestamp/last-write-wins merge (rejected; whole-set, command-direction-wins is sufficient).
- A separate encrypted local credential vault file (rejected; secrets resolve from environment variables).
- Live file-writing from the cloud dashboard (sync happens via the `pull` command, not a server pushing to disk).

---

## Core decisions (locked)

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | **Two-way sync**, both sides editable | Matches how test definitions already round-trip (push up / pull down). |
| D2 | **Command-direction wins, whole-set** | `push` makes the DB match YAML; `pull` makes YAML match the DB. No timestamps, no merge. Predictable; mirrors how `pull` already overwrites `test_definitions.yaml`. Guarded by diff + confirm. |
| D3 | **Secrets resolved from environment variables only** — no plaintext in tracked YAML, no sidecar file | Preserves the existing `${ENV_VAR}` security model; nothing new to protect on disk. |
| D4 | **The env-var NAME is non-secret structure** — stored on the dashboard and round-tripped; only the VALUE stays local | This is the keystone that lets `pull` write a usable `${VAR}` reference *and* tell the user exactly which variable to set, even for a profile they've never seen. |
| D5 | **Dashboard stores the encrypted secret VALUE** (for server-side / UI-created runs); the API **never returns it** | Keeps frictionless browser self-serve while preserving the "never returned" posture the system already has. |
| D6 | **`ruamel.yaml` in-place update** for `pull` | Preserves the file's extensive documentation comments and formatting. |
| D7 | Delivered as **Phase 8 of the current v1.2 milestone** (not a new v1.3) | Per user preference. Reopens v1.2 until complete. |

---

## Data model

A profile is split into three data categories:

| Category | Examples | On dashboard? | Returned by API? | In tracked YAML? |
|---|---|---|---|---|
| **Structure** (non-secret) | `db_type`, `host`, `port`, `database`, `username`, sqlite `path` | ✅ plaintext columns | ✅ yes | ✅ yes |
| **Secret reference** (env var *name*) | `secret_env: COMET_STAGING_PASSWORD` | ✅ plaintext column | ✅ yes | ✅ yes, as `${...}` |
| **Secret value** (password/token) | the actual password | ✅ encrypted | ❌ **never** | ❌ never — env var only |

### `connection_profiles` table changes

Replace the single `connection_url_encrypted` column with:

- `db_type` (existing) — `postgresql` | `mysql` | `sqlite` | …
- `host`, `port`, `database`, `username` — nullable structure
- `sqlite_path` — nullable (for SQLite profiles)
- `secret_env` — nullable; the env var name expected to hold the secret. Null for secretless profiles (e.g. SQLite `dev`).
- `secret_encrypted` — nullable; encrypted secret value, used **only** for dashboard-triggered runs; never returned by any endpoint.

Unique constraint `(client_id, name)` retained.

### `secret_env` semantics

- **Default:** `COMET_<PROFILENAME>_PASSWORD` (uppercase, profile name sanitized to `[A-Z0-9_]`). E.g. profile `staging` → `COMET_STAGING_PASSWORD`.
- **Editable on both sides:**
  - In YAML: whatever `${VAR}` the user writes (e.g. `${STAGING_DB_PASSWORD}`).
  - In the UI: an editable "Environment variable name" field, pre-filled with the default.
- **Round-trips:** because `secret_env` is a stored, returned field, neither side regenerates it from scratch. A user's `${STAGING_DB_PASSWORD}` survives a `pull` unchanged.
- **Rename = explicit warning** (anti-footgun): since the env var *value* lives only in the environment, renaming `secret_env` means the environment must now provide a variable under the new name. Both the UI and `comet pull` warn loudly on a rename.

---

## API contract changes

`dashboard_api/schemas.py`:

- **`ConnectionProfileCreate`** (inbound) — replace `connection_url: str` with structured fields:
  - `name`, `db_type`, `host?`, `port?`, `database?`, `username?`, `sqlite_path?`, `secret_env?`, `secret_value?` (plaintext password; encrypted before storage; optional so a push from a machine lacking the secret can omit it).
- **`ConnectionProfileOut`** (outbound) — return `id, name, db_type, host, port, database, username, sqlite_path, secret_env, created_at`. **Never** `secret_value` / `secret_encrypted`.
- **Update endpoint:** add `PUT /api/v1/profiles/{id}` (or `POST` upsert by name) for `push` to update existing profiles. `delete` already exists.

`dashboard_api/routers/profiles.py`:

- `create`/`update` encrypt `secret_value` into `secret_encrypted` **only when provided**; when omitted, the existing `secret_encrypted` is **preserved** (no-clobber).
- `runs.py` connection building: reconstruct the connection URL at run time from structure + decrypted `secret_encrypted`.

---

## Sync semantics

### `comet push` (local YAML → dashboard) — whole-set mirror

1. Parse each profile's **structure** from `comet/database_connection.yaml`.
2. Derive `secret_env`: the `${VAR}` referenced by the profile's secret field, or the `COMET_<NAME>_PASSWORD` default.
3. Resolve the secret **value** from `os.environ[secret_env]`.
4. **No-clobber rule:** if the env var is **set**, send `secret_value` (dashboard re-encrypts). If **unset**, omit `secret_value` → dashboard **keeps its existing** `secret_encrypted`. Emit `⚠ <VAR> not set — kept existing dashboard secret`.
5. **Reconcile the set:** create new profiles, update changed structure/`secret_env`/secret, **delete** profiles absent from YAML.
6. **Guarded:** show a diff and **confirm** before applying (especially deletes). Flags: `--dry-run` (preview only), `--yes` (skip confirm, for CI).
7. **Bug fixes folded in:** `${ENV}` is now actually resolved; push now updates/deletes (not create-only).

### `comet pull` (dashboard → local YAML)

1. `GET /api/v1/profiles` → structure + `secret_env` (never the secret).
2. Load existing `database_connection.yaml` with `ruamel.yaml` (round-trip). Update/add/remove **only** the profile mappings in place; preserve all documentation comments and formatting.
3. For each profile, write structure + the secret field as `${secret_env}` (e.g. `password: ${COMET_STAGING_PASSWORD}`). Secretless profiles (SQLite) get no secret field.
4. Show a diff and **confirm** before writing (`--yes` to skip).
5. Print a **readiness report**:
   ```
   dev      sqlite     ✓ no secret needed
   staging  postgres   needs $COMET_STAGING_PASSWORD   [NOT SET]
   ```

### Round-trip guarantee

Because structure and `secret_env` are stored and returned, `pull → push → pull` is a **no-op**: the YAML returns byte-identical (modulo the comment-preserving writer), and secret *values* never appear in the file, so they cannot produce phantom diffs.

---

## UI / UX

**Create-profile form** (`frontend` Settings):
- Structure fields: `type`, `host`, `port`, `database`, `username` (or `path` for SQLite).
- **Password** field — stored encrypted (D5).
- **"Environment variable name"** field — editable, pre-filled with `COMET_<NAME>_PASSWORD`, helptext: *"Local CLI runs read this profile's secret from this environment variable."*

**After-create confirmation panel** (the key clarity moment):
> ✓ **`staging` is ready for dashboard runs.**
> To use it from your local machine:
> 1. Run `comet pull`
> 2. Set `COMET_STAGING_PASSWORD` in your shell *(click to copy)*

**Editing `secret_env` in the UI** → warning modal: *"This changes which environment variable runs read. The environment (your shell locally, Railway in the cloud) must provide `NEW_NAME`, or runs will fail until it does."*

**Profile list** shows `name`, `db_type`, and the expected `secret_env` — never the secret. The Phase-6 "Active Environment" switcher is functionally unchanged; it will now display multiple rows.

---

## Migration & rollout

- **No Alembic** in this project. Dev: schema change requires `docker compose down -v` (drops data).
- **Railway Postgres:** a one-time manual migration (add columns, drop `connection_url_encrypted`) **or** an accepted data reset. Exact SQL/steps to be specified in the plan; treated as a **human gate**.
- New dependency: `ruamel.yaml` added to the CLI/engine requirements.

---

## Testing

Unit + integration coverage:

- **Env resolution:** `${VAR}` parsing; default `COMET_<NAME>_PASSWORD` derivation; sanitization of profile names into valid env var names.
- **Push reconcile:** create / update / delete; **unset-env no-clobber** (omitting secret preserves dashboard's existing `secret_encrypted`); `${ENV}` resolution bug fixed.
- **Pull:** `ruamel` in-place update preserves comments; structure + `${secret_env}` written correctly; secretless profiles handled.
- **Round-trip:** `pull → push → pull` is a no-op.
- **API contract:** outbound schema returns structure + `secret_env`, and **never** the secret (regression guard).
- **UI:** create flow surfaces the env-var instruction; rename warning fires.

---

## Open items to confirm during planning

- Exact Railway migration steps (manual SQL vs. reset).
- Whether `push` upserts via `POST` (name-keyed) or a dedicated `PUT /{id}`.
- Whether the local engine path (`backend/core/config_loader.py`) and the CLI file (`comet/database_connection.yaml`) should converge to a single file location, or remain distinct.
