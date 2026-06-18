# Connection Profile Sync — Implementation Plan

> ⚠️ **SUPERSEDED (2026-06-02).** This plan implements the structured-columns +
> encrypted-secret + two-way-CRUD design, which was **built and then reverted** in
> favor of a file-driven model (profiles in `database_connection.yaml`, `comet push`
> → `POST /api/v1/profiles/sync`, selector-only Settings, `${ENV}` secrets resolved
> at run time — no Fernet encryption). See the design spec's superseded banner for
> the final model. Kept for historical context only; do not execute.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make connection profiles sync two-way between local YAML and the dashboard DB, keeping secrets out of the tracked file by storing only the *name* of the env var that holds each secret.

**Architecture:** Split a profile into structure (non-secret, stored+returned), a secret-env-var *name* (non-secret, stored+returned), and a secret *value* (encrypted on the dashboard for server-side runs, never returned, resolved locally from the environment). `comet push` mirrors local→DB; `comet pull` rewrites local YAML in place (preserving comments via `ruamel.yaml`). Both are whole-set, command-direction-wins, guarded by diff+confirm.

**Tech Stack:** FastAPI + SQLAlchemy 2.0 + Pydantic 2 (dashboard_api), Typer + requests + ruamel.yaml (CLI), Next.js + React + TypeScript (frontend), Fernet encryption (existing).

**Spec:** `docs/superpowers/specs/2026-06-01-profile-sync-design.md`

**Three parts, in order. Each part ends in working, testable software:**
- **Part A — Backend data model + API.** Dashboard stores structured profiles + `secret_env`, returns them (never the secret), and runs reconstruct the connection URL.
- **Part B — CLI sync.** `push` reconciles (create/update/delete, env-resolved, no-clobber); `pull` rewrites YAML in place + readiness report.
- **Part C — Frontend.** Create form with structured fields + editable env-var name; after-create instructions; rename warning; list shows `secret_env`.

---

## ⚠️ Human gate: schema migration (do this before Part A Task A2 runs against a real DB)

There is **no Alembic** in this project. The `connection_profiles` table changes shape (drop `connection_url_encrypted`, add structured columns).

- **Local dev:** `docker compose down -v` then `docker compose up` recreates the schema (drops all data). Then re-seed: `make seed`.
- **Railway (live):** the Postgres volume persists, so the table must be migrated by hand. Connect (`railway connect Postgres` or the dashboard SQL console) and run:
  ```sql
  ALTER TABLE connection_profiles ADD COLUMN host VARCHAR;
  ALTER TABLE connection_profiles ADD COLUMN port INTEGER;
  ALTER TABLE connection_profiles ADD COLUMN database VARCHAR;
  ALTER TABLE connection_profiles ADD COLUMN username VARCHAR;
  ALTER TABLE connection_profiles ADD COLUMN sqlite_path VARCHAR;
  ALTER TABLE connection_profiles ADD COLUMN secret_env VARCHAR;
  ALTER TABLE connection_profiles ADD COLUMN secret_encrypted VARCHAR;
  -- existing rows: their old connection_url_encrypted is now orphaned. Re-create them via `comet push` after deploy.
  ALTER TABLE connection_profiles DROP COLUMN connection_url_encrypted;
  ```
  This is a one-time manual step. After it, re-push profiles. **Confirm with the user before running against the live DB.**

---

## File Structure

**Part A (backend):**
- Modify `dashboard_api/models.py` — `ConnectionProfile` columns.
- Create `dashboard_api/profile_url.py` — `build_connection_url(profile, secret_value)`; single source of URL assembly.
- Modify `dashboard_api/schemas.py` — `ConnectionProfileCreate`, `ConnectionProfileUpdate`, `ConnectionProfileOut`.
- Modify `dashboard_api/routers/profiles.py` — upsert-on-create no-clobber, `PUT /{id}`, structured list.
- Modify `dashboard_api/run_executor.py:112-136` — rebuild URL from structure + secret.
- Tests: `tests/test_dashboard_api/test_profiles.py`, `tests/test_dashboard_api/test_profile_url.py`.

**Part B (CLI):**
- Modify `pyproject.toml` — add `ruamel.yaml`.
- Create `cli/profiles_sync.py` — YAML↔payload parsing, `secret_env` derivation, env resolution.
- Modify `cli/commands/push.py` — reconcile + flags.
- Modify `cli/commands/pull.py` — pull profiles + ruamel in-place rewrite + readiness report.
- Modify `cli/api_client.py` — add `put`, `delete`.
- Tests: `tests/test_cli/test_profiles_sync.py`, `tests/test_cli/test_push_pull_profiles.py`.

**Part C (frontend):**
- Modify `frontend/src/lib/types.ts` — `ProfileOut` structured fields.
- Modify `frontend/src/lib/api.ts` — `createProfile`/`updateProfile` payloads.
- Modify `frontend/src/app/dashboard/settings/page.tsx` — form + after-create panel + rename warning + list.

> **Frontend note (read first):** `frontend/AGENTS.md` warns this is a non-standard Next.js — read `node_modules/next/dist/docs/` before writing frontend code. There is no JS unit-test harness in this repo, so Part C tasks verify in the browser (`make start`), consistent with the project's existing manual-UAT approach.

---

# PART A — Backend data model + API

### Task A1: Reshape the `ConnectionProfile` model

**Files:**
- Modify: `dashboard_api/models.py:81-93`

- [ ] **Step 1: Replace the model body**

Replace lines 81-93 with:

```python
class ConnectionProfile(Base):
    __tablename__ = "connection_profiles"

    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    name = Column(String, nullable=False)          # e.g. "production", "dev"
    db_type = Column(String, nullable=False)       # "postgresql" | "mysql" | "sqlite" | "mssql"

    # Structure (non-secret) — returned by the API, written into local YAML.
    host = Column(String, nullable=True)
    port = Column(Integer, nullable=True)
    database = Column(String, nullable=True)
    username = Column(String, nullable=True)
    sqlite_path = Column(String, nullable=True)

    # secret_env: the env var NAME holding this profile's secret (non-secret label).
    # Null for secretless profiles (e.g. SQLite). Returned by the API.
    secret_env = Column(String, nullable=True)
    # secret_encrypted: the secret VALUE, encrypted; used only for server-side runs.
    # NEVER returned by any endpoint. Null until a secret is supplied.
    secret_encrypted = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_profiles_client_name", "client_id", "name", unique=True),
    )
```

- [ ] **Step 2: Verify the app imports cleanly**

Run: `python -c "import dashboard_api.models"`
Expected: no output, exit 0 (no import errors).

- [ ] **Step 3: Commit**

```bash
git add dashboard_api/models.py
git commit -m "feat(profiles): reshape ConnectionProfile to structured columns + secret_env"
```

---

### Task A2: Connection-URL builder (single source of assembly)

**Files:**
- Create: `dashboard_api/profile_url.py`
- Test: `tests/test_dashboard_api/test_profile_url.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dashboard_api/test_profile_url.py
import pytest
from types import SimpleNamespace
from dashboard_api.profile_url import build_connection_url


def _profile(**kw):
    base = dict(db_type="postgresql", host="db.example.com", port=5432,
                database="analytics", username="reader", sqlite_path=None)
    base.update(kw)
    return SimpleNamespace(**base)


def test_postgres_url_with_secret():
    url = build_connection_url(_profile(), "p@ss/word")
    assert url == "postgresql://reader:p%40ss%2Fword@db.example.com:5432/analytics"


def test_mysql_uses_pymysql_driver():
    url = build_connection_url(_profile(db_type="mysql", port=3306), "pw")
    assert url == "mysql+pymysql://reader:pw@db.example.com:3306/analytics"


def test_sqlite_uses_path_and_ignores_secret():
    p = _profile(db_type="sqlite", host=None, port=None, database=None,
                 username=None, sqlite_path="/app/data/sample.db")
    assert build_connection_url(p, None) == "sqlite:////app/data/sample.db"


def test_missing_secret_for_password_db_raises():
    with pytest.raises(ValueError, match="requires a secret"):
        build_connection_url(_profile(), None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_dashboard_api/test_profile_url.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'dashboard_api.profile_url'`

- [ ] **Step 3: Implement**

```python
# dashboard_api/profile_url.py
"""Reconstruct a SQLAlchemy connection URL from a stored ConnectionProfile + its secret.

Single source of URL assembly so the run executor and tests agree. The secret VALUE
is never stored in the URL at rest — it is supplied at call time (decrypted from
secret_encrypted, or resolved from the environment).
"""
from urllib.parse import quote_plus

_DRIVERS = {
    "postgresql": "postgresql",
    "postgres": "postgresql",
    "mysql": "mysql+pymysql",
    "mssql": "mssql+pyodbc",
}


def build_connection_url(profile, secret_value: str | None) -> str:
    db_type = (profile.db_type or "").lower()

    if db_type == "sqlite":
        path = profile.sqlite_path or ""
        # sqlite:////abs/path  (four slashes => absolute)
        return f"sqlite:///{path}" if not path.startswith("/") else f"sqlite:///{path}"

    driver = _DRIVERS.get(db_type)
    if driver is None:
        raise ValueError(f"Unsupported db_type '{profile.db_type}' for URL assembly")

    if secret_value is None:
        raise ValueError(f"Profile '{getattr(profile, 'name', '?')}' ({db_type}) requires a secret")

    user = quote_plus(profile.username or "")
    pw = quote_plus(secret_value)
    host = profile.host or "localhost"
    port = profile.port
    database = profile.database or ""
    hostpart = f"{host}:{port}" if port else host
    return f"{driver}://{user}:{pw}@{hostpart}/{database}"
```

> Note: the sqlite branch above intentionally yields `sqlite:///` + path. For an absolute POSIX path `/app/data/sample.db` that produces `sqlite:////app/data/sample.db` (the four-slash absolute form) because the path already starts with `/`. The conditional is written explicitly so the intent is obvious to a future reader.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_dashboard_api/test_profile_url.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add dashboard_api/profile_url.py tests/test_dashboard_api/test_profile_url.py
git commit -m "feat(profiles): add build_connection_url assembler + tests"
```

---

### Task A3: Update the profile schemas

**Files:**
- Modify: `dashboard_api/schemas.py:158-172`

- [ ] **Step 1: Replace the Connection Profiles schema block**

Replace lines 158-172 (the `# ── Connection Profiles ──` block) with:

```python
# ── Connection Profiles ───────────────────────────────────────────────────────

class ConnectionProfileCreate(BaseModel):
    name: str = Field(..., max_length=128)
    db_type: str                              # postgresql | mysql | sqlite | mssql
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    username: Optional[str] = None
    sqlite_path: Optional[str] = None
    secret_env: Optional[str] = None          # env var NAME (non-secret); defaulted server-side if omitted
    secret_value: Optional[str] = None         # plaintext secret; encrypted before storage; never returned


class ConnectionProfileUpdate(BaseModel):
    db_type: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    username: Optional[str] = None
    sqlite_path: Optional[str] = None
    secret_env: Optional[str] = None
    secret_value: Optional[str] = None         # if omitted, the existing encrypted secret is preserved


class ConnectionProfileOut(BaseModel):
    id: int
    name: str
    db_type: str
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    username: Optional[str] = None
    sqlite_path: Optional[str] = None
    secret_env: Optional[str] = None
    created_at: datetime
    # NOTE: secret_value / secret_encrypted are deliberately absent — never returned.

    model_config = {"from_attributes": True}
```

- [ ] **Step 2: Verify import**

Run: `python -c "import dashboard_api.schemas"`
Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add dashboard_api/schemas.py
git commit -m "feat(profiles): structured profile schemas; secret never in ConnectionProfileOut"
```

---

### Task A4: Rewrite the profiles router (upsert no-clobber + PUT)

**Files:**
- Modify: `dashboard_api/routers/profiles.py` (whole file)
- Test: `tests/test_dashboard_api/test_profiles.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_dashboard_api/test_profiles.py
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client_and_headers(api_client_factory):
    """Provides (TestClient, auth_headers) for one fresh client.
    api_client_factory is the existing fixture used by other dashboard_api tests
    (creates a client + returns its API key header). See tests/test_dashboard_api/conftest.py."""
    return api_client_factory()


def _create(c, headers, **body):
    return c.post("/api/v1/profiles", json=body, headers=headers)


def test_create_returns_structure_never_secret(client_and_headers):
    c, h = client_and_headers
    r = _create(c, h, name="staging", db_type="postgresql", host="h", port=5432,
                database="analytics", username="reader",
                secret_env="COMET_STAGING_PASSWORD", secret_value="s3cret")
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "staging"
    assert body["secret_env"] == "COMET_STAGING_PASSWORD"
    assert "secret_value" not in body and "secret_encrypted" not in body


def test_create_existing_name_updates_in_place(client_and_headers):
    c, h = client_and_headers
    _create(c, h, name="staging", db_type="postgresql", host="old", username="u", secret_value="x")
    r = _create(c, h, name="staging", db_type="postgresql", host="new", username="u", secret_value="x")
    assert r.status_code == 201           # upsert, not 409
    assert r.json()["host"] == "new"
    # only one row exists
    listed = c.get("/api/v1/profiles", headers=h).json()
    assert [p["name"] for p in listed].count("staging") == 1


def test_update_without_secret_preserves_existing_secret(client_and_headers, db_session_for):
    c, h = client_and_headers
    pid = _create(c, h, name="staging", db_type="postgresql", host="h", username="u",
                  secret_value="keepme").json()["id"]
    # update structure only, omit secret_value
    r = c.put(f"/api/v1/profiles/{pid}", json={"host": "h2"}, headers=h)
    assert r.status_code == 200
    # secret_encrypted must be unchanged (decrypts to keepme)
    from dashboard_api import models
    from dashboard_api.encryption import decrypt
    row = db_session_for(h).query(models.ConnectionProfile).filter_by(id=pid).first()
    assert decrypt(row.secret_encrypted) == "keepme"


def test_sqlite_profile_no_secret(client_and_headers):
    c, h = client_and_headers
    r = _create(c, h, name="dev", db_type="sqlite", sqlite_path="/app/data/x.db")
    assert r.status_code == 201
    assert r.json()["secret_env"] is None
```

> The fixtures `api_client_factory` and `db_session_for` follow the existing dashboard_api test setup. If they are not present in `tests/test_dashboard_api/conftest.py`, add thin wrappers there mirroring how `tests/test_dashboard_api/` already builds a `TestClient` and seeds a client+API key (grep existing tests: `grep -rn "TestClient" tests/test_dashboard_api`). Do not invent a new auth path.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_dashboard_api/test_profiles.py -v`
Expected: FAIL — the endpoints still use the old `connection_url` shape.

- [ ] **Step 3: Implement the router**

Replace the whole file `dashboard_api/routers/profiles.py` with:

```python
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from dashboard_api import models, schemas
from dashboard_api.auth import get_client_any_auth
from dashboard_api.database import get_db
from dashboard_api.encryption import encrypt

router = APIRouter(prefix="/api/v1/profiles", tags=["profiles"])

# Fields copied straight from create/update bodies onto the model row.
_STRUCT_FIELDS = ("db_type", "host", "port", "database", "username", "sqlite_path", "secret_env")


def _default_secret_env(name: str) -> str:
    safe = "".join(ch if ch.isalnum() else "_" for ch in name).upper()
    return f"COMET_{safe}_PASSWORD"


@router.post("", response_model=schemas.ConnectionProfileOut, status_code=201)
def upsert_profile(
    body: schemas.ConnectionProfileCreate,
    db: Session = Depends(get_db),
    client: models.Client = Depends(get_client_any_auth),
):
    """Create or update a profile by (client_id, name). Upsert so `comet push` is idempotent.

    Secret handling (no-clobber): if secret_value is provided it is encrypted and stored;
    if omitted, any existing secret is preserved.
    """
    row = db.query(models.ConnectionProfile).filter(
        models.ConnectionProfile.client_id == client.id,
        models.ConnectionProfile.name == body.name,
    ).first()

    is_new = row is None
    if is_new:
        row = models.ConnectionProfile(client_id=client.id, name=body.name)

    for f in _STRUCT_FIELDS:
        setattr(row, f, getattr(body, f))

    # Secretless dbs (sqlite) carry no secret_env.
    if (row.db_type or "").lower() == "sqlite":
        row.secret_env = None
    elif row.secret_env is None:
        row.secret_env = _default_secret_env(body.name)

    if body.secret_value is not None:
        row.secret_encrypted = encrypt(body.secret_value)

    if is_new:
        db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("", response_model=list[schemas.ConnectionProfileOut])
def list_profiles(
    db: Session = Depends(get_db),
    client: models.Client = Depends(get_client_any_auth),
):
    return db.query(models.ConnectionProfile).filter(
        models.ConnectionProfile.client_id == client.id
    ).order_by(models.ConnectionProfile.name.asc()).all()


@router.put("/{profile_id}", response_model=schemas.ConnectionProfileOut)
def update_profile(
    profile_id: int,
    body: schemas.ConnectionProfileUpdate,
    db: Session = Depends(get_db),
    client: models.Client = Depends(get_client_any_auth),
):
    row = db.query(models.ConnectionProfile).filter(
        models.ConnectionProfile.id == profile_id,
        models.ConnectionProfile.client_id == client.id,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Profile not found")

    for f in _STRUCT_FIELDS:
        val = getattr(body, f)
        if val is not None:
            setattr(row, f, val)

    if (row.db_type or "").lower() == "sqlite":
        row.secret_env = None

    if body.secret_value is not None:          # no-clobber: only overwrite when supplied
        row.secret_encrypted = encrypt(body.secret_value)

    db.commit()
    db.refresh(row)
    return row


@router.delete("/{profile_id}", status_code=204)
def delete_profile(
    profile_id: int,
    db: Session = Depends(get_db),
    client: models.Client = Depends(get_client_any_auth),
):
    row = db.query(models.ConnectionProfile).filter(
        models.ConnectionProfile.id == profile_id,
        models.ConnectionProfile.client_id == client.id,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Profile not found")
    db.delete(row)
    db.commit()
    return Response(status_code=204)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_dashboard_api/test_profiles.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add dashboard_api/routers/profiles.py tests/test_dashboard_api/test_profiles.py
git commit -m "feat(profiles): upsert-on-create no-clobber, PUT update, structured list"
```

---

### Task A5: Rebuild the connection URL in the run executor

**Files:**
- Modify: `dashboard_api/run_executor.py:100` (import) and `:112-136` (profile load → URL)

- [ ] **Step 1: Update the import line**

At `dashboard_api/run_executor.py:100`, change:

```python
    from dashboard_api.encryption import decrypt
```
to:
```python
    from dashboard_api.encryption import decrypt
    from dashboard_api.profile_url import build_connection_url
```

- [ ] **Step 2: Replace the decrypt-URL block**

Replace lines 127-136 (the `try: connection_url = decrypt(...)` block through the `connections = {...}` line) with:

```python
        try:
            secret = decrypt(conn_row.secret_encrypted) if conn_row.secret_encrypted else None
            connection_url = build_connection_url(conn_row, secret)
        except Exception as e:
            run.status = "FAILED"
            run.error_reason = _sanitize_error(
                f"Could not build connection for profile '{profile}': {e}"
            )
            run.completed_at = datetime.utcnow()
            db.commit()
            return

        connections = {profile: {"connection_url": connection_url}}
```

- [ ] **Step 3: Verify import + existing run-executor tests still pass**

Run: `python -c "import dashboard_api.run_executor"`
Then: `pytest tests/test_dashboard_api -v`
Expected: import exit 0; existing executor/profile tests PASS (update any test that constructed a profile with `connection_url_encrypted=` to use the new columns — grep: `grep -rn "connection_url_encrypted" tests/`).

- [ ] **Step 4: Commit**

```bash
git add dashboard_api/run_executor.py
git commit -m "feat(profiles): rebuild run connection URL from structure + decrypted secret"
```

**✅ Part A done — the dashboard now stores structured profiles, returns them without secrets, and runs reconstruct the URL.**

---

# PART B — CLI sync

### Task B1: Add the `ruamel.yaml` dependency

**Files:**
- Modify: `pyproject.toml:9-16`

- [ ] **Step 1: Add the dependency**

In `pyproject.toml`, change the `dependencies` list (lines 10-15) to include ruamel:

```toml
dependencies = [
    "typer>=0.12",
    "requests>=2.31",
    "pyyaml>=6.0",
    "ruamel.yaml>=0.18",
    "python-dotenv>=1.0",
    "cryptography>=42.0",
    "rich>=13.0",
]
```

- [ ] **Step 2: Install it**

Run: `pip install "ruamel.yaml>=0.18"`
Expected: installs successfully.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "build(cli): add ruamel.yaml for comment-preserving YAML rewrite"
```

---

### Task B2: Profile sync helpers (parse, derive env name, resolve)

**Files:**
- Create: `cli/profiles_sync.py`
- Test: `tests/test_cli/test_profiles_sync.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_cli/test_profiles_sync.py
from cli.profiles_sync import (
    default_secret_env, parse_yaml_profile, profile_to_payload, env_ref_or_none,
)


def test_default_secret_env():
    assert default_secret_env("staging") == "COMET_STAGING_PASSWORD"
    assert default_secret_env("prod-mysql") == "COMET_PROD_MYSQL_PASSWORD"


def test_env_ref_extracts_var_name():
    assert env_ref_or_none("${STAGING_DB_PASSWORD}") == "STAGING_DB_PASSWORD"
    assert env_ref_or_none("literalpw") is None
    assert env_ref_or_none(None) is None


def test_parse_postgres_profile_uses_yaml_env_ref():
    p = parse_yaml_profile("staging", {
        "type": "postgres", "host": "h", "port": 5432, "database": "db",
        "username": "u", "password": "${STAGING_DB_PASSWORD}",
    })
    assert p["db_type"] == "postgresql"
    assert p["host"] == "h" and p["port"] == 5432 and p["database"] == "db"
    assert p["secret_env"] == "STAGING_DB_PASSWORD"


def test_parse_postgres_literal_password_defaults_env_name():
    p = parse_yaml_profile("staging", {"type": "postgres", "host": "h", "username": "u", "password": "raw"})
    assert p["secret_env"] == "COMET_STAGING_PASSWORD"
    assert p["_literal_secret"] == "raw"     # carried so push can send it


def test_parse_sqlite_has_no_secret():
    p = parse_yaml_profile("dev", {"type": "sqlite", "path": "/app/data/x.db"})
    assert p["db_type"] == "sqlite" and p["sqlite_path"] == "/app/data/x.db"
    assert p["secret_env"] is None


def test_profile_to_payload_resolves_env(monkeypatch):
    monkeypatch.setenv("STAGING_DB_PASSWORD", "fromenv")
    p = parse_yaml_profile("staging", {"type": "postgres", "host": "h", "username": "u",
                                       "password": "${STAGING_DB_PASSWORD}"})
    payload, warn = profile_to_payload("staging", p)
    assert payload["secret_value"] == "fromenv"
    assert payload["secret_env"] == "STAGING_DB_PASSWORD"
    assert warn is None


def test_profile_to_payload_unset_env_omits_secret_and_warns(monkeypatch):
    monkeypatch.delenv("STAGING_DB_PASSWORD", raising=False)
    p = parse_yaml_profile("staging", {"type": "postgres", "host": "h", "username": "u",
                                       "password": "${STAGING_DB_PASSWORD}"})
    payload, warn = profile_to_payload("staging", p)
    assert "secret_value" not in payload          # no-clobber: don't send a secret we don't have
    assert "STAGING_DB_PASSWORD" in warn
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_cli/test_profiles_sync.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'cli.profiles_sync'`

- [ ] **Step 3: Implement**

```python
# cli/profiles_sync.py
"""Parse local YAML profiles into dashboard API payloads, and back.

Secret model: the env var NAME is non-secret and travels; the env var VALUE is
resolved locally and only sent when present (no-clobber). SQLite profiles carry
no secret.
"""
import os
import re

_TYPE_MAP = {"postgres": "postgresql", "postgresql": "postgresql",
             "mysql": "mysql", "sqlite": "sqlite", "mssql": "mssql"}

_ENV_REF = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")


def default_secret_env(name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9]", "_", name).upper()
    return f"COMET_{safe}_PASSWORD"


def env_ref_or_none(value):
    """If value is exactly '${VAR}', return VAR; else None."""
    if not isinstance(value, str):
        return None
    m = _ENV_REF.match(value.strip())
    return m.group(1) if m else None


def parse_yaml_profile(name: str, profile: dict) -> dict:
    """Normalize one YAML profile dict into a structured intermediate.

    Keys: db_type, host, port, database, username, sqlite_path, secret_env,
    and optionally _literal_secret (when the YAML embedded a non-${} password).
    """
    db_type = _TYPE_MAP.get(str(profile.get("type", "")).lower(), str(profile.get("type", "")).lower())
    out = {"db_type": db_type, "host": None, "port": None, "database": None,
           "username": None, "sqlite_path": None, "secret_env": None}

    if db_type == "sqlite":
        out["sqlite_path"] = profile.get("path")
        return out

    out["host"] = profile.get("host")
    out["port"] = profile.get("port")
    out["database"] = profile.get("database")
    out["username"] = profile.get("username")

    raw_pw = profile.get("password")
    ref = env_ref_or_none(raw_pw)
    if ref:
        out["secret_env"] = ref
    else:
        out["secret_env"] = default_secret_env(name)
        if raw_pw:                              # literal password present in YAML
            out["_literal_secret"] = raw_pw
    return out


def profile_to_payload(name: str, parsed: dict):
    """Build the POST body for /api/v1/profiles. Returns (payload, warning_or_None).

    Secret value is taken from the literal YAML password if present, else resolved
    from os.environ[secret_env]. If neither is available, secret_value is omitted
    (the dashboard keeps any existing secret) and a warning string is returned.
    """
    payload = {
        "name": name,
        "db_type": parsed["db_type"],
        "host": parsed["host"],
        "port": parsed["port"],
        "database": parsed["database"],
        "username": parsed["username"],
        "sqlite_path": parsed["sqlite_path"],
        "secret_env": parsed["secret_env"],
    }
    warning = None
    if parsed["db_type"] != "sqlite":
        secret = parsed.get("_literal_secret")
        if secret is None and parsed["secret_env"]:
            secret = os.environ.get(parsed["secret_env"])
        if secret is not None:
            payload["secret_value"] = secret
        else:
            warning = (f"{parsed['secret_env']} not set — kept existing dashboard secret "
                       f"for '{name}'")
    return payload, warning
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_cli/test_profiles_sync.py -v`
Expected: PASS (8 passed)

- [ ] **Step 5: Commit**

```bash
git add cli/profiles_sync.py tests/test_cli/test_profiles_sync.py
git commit -m "feat(cli): profile YAML<->payload parsing with env-ref + no-clobber secret"
```

---

### Task B3: Add `put`/`delete` to the API client

**Files:**
- Modify: `cli/api_client.py`

- [ ] **Step 1: Add the methods**

Append to the `CometClient` class (after `get_text`, line 22):

```python
    def put(self, path: str, json: dict = None, **kwargs) -> dict:
        resp = requests.put(f"{self._base}{path}", json=json, headers=self._headers, timeout=15, **kwargs)
        resp.raise_for_status()
        return resp.json()

    def delete(self, path: str, **kwargs) -> None:
        resp = requests.delete(f"{self._base}{path}", headers=self._headers, timeout=15, **kwargs)
        resp.raise_for_status()
```

- [ ] **Step 2: Verify import**

Run: `python -c "from cli.api_client import CometClient"`
Expected: exit 0.

- [ ] **Step 3: Commit**

```bash
git add cli/api_client.py
git commit -m "feat(cli): CometClient.put/.delete for profile sync"
```

---

### Task B4: Rewrite `comet push` as a reconciling mirror

**Files:**
- Modify: `cli/commands/push.py` (profiles section, lines 67-102; keep tests-push section 44-65)
- Test: `tests/test_cli/test_push_pull_profiles.py`

- [ ] **Step 1: Write the failing test (push reconcile)**

```python
# tests/test_cli/test_push_pull_profiles.py
import yaml
from cli.commands.push import _reconcile_profiles


class FakeClient:
    """Records calls; serves a mutable list of remote profiles."""
    def __init__(self, remote):
        self.remote = remote                  # list[dict] with id,name
        self.posts, self.puts, self.deletes = [], [], []

    def get(self, path):
        assert path == "/api/v1/profiles"
        return self.remote

    def post(self, path, json):
        self.posts.append(json)
        return {"id": 999, **json}

    def put(self, path, json):
        self.puts.append((path, json))
        return {"id": int(path.rsplit("/", 1)[1]), **json}

    def delete(self, path):
        self.deletes.append(path)


def test_push_creates_updates_deletes(monkeypatch):
    monkeypatch.setenv("COMET_STAGING_PASSWORD", "pw")
    local = {
        "dev": {"type": "sqlite", "path": "/app/data/x.db"},
        "staging": {"type": "postgres", "host": "h", "username": "u",
                    "password": "${COMET_STAGING_PASSWORD}"},
    }
    remote = [
        {"id": 1, "name": "staging", "db_type": "postgresql", "host": "old"},
        {"id": 2, "name": "obsolete", "db_type": "postgresql"},
    ]
    c = FakeClient(remote)
    summary = _reconcile_profiles(c, local, confirm=lambda *_a, **_k: True)
    names_posted = {p["name"] for p in c.posts}
    names_put = {j["name"] if "name" in j else None for _p, j in c.puts}
    # dev is new -> POST (upsert); staging exists -> POST upsert too (we upsert by name)
    assert "dev" in names_posted
    assert c.deletes == ["/api/v1/profiles/2"]      # obsolete removed
    assert summary["deleted"] == 1


def test_push_unset_env_warns_and_omits_secret(monkeypatch, capsys):
    monkeypatch.delenv("COMET_STAGING_PASSWORD", raising=False)
    local = {"staging": {"type": "postgres", "host": "h", "username": "u",
                         "password": "${COMET_STAGING_PASSWORD}"}}
    c = FakeClient([])
    _reconcile_profiles(c, local, confirm=lambda *_a, **_k: True)
    assert "secret_value" not in c.posts[0]
    assert "not set" in capsys.readouterr().out
```

> Note: this plan upserts every local profile via `POST` (the endpoint is idempotent — Task A4). `PUT` exists for the frontend's structure-only edits; `push` does not need it, so the test asserts deletes + posts. Keep `_reconcile_profiles` returning a summary dict `{created/updated/deleted/unchanged/errors}` — for the POST-upsert path, count name-not-in-remote as created and name-in-remote as updated.

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_cli/test_push_pull_profiles.py -v`
Expected: FAIL — `_reconcile_profiles` does not exist.

- [ ] **Step 3: Implement — replace the profiles section of push.py**

Replace `cli/commands/push.py` lines 67-102 (everything from `# --- Push connection profiles` to end of file) with:

```python
    # --- Push connection profiles (reconciling mirror) ---
    conn_path = Path("comet") / "database_connection.yaml"
    if not conn_path.exists():
        return

    try:
        raw = yaml.safe_load(conn_path.read_text(encoding="utf-8")) or {}
    except Exception as e:
        typer.echo(f"[comet] Could not parse database_connection.yaml: {e}")
        return

    local = {k: v for k, v in raw.items() if isinstance(v, dict)}
    if not local:
        return

    def _confirm(prompt: str) -> bool:
        if yes:
            return True
        return typer.confirm(prompt)

    if dry_run:
        typer.echo("[comet] --dry-run: showing intended changes only")
    summary = _reconcile_profiles(client, local, confirm=_confirm, dry_run=dry_run)
    typer.echo(
        f"[comet] Profiles pushed. created={summary['created']} updated={summary['updated']} "
        f"deleted={summary['deleted']} errors={summary['errors']}"
    )
```

Then add these two helpers and the imports at the top of `cli/commands/push.py`. Change the function signature of `push_cmd` to accept the flags. Full top-of-file + helpers:

```python
from pathlib import Path
import requests
import yaml
import typer
from cli.config import load_config
from cli.api_client import CometClient
from cli.profiles_sync import parse_yaml_profile, profile_to_payload


def _reconcile_profiles(client, local: dict, confirm, dry_run: bool = False) -> dict:
    """Mirror local YAML profiles to the dashboard. Upsert each local profile (POST is
    idempotent by name); delete remote profiles absent from local after confirmation."""
    remote = client.get("/api/v1/profiles")
    remote_by_name = {p["name"]: p for p in remote}
    summary = {"created": 0, "updated": 0, "deleted": 0, "unchanged": 0, "errors": 0}

    for name, profile in local.items():
        parsed = parse_yaml_profile(name, profile)
        payload, warning = profile_to_payload(name, parsed)
        if warning:
            typer.echo(f"[comet] ⚠ {warning}")
        existed = name in remote_by_name
        if dry_run:
            typer.echo(f"[comet]   {'update' if existed else 'create'} {name}")
            summary["updated" if existed else "created"] += 1
            continue
        try:
            client.post("/api/v1/profiles", json=payload)
            summary["updated" if existed else "created"] += 1
        except Exception as e:
            typer.echo(f"[comet] Profile '{name}': push failed — {e}")
            summary["errors"] += 1

    stale = [p for n, p in remote_by_name.items() if n not in local]
    if stale:
        names = ", ".join(p["name"] for p in stale)
        if confirm(f"Delete {len(stale)} dashboard profile(s) not in local YAML ({names})?"):
            for p in stale:
                if dry_run:
                    typer.echo(f"[comet]   delete {p['name']}")
                    summary["deleted"] += 1
                    continue
                try:
                    client.delete(f"/api/v1/profiles/{p['id']}")
                    summary["deleted"] += 1
                except Exception as e:
                    typer.echo(f"[comet] Profile '{p['name']}': delete failed — {e}")
                    summary["errors"] += 1
    return summary
```

And change the `push_cmd` signature (line 44) from `def push_cmd():` to:

```python
def push_cmd(
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview profile changes without applying them"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip the delete confirmation prompt (for CI)"),
):
```

> Verify how `push_cmd` is registered in `cli/cli.py` (grep: `grep -n "push" cli/cli.py`). Typer picks up the new options automatically when the command is registered as a callback; no change needed there unless it is wrapped manually.

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_cli/test_push_pull_profiles.py -v`
Expected: the two push tests PASS.

- [ ] **Step 5: Commit**

```bash
git add cli/commands/push.py tests/test_cli/test_push_pull_profiles.py
git commit -m "feat(cli): push reconciles profiles (upsert + confirmed delete), resolves env, --dry-run/--yes"
```

---

### Task B5: `comet pull` — write profiles into YAML in place + readiness report

**Files:**
- Modify: `cli/commands/pull.py` (whole file)
- Test: add to `tests/test_cli/test_push_pull_profiles.py`

- [ ] **Step 1: Write the failing test (pull rewrite + readiness)**

Append to `tests/test_cli/test_push_pull_profiles.py`:

```python
from cli.commands.pull import _profiles_to_yaml_dict, _readiness_lines


def test_profiles_to_yaml_dict_uses_env_ref_placeholder():
    remote = [
        {"name": "dev", "db_type": "sqlite", "sqlite_path": "/app/data/x.db", "secret_env": None,
         "host": None, "port": None, "database": None, "username": None},
        {"name": "staging", "db_type": "postgresql", "host": "h", "port": 5432, "database": "db",
         "username": "u", "secret_env": "COMET_STAGING_PASSWORD", "sqlite_path": None},
    ]
    d = _profiles_to_yaml_dict(remote)
    assert d["dev"] == {"type": "sqlite", "path": "/app/data/x.db"}
    assert d["staging"]["password"] == "${COMET_STAGING_PASSWORD}"
    assert d["staging"]["type"] == "postgresql" and d["staging"]["host"] == "h"


def test_readiness_lines_flags_unset(monkeypatch):
    monkeypatch.delenv("COMET_STAGING_PASSWORD", raising=False)
    remote = [{"name": "staging", "db_type": "postgresql", "secret_env": "COMET_STAGING_PASSWORD"},
              {"name": "dev", "db_type": "sqlite", "secret_env": None}]
    lines = _readiness_lines(remote)
    joined = "\n".join(lines)
    assert "COMET_STAGING_PASSWORD" in joined and "NOT SET" in joined
    assert "no secret needed" in joined
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_cli/test_push_pull_profiles.py -v`
Expected: FAIL — `cli.commands.pull` has no `_profiles_to_yaml_dict`.

- [ ] **Step 3: Implement — replace `cli/commands/pull.py`**

```python
import os
from pathlib import Path
import typer
from ruamel.yaml import YAML
from cli.config import load_config
from cli.api_client import CometClient

_yaml = YAML()
_yaml.preserve_quotes = True


def _profiles_to_yaml_dict(remote: list[dict]) -> dict:
    """Build {profile_name: {fields...}} from API rows. Secrets become ${secret_env} refs."""
    out = {}
    for p in remote:
        if (p.get("db_type") or "").lower() == "sqlite":
            out[p["name"]] = {"type": "sqlite", "path": p.get("sqlite_path")}
            continue
        entry = {"type": p["db_type"]}
        for f in ("host", "port", "database", "username"):
            if p.get(f) is not None:
                entry[f] = p[f]
        if p.get("secret_env"):
            entry["password"] = "${" + p["secret_env"] + "}"
        out[p["name"]] = entry
    return out


def _readiness_lines(remote: list[dict]) -> list[str]:
    lines = []
    for p in remote:
        env = p.get("secret_env")
        if not env:
            lines.append(f"  {p['name']:<12} {p.get('db_type',''):<10} ✓ no secret needed")
        else:
            state = "SET" if os.environ.get(env) else "NOT SET"
            lines.append(f"  {p['name']:<12} {p.get('db_type',''):<10} needs ${env}   [{state}]")
    return lines


def _merge_profiles_into_file(path: Path, desired: dict) -> None:
    """Update profile mappings in place, preserving comments. Adds new, removes absent."""
    if path.exists():
        doc = _yaml.load(path.read_text(encoding="utf-8")) or {}
    else:
        doc = {}
    # remove profiles no longer present (top-level mapping keys that look like profiles)
    for key in list(doc.keys()):
        if isinstance(doc.get(key), dict) and "type" in doc[key] and key not in desired:
            del doc[key]
    # upsert desired
    for name, fields in desired.items():
        if name in doc and isinstance(doc[name], dict):
            doc[name].clear()
            doc[name].update(fields)
        else:
            doc[name] = fields
    with path.open("w", encoding="utf-8") as f:
        _yaml.dump(doc, f)


def pull_cmd(
    yes: bool = typer.Option(False, "--yes", "-y", help="Write without the confirmation prompt"),
):
    """Download test definitions AND connection profiles from the dashboard to local YAML."""
    cfg = load_config()
    client = CometClient(api_url=cfg["api_url"], api_key=cfg["api_key"])

    # --- Pull test definitions (unchanged behavior) ---
    try:
        yaml_content = client.get_text("/api/v1/tests/yaml")
    except Exception as e:
        typer.echo(f"[comet] Pull failed: {e}")
        raise typer.Exit(1)
    tests_path = Path("comet") / "test_definitions.yaml"
    tests_path.write_text(yaml_content, encoding="utf-8")
    typer.echo(f"[comet] Pulled latest test definitions to {tests_path}")

    # --- Pull connection profiles ---
    try:
        remote = client.get("/api/v1/profiles")
    except Exception as e:
        typer.echo(f"[comet] Could not pull profiles: {e}")
        return

    desired = _profiles_to_yaml_dict(remote)
    conn_path = Path("comet") / "database_connection.yaml"
    if not yes:
        typer.echo(f"[comet] About to update {len(desired)} profile(s) in {conn_path} (comments preserved).")
        if not typer.confirm("Proceed?"):
            typer.echo("[comet] Skipped profile write.")
            return
    _merge_profiles_into_file(conn_path, desired)
    typer.echo(f"[comet] Pulled {len(desired)} connection profile(s) to {conn_path}")
    typer.echo("[comet] Local readiness (set these env vars before running):")
    for line in _readiness_lines(remote):
        typer.echo(line)
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_cli/test_push_pull_profiles.py -v`
Expected: all push + pull tests PASS.

- [ ] **Step 5: Round-trip check (manual, against a running API)**

Run `make start` (+ `make seed`), then:
```bash
comet pull --yes
comet push --yes
comet pull --yes
git diff -- comet/database_connection.yaml
```
Expected: the second pull leaves `comet/database_connection.yaml` unchanged (no diff) and comments are preserved.

- [ ] **Step 6: Commit**

```bash
git add cli/commands/pull.py tests/test_cli/test_push_pull_profiles.py
git commit -m "feat(cli): pull writes profiles into YAML in place (ruamel) + readiness report"
```

**✅ Part B done — `push`/`pull` round-trip profiles two ways; secrets stay in env vars; comments survive.**

---

# PART C — Frontend

> Read `node_modules/next/dist/docs/` per `frontend/AGENTS.md` before editing. Verify in the browser via `make start` — no JS unit harness exists.

### Task C1: Structured `ProfileOut` type

**Files:**
- Modify: `frontend/src/lib/types.ts:68-73`

- [ ] **Step 1: Replace the ProfileOut interface**

```typescript
export interface ProfileOut {
  id: number;
  name: string;
  db_type: string;
  host: string | null;
  port: number | null;
  database: string | null;
  username: string | null;
  sqlite_path: string | null;
  secret_env: string | null;
  created_at: string;
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend; npx tsc --noEmit`
Expected: no new errors from this file (existing usages read `name`, `id`, `db_type` — all still present).

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/types.ts
git commit -m "feat(ui): structured ProfileOut type with secret_env"
```

---

### Task C2: `createProfile`/`updateProfile` payloads

**Files:**
- Modify: `frontend/src/lib/api.ts:72-81`

- [ ] **Step 1: Replace the create wrapper and add update**

```typescript
export interface ProfileInput {
  name: string;
  db_type: string;
  host?: string | null;
  port?: number | null;
  database?: string | null;
  username?: string | null;
  sqlite_path?: string | null;
  secret_env?: string | null;
  secret_value?: string | null;
}

export async function createProfile(body: ProfileInput, token: string): Promise<ProfileOut> {
  return apiPost("/api/v1/profiles", body, token) as Promise<ProfileOut>;
}

export async function updateProfile(
  id: number,
  body: Partial<ProfileInput>,
  token: string,
): Promise<ProfileOut> {
  return apiPut(`/api/v1/profiles/${id}`, body, token) as Promise<ProfileOut>;
}

export async function deleteProfile(id: number, token: string): Promise<void> {
  await apiDelete(`/api/v1/profiles/${id}`, token);
}
```

- [ ] **Step 2: Type-check**

Run: `cd frontend; npx tsc --noEmit`
Expected: errors only where `settings/page.tsx` still passes the old `{ connection_url }` shape — fixed in Task C3.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/api.ts
git commit -m "feat(ui): structured createProfile + updateProfile wrappers"
```

---

### Task C3: Settings form — structured fields, env-var name, after-create instructions

**Files:**
- Modify: `frontend/src/app/dashboard/settings/page.tsx`

- [ ] **Step 1: Replace the form state + handlers (lines 10-55)**

```typescript
const DB_TYPES = ["postgresql", "mysql", "sqlite", "mssql"] as const;

const EMPTY_FORM = {
  name: "", db_type: "postgresql",
  host: "", port: "", database: "", username: "",
  sqlite_path: "", secret_env: "", secret_value: "",
};

function defaultSecretEnv(name: string): string {
  const safe = name.replace(/[^A-Za-z0-9]/g, "_").toUpperCase();
  return safe ? `COMET_${safe}_PASSWORD` : "";
}
```

Inside the component, replace the state block + `handleAdd` (lines 21-42) with:

```typescript
  const [showAddForm, setShowAddForm] = useState(false);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [secretEnvTouched, setSecretEnvTouched] = useState(false);
  const [adding, setAdding] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [createdInfo, setCreatedInfo] = useState<{ name: string; env: string } | null>(null);

  const isSqlite = form.db_type === "sqlite";
  const effectiveSecretEnv = secretEnvTouched ? form.secret_env : defaultSecretEnv(form.name);

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault();
    if (!token) return;
    setAdding(true);
    setFormError(null);
    try {
      const payload = {
        name: form.name,
        db_type: form.db_type,
        host: isSqlite ? null : form.host || null,
        port: isSqlite || !form.port ? null : Number(form.port),
        database: isSqlite ? null : form.database || null,
        username: isSqlite ? null : form.username || null,
        sqlite_path: isSqlite ? form.sqlite_path || null : null,
        secret_env: isSqlite ? null : effectiveSecretEnv,
        secret_value: isSqlite || !form.secret_value ? null : form.secret_value,
      };
      await createProfile(payload, token);
      if (!isSqlite) setCreatedInfo({ name: form.name, env: effectiveSecretEnv });
      setForm({ ...EMPTY_FORM });
      setSecretEnvTouched(false);
      setShowAddForm(false);
      refreshProfiles();
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : "Failed to add profile — check the fields and try again.");
    } finally {
      setAdding(false);
    }
  }
```

(Keep `handleDelete` as-is. Update the import on line 7 to `import { createProfile, deleteProfile } from "@/lib/api";` — unchanged, but ensure `ProfileInput` is not needed here.)

- [ ] **Step 2: Replace the Connection Profiles `<form>` body (lines 251-361)**

Replace the entire `<form onSubmit={handleAdd} ...>...</form>` with structured inputs. Use the same input styling already in the file (extract a shared `inputStyle` object at the top of the return to stay DRY):

```tsx
          <form onSubmit={handleAdd} className="space-y-3 mt-2">
            {(() => {
              const inputStyle: React.CSSProperties = {
                width: "100%", padding: "7px 10px", borderRadius: "6px",
                border: `1px solid ${palette.borderSubtle}`, backgroundColor: palette.surfaceBg,
                color: palette.textPrimary, fontFamily: "var(--font-jetbrains-mono)",
                fontSize: "13px", outline: "none",
              };
              const labelStyle: React.CSSProperties = { color: palette.textSecondary, textTransform: "none", letterSpacing: 0 };
              return (
                <>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-caption block mb-1" style={labelStyle}>Profile name</label>
                      <input required value={form.name}
                        onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                        placeholder="e.g. production" style={inputStyle} />
                    </div>
                    <div>
                      <label className="text-caption block mb-1" style={labelStyle}>Database type</label>
                      <select value={form.db_type}
                        onChange={(e) => setForm((f) => ({ ...f, db_type: e.target.value }))}
                        style={{ ...inputStyle, fontFamily: "inherit" }}>
                        {DB_TYPES.map((t) => (<option key={t} value={t}>{t}</option>))}
                      </select>
                    </div>
                  </div>

                  {isSqlite ? (
                    <div>
                      <label className="text-caption block mb-1" style={labelStyle}>SQLite path</label>
                      <input required value={form.sqlite_path}
                        onChange={(e) => setForm((f) => ({ ...f, sqlite_path: e.target.value }))}
                        placeholder="/app/data/sample.db" style={inputStyle} />
                    </div>
                  ) : (
                    <>
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <label className="text-caption block mb-1" style={labelStyle}>Host</label>
                          <input value={form.host}
                            onChange={(e) => setForm((f) => ({ ...f, host: e.target.value }))}
                            placeholder="db.example.com" style={inputStyle} />
                        </div>
                        <div>
                          <label className="text-caption block mb-1" style={labelStyle}>Port</label>
                          <input value={form.port} inputMode="numeric"
                            onChange={(e) => setForm((f) => ({ ...f, port: e.target.value }))}
                            placeholder="5432" style={inputStyle} />
                        </div>
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <label className="text-caption block mb-1" style={labelStyle}>Database</label>
                          <input value={form.database}
                            onChange={(e) => setForm((f) => ({ ...f, database: e.target.value }))}
                            placeholder="analytics" style={inputStyle} />
                        </div>
                        <div>
                          <label className="text-caption block mb-1" style={labelStyle}>Username</label>
                          <input value={form.username}
                            onChange={(e) => setForm((f) => ({ ...f, username: e.target.value }))}
                            placeholder="reader" style={inputStyle} />
                        </div>
                      </div>
                      <div>
                        <label className="text-caption block mb-1" style={labelStyle}>Password</label>
                        <input type="password" value={form.secret_value}
                          onChange={(e) => setForm((f) => ({ ...f, secret_value: e.target.value }))}
                          placeholder="stored encrypted; used for dashboard runs" style={inputStyle} />
                      </div>
                      <div>
                        <label className="text-caption block mb-1" style={labelStyle}>Environment variable name</label>
                        <input value={effectiveSecretEnv}
                          onChange={(e) => { setSecretEnvTouched(true); setForm((f) => ({ ...f, secret_env: e.target.value })); }}
                          style={inputStyle} />
                        <p className="text-caption mt-1" style={{ ...labelStyle }}>
                          Local CLI runs read this profile&apos;s secret from this environment variable.
                        </p>
                      </div>
                    </>
                  )}

                  {formError && (
                    <p className="text-caption" style={{ color: STATUS_PALETTE.FAILED, textTransform: "none", letterSpacing: 0 }}>
                      {formError}
                    </p>
                  )}
                  <div className="flex gap-2">
                    <button type="submit" disabled={adding}
                      style={{ padding: "6px 16px", borderRadius: "6px", backgroundColor: BRAND_TEAL,
                        color: "#fff", border: "none", cursor: adding ? "not-allowed" : "pointer",
                        opacity: adding ? 0.6 : 1, fontSize: "13px", fontWeight: 500 }}>
                      {adding ? "Saving…" : "Save Changes"}
                    </button>
                    <button type="button"
                      onClick={() => { setShowAddForm(false); setForm({ ...EMPTY_FORM }); setSecretEnvTouched(false); setFormError(null); }}
                      style={{ padding: "6px 16px", borderRadius: "6px", backgroundColor: "transparent",
                        color: palette.textSecondary, border: `1px solid ${palette.borderSubtle}`,
                        cursor: "pointer", fontSize: "13px" }}>
                      Cancel
                    </button>
                  </div>
                </>
              );
            })()}
          </form>
```

- [ ] **Step 3: Add the after-create instructions panel**

Immediately before the `{!showAddForm ? (` block (around line 234), insert:

```tsx
        {createdInfo && (
          <div className="mb-4 p-4" style={{
            borderRadius: "6px", backgroundColor: `${BRAND_TEAL}0F`,
            border: `1px solid ${BRAND_TEAL}4D`,
          }}>
            <p className="text-body" style={{ color: palette.textPrimary, fontWeight: 500 }}>
              ✓ <span style={{ fontFamily: "var(--font-jetbrains-mono)" }}>{createdInfo.name}</span> is ready for dashboard runs.
            </p>
            <p className="text-caption mt-2" style={{ color: palette.textSecondary, textTransform: "none", letterSpacing: 0 }}>
              To use it from your local machine: run <code>comet pull</code>, then set{" "}
              <button type="button"
                onClick={() => navigator.clipboard?.writeText(createdInfo.env)}
                style={{ fontFamily: "var(--font-jetbrains-mono)", color: BRAND_TEAL, background: "none",
                  border: "none", cursor: "pointer", padding: 0 }}>
                {createdInfo.env}
              </button>{" "}in your shell (click to copy).
            </p>
            <button type="button" onClick={() => setCreatedInfo(null)} className="text-caption mt-2"
              style={{ color: palette.textSecondary, background: "none", border: "none", cursor: "pointer", textTransform: "none", letterSpacing: 0 }}>
              Dismiss
            </button>
          </div>
        )}
```

- [ ] **Step 4: Show `secret_env` in the profile list**

In the profile list row (after the `{p.db_type}` badge, ~line 210), add:

```tsx
                  {p.secret_env && (
                    <span className="text-[10px]" style={{ fontFamily: "var(--font-jetbrains-mono)", color: palette.textSecondary }}>
                      ${p.secret_env}
                    </span>
                  )}
```

- [ ] **Step 5: Verify in the browser**

Run: `make start` (and `make seed` if no profiles).
Check, in Settings → Connection Profiles:
1. "Add connection" shows structured fields; selecting `sqlite` swaps to a single Path field.
2. Typing a name auto-fills "Environment variable name" as `COMET_<NAME>_PASSWORD`; editing it stops the auto-fill.
3. Saving a non-sqlite profile shows the teal "ready for dashboard runs / set `COMET_..._PASSWORD`" panel; the var name copies on click.
4. The list shows each profile's `db_type` and `$SECRET_ENV`.
Expected: all four behave as described; no console errors.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/dashboard/settings/page.tsx
git commit -m "feat(ui): structured connection form + env-var name + post-create instructions"
```

**✅ Part C done — the browser captures structured profiles, makes the env-var requirement explicit, and shows it in the list.**

---

## Self-Review (completed by plan author)

- **Spec coverage:** D1/D2 (two-way, command-wins) → B4/B5 + confirms; D3 (env-only secrets) → B2 `profile_to_payload`; D4 (env-name round-trips) → A1 `secret_env`, A4 default, B5 `_profiles_to_yaml_dict`; D5 (encrypted value, never returned) → A1/A3/A4 + test `test_create_returns_structure_never_secret`; D6 (ruamel in-place) → B5 `_merge_profiles_into_file` + round-trip check; D7 (Phase 8 of v1.2) → header. Push bug fixes (env resolution, update/delete) → B2/B4. UI clarity → C3. Migration → human gate section.
- **Placeholder scan:** no TBD/“handle edge cases”/uncited symbols. Fixtures `api_client_factory`/`db_session_for` flagged with a fallback instruction.
- **Type consistency:** `secret_env`, `secret_value`, `sqlite_path`, `db_type` used identically across models, schemas, payloads, TS types, and CLI. `build_connection_url` signature matches its sole caller in A5.

## Open items deferred to execution (from spec)
- Whether the engine's `backend/config/database_connection.yaml` and the CLI's `comet/database_connection.yaml` converge — out of scope for this plan; pull/push operate on `comet/database_connection.yaml`.
- Exact live-Railway migration timing — gated on user confirmation (human gate above).
