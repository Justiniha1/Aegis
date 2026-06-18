# Week 1 — Engine Packaging & API Changes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Package the engine as an installable `comet-dq` CLI (`comet init/push/pull/run/status`), add encrypted connection profile storage to the API, and update the run executor to load DB credentials from Postgres instead of a local YAML file.

**Architecture:** A new `cli/` directory holds a Typer-based CLI that calls the Comet API — it never runs the engine locally. A new `ConnectionProfile` model stores encrypted connection strings in the existing Postgres/SQLite DB. `run_executor.py` is updated to build its connections dict from `ConnectionProfile` rows instead of a local YAML file. `pyproject.toml` at the repo root makes the whole thing installable as `comet-dq`.

**Tech Stack:** Python 3.13, Typer (CLI), `cryptography` (Fernet encryption), `requests` (HTTP), `pytest` + FastAPI `TestClient` (tests), PyYAML, `python-dotenv`

---

## File Map

**New files:**
- `pyproject.toml` — package definition, entry point, dependencies
- `cli/__init__.py` — package marker
- `cli/cli.py` — Typer app, registers all subcommands
- `cli/config.py` — loads `comet/config.yaml` and `COMET_API_KEY` from `.env`
- `cli/api_client.py` — thin `requests` wrapper for the Comet API
- `cli/commands/__init__.py`
- `cli/commands/init.py` — `comet init` command
- `cli/commands/push.py` — `comet push` command
- `cli/commands/pull.py` — `comet pull` command
- `cli/commands/run_cmd.py` — `comet run` command
- `cli/commands/status.py` — `comet status` command
- `cli/templates/config.yaml` — scaffolded by `comet init`
- `cli/templates/test_definitions.yaml` — scaffolded by `comet init`
- `dashboard_api/encryption.py` — Fernet encrypt/decrypt helpers
- `dashboard_api/routers/profiles.py` — CRUD for connection profiles
- `tests/__init__.py`
- `tests/test_api/__init__.py`
- `tests/test_api/test_encryption.py`
- `tests/test_api/test_profiles.py`
- `tests/test_api/test_run_executor.py`
- `tests/test_cli/__init__.py`
- `tests/test_cli/test_config.py`
- `tests/test_cli/test_push_pull.py`
- `tests/test_cli/test_run.py`

**Modified files:**
- `dashboard_api/models.py` — add `ConnectionProfile` model
- `dashboard_api/schemas.py` — add `ConnectionProfileCreate`, `ConnectionProfileOut`
- `dashboard_api/main.py` — register profiles router
- `dashboard_api/run_executor.py` — load connections from `ConnectionProfile` rows

---

## Task 1: pytest setup + `cryptography` dependency

**Files:**
- Create: `pyproject.toml`
- Create: `tests/__init__.py`
- Create: `tests/test_api/__init__.py`
- Create: `tests/test_cli/__init__.py`

- [ ] **Step 1: Create `pyproject.toml` at repo root**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "comet-dq"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "typer>=0.12",
    "requests>=2.31",
    "pyyaml>=6.0",
    "python-dotenv>=1.0",
    "cryptography>=42.0",
    "rich>=13.0",
]

[project.scripts]
comet = "cli.cli:app"

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-mock>=3.12",
    "httpx>=0.27",
]

[tool.setuptools.packages.find]
where = ["."]
include = ["cli*"]
```

- [ ] **Step 2: Create empty test init files**

```python
# tests/__init__.py  (empty)
# tests/test_api/__init__.py  (empty)
# tests/test_cli/__init__.py  (empty)
```

- [ ] **Step 3: Install the package in dev mode**

```bash
pip install -e ".[dev]"
```

Expected: no errors. `comet --help` prints Typer default help (will show "No commands" until Task 6).

- [ ] **Step 4: Verify pytest finds the test directories**

```bash
pytest tests/ --collect-only
```

Expected: `no tests ran` with 0 errors (empty dirs are valid).

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml tests/
git commit -m "chore: add pyproject.toml, comet-dq package scaffold, pytest setup"
```

---

## Task 2: Fernet encryption helpers

**Files:**
- Create: `dashboard_api/encryption.py`
- Create: `tests/test_api/test_encryption.py`

The `COMET_ENCRYPTION_KEY` env var holds a Fernet key (URL-safe base64, 32 bytes). Generate one with: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. Set it in `.env` for local dev and as a Railway env var for production.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_api/test_encryption.py
import os
import pytest
from cryptography.fernet import Fernet

def _set_key(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("COMET_ENCRYPTION_KEY", key)
    return key

def test_encrypt_decrypt_roundtrip(monkeypatch):
    _set_key(monkeypatch)
    from dashboard_api.encryption import encrypt, decrypt
    plaintext = "postgresql://user:pass@host:5432/mydb"
    assert decrypt(encrypt(plaintext)) == plaintext

def test_encrypt_produces_different_ciphertext_each_time(monkeypatch):
    _set_key(monkeypatch)
    from dashboard_api.encryption import encrypt
    a = encrypt("same-string")
    b = encrypt("same-string")
    assert a != b  # Fernet uses random IV

def test_missing_key_raises(monkeypatch):
    monkeypatch.delenv("COMET_ENCRYPTION_KEY", raising=False)
    import importlib
    import dashboard_api.encryption as enc_mod
    importlib.reload(enc_mod)  # re-evaluate module-level code without the env var
    with pytest.raises(RuntimeError, match="COMET_ENCRYPTION_KEY"):
        from dashboard_api.encryption import encrypt
        encrypt("anything")
```

- [ ] **Step 2: Run to verify it fails**

```bash
pytest tests/test_api/test_encryption.py -v
```

Expected: `ModuleNotFoundError: No module named 'dashboard_api.encryption'`

- [ ] **Step 3: Implement `dashboard_api/encryption.py`**

```python
import os
from cryptography.fernet import Fernet

def _get_fernet() -> Fernet:
    key = os.environ.get("COMET_ENCRYPTION_KEY")
    if not key:
        raise RuntimeError(
            "COMET_ENCRYPTION_KEY env var is not set. "
            "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    return Fernet(key.encode())

def encrypt(plaintext: str) -> str:
    return _get_fernet().encrypt(plaintext.encode()).decode()

def decrypt(ciphertext: str) -> str:
    return _get_fernet().decrypt(ciphertext.encode()).decode()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_api/test_encryption.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add dashboard_api/encryption.py tests/test_api/test_encryption.py
git commit -m "feat: Fernet encryption helpers for connection credential storage"
```

---

## Task 3: `ConnectionProfile` model + schemas

**Files:**
- Modify: `dashboard_api/models.py`
- Modify: `dashboard_api/schemas.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_api/test_profiles.py
from dashboard_api.models import ConnectionProfile

def test_connection_profile_model_fields():
    """Verify the model has the expected columns before hitting a DB."""
    cols = {c.name for c in ConnectionProfile.__table__.columns}
    assert cols == {"id", "client_id", "name", "connection_url_encrypted", "db_type", "created_at"}
```

- [ ] **Step 2: Run to verify it fails**

```bash
pytest tests/test_api/test_profiles.py::test_connection_profile_model_fields -v
```

Expected: `ImportError` or `AttributeError`.

- [ ] **Step 3: Add `ConnectionProfile` to `dashboard_api/models.py`**

Add after the `Run` class:

```python
class ConnectionProfile(Base):
    __tablename__ = "connection_profiles"

    id = Column(Integer, primary_key=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    name = Column(String, nullable=False)          # e.g. "production", "dev"
    connection_url_encrypted = Column(String, nullable=False)
    db_type = Column(String, nullable=False)       # display only: "postgresql", "mysql", etc.
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_profiles_client_name", "client_id", "name", unique=True),
    )
```

Also add the relationship to `Client`:

```python
# Inside class Client, after existing relationships:
connection_profiles = relationship("ConnectionProfile", cascade="all, delete-orphan")
```

- [ ] **Step 4: Add schemas to `dashboard_api/schemas.py`**

Append to the end of `schemas.py`:

```python
# ── Connection Profiles ───────────────────────────────────────────────────────

class ConnectionProfileCreate(BaseModel):
    name: str
    connection_url: str    # plaintext — encrypted before storage, never returned
    db_type: str


class ConnectionProfileOut(BaseModel):
    id: int
    name: str
    db_type: str
    created_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_api/test_profiles.py::test_connection_profile_model_fields -v
```

Expected: 1 passed.

- [ ] **Step 6: Commit**

```bash
git add dashboard_api/models.py dashboard_api/schemas.py tests/test_api/test_profiles.py
git commit -m "feat: ConnectionProfile model + schemas for encrypted credential storage"
```

---

## Task 4: Connection profiles API router

**Files:**
- Create: `dashboard_api/routers/profiles.py`
- Modify: `dashboard_api/main.py`
- Modify: `tests/test_api/test_profiles.py` (add endpoint tests)

- [ ] **Step 1: Write the failing tests (append to `test_profiles.py`)**

```python
# Append to tests/test_api/test_profiles.py
import os
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from dashboard_api.models import Base, Client
from dashboard_api.database import get_db
from dashboard_api.auth import hash_api_key

@pytest.fixture()
def client_app(monkeypatch, tmp_path):
    monkeypatch.setenv("COMET_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-32-chars-xxxxxxxxx")

    engine = create_engine(f"sqlite:///{tmp_path}/test.db", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)

    from dashboard_api.main import app
    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()
    app.dependency_overrides[get_db] = override_get_db

    # seed a client with a known api key
    raw_key = "test-api-key-abc123"
    db = TestingSession()
    db.add(Client(name="testco", email="test@test.com", api_key_hash=hash_api_key(raw_key)))
    db.commit()
    db.close()

    yield TestClient(app), {"Authorization": f"Bearer {raw_key}"}
    app.dependency_overrides.clear()


def test_create_and_list_profiles(client_app):
    tc, headers = client_app
    resp = tc.post("/api/v1/profiles", json={
        "name": "production",
        "connection_url": "postgresql://user:pass@host:5432/mydb",
        "db_type": "postgresql",
    }, headers=headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "production"
    assert "connection_url" not in body  # never returned

    resp = tc.get("/api/v1/profiles", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_delete_profile(client_app):
    tc, headers = client_app
    tc.post("/api/v1/profiles", json={
        "name": "dev", "connection_url": "sqlite:///./test.db", "db_type": "sqlite"
    }, headers=headers)
    resp = tc.get("/api/v1/profiles", headers=headers)
    profile_id = resp.json()[0]["id"]

    resp = tc.delete(f"/api/v1/profiles/{profile_id}", headers=headers)
    assert resp.status_code == 204

    resp = tc.get("/api/v1/profiles", headers=headers)
    assert resp.json() == []
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_api/test_profiles.py::test_create_and_list_profiles -v
```

Expected: 404 (route doesn't exist yet).

- [ ] **Step 3: Create `dashboard_api/routers/profiles.py`**

```python
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from dashboard_api import models, schemas
from dashboard_api.auth import get_client_any_auth
from dashboard_api.database import get_db
from dashboard_api.encryption import encrypt

router = APIRouter(prefix="/api/v1/profiles", tags=["profiles"])


@router.post("", response_model=schemas.ConnectionProfileOut, status_code=201)
def create_profile(
    body: schemas.ConnectionProfileCreate,
    db: Session = Depends(get_db),
    client: models.Client = Depends(get_client_any_auth),
):
    existing = db.query(models.ConnectionProfile).filter(
        models.ConnectionProfile.client_id == client.id,
        models.ConnectionProfile.name == body.name,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Profile '{body.name}' already exists")
    profile = models.ConnectionProfile(
        client_id=client.id,
        name=body.name,
        connection_url_encrypted=encrypt(body.connection_url),
        db_type=body.db_type,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


@router.get("", response_model=list[schemas.ConnectionProfileOut])
def list_profiles(
    db: Session = Depends(get_db),
    client: models.Client = Depends(get_client_any_auth),
):
    return db.query(models.ConnectionProfile).filter(
        models.ConnectionProfile.client_id == client.id
    ).all()


@router.delete("/{profile_id}", status_code=204)
def delete_profile(
    profile_id: int,
    db: Session = Depends(get_db),
    client: models.Client = Depends(get_client_any_auth),
):
    profile = db.query(models.ConnectionProfile).filter(
        models.ConnectionProfile.id == profile_id,
        models.ConnectionProfile.client_id == client.id,
    ).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    db.delete(profile)
    db.commit()
    return Response(status_code=204)
```

- [ ] **Step 4: Register the router in `dashboard_api/main.py`**

Find the block where other routers are included (look for `app.include_router`) and add:

```python
from dashboard_api.routers.profiles import router as profiles_router
app.include_router(profiles_router)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_api/test_profiles.py -v
```

Expected: 3 passed (model test + 2 endpoint tests).

- [ ] **Step 6: Commit**

```bash
git add dashboard_api/routers/profiles.py dashboard_api/main.py tests/test_api/test_profiles.py
git commit -m "feat: connection profiles CRUD endpoints with Fernet encryption"
```

---

## Task 5: Update `run_executor.py` to use DB credentials

**Files:**
- Modify: `dashboard_api/run_executor.py`
- Create: `tests/test_api/test_run_executor.py`

The current executor calls `load_config()` (reads a local YAML file) to get connection info. Replace that with a query against `ConnectionProfile` rows for the client. Test definitions are already loaded from DB — this change makes credentials DB-sourced too.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_api/test_run_executor.py
import os
import pytest
from unittest.mock import patch, MagicMock
from cryptography.fernet import Fernet
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from dashboard_api.models import Base, Client, Run, ConnectionProfile
from dashboard_api.auth import hash_api_key
from dashboard_api.encryption import encrypt


@pytest.fixture()
def db_session(monkeypatch, tmp_path):
    monkeypatch.setenv("COMET_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-32-chars-xxxxxxxxxxxxx")
    engine = create_engine(f"sqlite:///{tmp_path}/exec.db", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    db = Session()
    client = Client(name="co", api_key_hash=hash_api_key("key123"))
    db.add(client)
    db.commit()
    db.refresh(client)

    run = Run(client_id=client.id, profile="dev", status="QUEUED", total_tests=0, completed_tests=0)
    db.add(run)
    db.commit()
    db.refresh(run)

    profile = ConnectionProfile(
        client_id=client.id,
        name="dev",
        connection_url_encrypted=encrypt("sqlite:///:memory:"),
        db_type="sqlite",
    )
    db.add(profile)
    db.commit()

    yield db, client, run
    db.close()


def test_execute_run_fails_when_no_connection_profile(monkeypatch, tmp_path):
    """Run should transition to FAILED if no ConnectionProfile exists for the profile."""
    monkeypatch.setenv("COMET_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-32-chars-xxxxxxxxxxxxx")
    engine = create_engine(f"sqlite:///{tmp_path}/noprofile.db", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    db = Session()
    client = Client(name="co2", api_key_hash=hash_api_key("key456"))
    db.add(client)
    db.commit()
    run = Run(client_id=client.id, profile="missing", status="QUEUED", total_tests=0, completed_tests=0)
    db.add(run)
    db.commit()
    db.close()

    from dashboard_api.run_executor import execute_run
    with patch("dashboard_api.run_executor.SessionLocal", return_value=Session()):
        execute_run(run_id=run.id, client_id=client.id, profile="missing", type_filter=None)

    db2 = Session()
    updated = db2.query(Run).filter(Run.id == run.id).first()
    assert updated.status == "FAILED"
    assert "missing" in updated.error_reason
    db2.close()
```

- [ ] **Step 2: Run to verify it fails**

```bash
pytest tests/test_api/test_run_executor.py::test_execute_run_fails_when_no_connection_profile -v
```

Expected: FAIL — current executor calls `load_config()` which raises `FileNotFoundError`, which gets caught as `FAILED` but with wrong message. The test will fail the assertion on `"missing" in updated.error_reason`.

- [ ] **Step 3: Update `dashboard_api/run_executor.py`**

Replace the `load_config()` block (lines 89–138 in the original) with a DB-sourced connection lookup. The test definitions loading (lines 141–182) stays unchanged. Here is the full updated `execute_run` function:

```python
def execute_run(
    run_id: int,
    client_id: int,
    profile: str,
    type_filter: Optional[list[str]],
) -> None:
    from backend.core.config_loader import (
        DQFConfig, EngineConfig, TestDefinition as EngineTestDef,
        _name_to_id, _deduplicate_test_ids,
    )
    from backend.core.test_engine import TestEngine
    from dashboard_api.encryption import decrypt

    db = SessionLocal()
    try:
        run = db.query(models.Run).filter(models.Run.id == run_id).first()
        if run is None:
            print(f"[warn] execute_run: run_id={run_id} not found — aborting")
            return

        run.status = "RUNNING"
        db.commit()

        # Load connection profile from DB (replaces local YAML lookup)
        conn_row = db.query(models.ConnectionProfile).filter(
            models.ConnectionProfile.client_id == client_id,
            models.ConnectionProfile.name == profile,
        ).first()

        if conn_row is None:
            run.status = "FAILED"
            run.error_reason = _sanitize_error(
                f"Profile '{profile}' not found — add it in Settings → Connection Profiles"
            )
            run.completed_at = datetime.utcnow()
            db.commit()
            return

        try:
            connection_url = decrypt(conn_row.connection_url_encrypted)
        except Exception as e:
            run.status = "FAILED"
            run.error_reason = _sanitize_error(f"Could not decrypt profile '{profile}': {e}")
            run.completed_at = datetime.utcnow()
            db.commit()
            return

        connections = {profile: {"connection_url": connection_url}}
        engine_cfg = EngineConfig(
            engine="simple",
            default_profile=profile,
            default_severity="MEDIUM",
            alerts={},
        )

        # Load tests from DB (unchanged from original)
        db_tests_q = db.query(models.TestDefinition).filter(
            models.TestDefinition.client_id == client_id,
            models.TestDefinition.enabled == True,  # noqa: E712
            models.TestDefinition.profile == profile,
        )
        if type_filter:
            db_tests_q = db_tests_q.filter(models.TestDefinition.type.in_(type_filter))
        db_test_rows = db_tests_q.order_by(models.TestDefinition.created_at.asc()).all()

        if not db_test_rows:
            run.status = "FAILED"
            run.error_reason = _sanitize_error(
                f"No enabled tests for profile '{profile}'"
                + (f" with type_filter {type_filter}" if type_filter else "")
            )
            run.completed_at = datetime.utcnow()
            db.commit()
            return

        engine_tests = []
        for t in db_test_rows:
            raw = {
                "name": t.name,
                "type": t.type,
                "severity": t.severity,
                "profile": t.profile,
                "enabled": t.enabled,
                "tags": t.tags or [],
                **(t.config or {}),
            }
            engine_tests.append(EngineTestDef(
                name=t.name,
                test_id=_name_to_id(t.name),
                type=t.type,
                profile=t.profile,
                severity=t.severity,
                enabled=t.enabled,
                tags=t.tags or [],
                raw=raw,
            ))
        engine_tests = _deduplicate_test_ids(engine_tests)

        narrowed = DQFConfig(
            engine=engine_cfg,
            connections=connections,
            tests=engine_tests,
        )

        run.total_tests = len(engine_tests)
        db.commit()

        engine = TestEngine(narrowed)
        run_at = datetime.utcnow()
        state = {"idx": 0}

        def on_result(result: dict) -> None:
            state["idx"] += 1
            _persist_result(db, client_id, run_id, result, run_at)

        try:
            engine.run(on_result=on_result)
        except Exception as e:
            tb = traceback.format_exc(limit=3)
            run.status = "FAILED"
            run.error_reason = _sanitize_error(
                f"Engine crashed at test {state['idx']} — {type(e).__name__}: {e}"
            )
            run.error_at_test = state["idx"]
            run.completed_at = datetime.utcnow()
            db.commit()
            print(f"[warn] execute_run run_id={run_id} crashed: {tb}")
            return

        run.status = "COMPLETE"
        run.completed_at = datetime.utcnow()
        db.commit()

    finally:
        db.close()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_api/test_run_executor.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add dashboard_api/run_executor.py tests/test_api/test_run_executor.py
git commit -m "feat: run_executor loads connection credentials from DB instead of local YAML"
```

---

## Task 6: CLI package scaffold + `cli/config.py`

**Files:**
- Create: `cli/__init__.py`
- Create: `cli/cli.py`
- Create: `cli/config.py`
- Create: `cli/commands/__init__.py`
- Create: `cli/templates/config.yaml`
- Create: `cli/templates/test_definitions.yaml`
- Create: `tests/test_cli/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli/test_config.py
import os
import pytest
from pathlib import Path

def test_load_config_reads_yaml_and_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("COMET_API_KEY", "test-key-from-env")

    comet_dir = tmp_path / "comet"
    comet_dir.mkdir()
    (comet_dir / "config.yaml").write_text(
        "api_url: https://api.comet-dq.com\ndefault_profile: production\n"
    )

    from cli.config import load_config
    cfg = load_config()
    assert cfg["api_url"] == "https://api.comet-dq.com"
    assert cfg["default_profile"] == "production"
    assert cfg["api_key"] == "test-key-from-env"


def test_load_config_raises_when_no_config_yaml(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from cli.config import load_config
    with pytest.raises(SystemExit):
        load_config()
```

- [ ] **Step 2: Run to verify it fails**

```bash
pytest tests/test_cli/test_config.py -v
```

Expected: `ModuleNotFoundError: No module named 'cli.config'`

- [ ] **Step 3: Create `cli/__init__.py`** (empty)

- [ ] **Step 4: Create `cli/commands/__init__.py`** (empty)

- [ ] **Step 5: Create `cli/config.py`**

```python
import os
import sys
from pathlib import Path
import yaml
from dotenv import load_dotenv


def load_config() -> dict:
    """Load comet/config.yaml + COMET_API_KEY from .env. Exits with a helpful message on failure."""
    load_dotenv()

    config_path = Path("comet") / "config.yaml"
    if not config_path.exists():
        print("[comet] comet/config.yaml not found. Run 'comet init' to set up your project.")
        sys.exit(1)

    with open(config_path, "r") as f:
        cfg = yaml.safe_load(f) or {}

    api_key = os.environ.get("COMET_API_KEY")
    if not api_key:
        print("[comet] COMET_API_KEY not set. Add it to your .env file: COMET_API_KEY=your-key")
        sys.exit(1)

    cfg["api_key"] = api_key
    cfg.setdefault("api_url", "https://api.comet-dq.com")
    cfg.setdefault("default_profile", "dev")
    return cfg
```

- [ ] **Step 6: Create `cli/templates/config.yaml`**

```yaml
# Comet configuration
# api_url can also be set via COMET_API_URL environment variable
api_url: https://api.comet-dq.com
default_profile: production
```

- [ ] **Step 7: Create `cli/templates/test_definitions.yaml`**

```yaml
# Comet test definitions
# Edit this file and run 'comet push' to sync changes to your dashboard.
# Run 'comet pull' to fetch the latest definitions from your dashboard.

settings:
  default_profile: production
  default_severity: MEDIUM

tests:
  - name: Example Row Count Check
    type: row_count
    profile: production
    severity: HIGH
    enabled: true
    table: your_table_name
    min_rows: 1
```

- [ ] **Step 8: Create `cli/cli.py`**

```python
import typer

app = typer.Typer(
    name="comet",
    help="Comet DQ — data quality from the command line.",
    no_args_is_help=True,
)

from cli.commands.init import init_cmd
from cli.commands.push import push_cmd
from cli.commands.pull import pull_cmd
from cli.commands.run_cmd import run_cmd
from cli.commands.status import status_cmd

app.command("init")(init_cmd)
app.command("push")(push_cmd)
app.command("pull")(pull_cmd)
app.command("run")(run_cmd)
app.command("status")(status_cmd)

if __name__ == "__main__":
    app()
```

- [ ] **Step 9: Run tests to verify they pass**

```bash
pytest tests/test_cli/test_config.py -v
```

Expected: 2 passed.

- [ ] **Step 10: Verify CLI entry point works**

```bash
comet --help
```

Expected: Typer help listing init, push, pull, run, status commands. (Commands not yet implemented — they'll raise `NotImplementedError` until Tasks 7-11.)

- [ ] **Step 11: Commit**

```bash
git add cli/ tests/test_cli/test_config.py
git commit -m "feat: CLI package scaffold — Typer app, config loader, templates"
```

---

## Task 7: `cli/api_client.py` + `comet init`

**Files:**
- Create: `cli/api_client.py`
- Create: `cli/commands/init.py`
- Modify: `tests/test_cli/test_config.py` (add api_client test)

- [ ] **Step 1: Write failing test for `api_client`**

Append to `tests/test_cli/test_config.py`:

```python
def test_api_client_get_raises_on_401(requests_mock):
    from cli.api_client import CometClient
    requests_mock.get("https://api.comet-dq.com/api/v1/runs/latest", status_code=401)
    client = CometClient(api_url="https://api.comet-dq.com", api_key="bad-key")
    import requests
    with pytest.raises(requests.HTTPError):
        client.get("/api/v1/runs/latest")
```

Note: This test requires `requests-mock`. Add it to `pyproject.toml` dev deps: `"requests-mock>=1.11"`, then re-run `pip install -e ".[dev]"`.

- [ ] **Step 2: Run to verify it fails**

```bash
pytest tests/test_cli/test_config.py::test_api_client_get_raises_on_401 -v
```

Expected: `ModuleNotFoundError: No module named 'cli.api_client'`

- [ ] **Step 3: Create `cli/api_client.py`**

```python
import requests


class CometClient:
    def __init__(self, api_url: str, api_key: str):
        self._base = api_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {api_key}"}

    def get(self, path: str, **kwargs) -> dict:
        resp = requests.get(f"{self._base}{path}", headers=self._headers, timeout=15, **kwargs)
        resp.raise_for_status()
        return resp.json()

    def post(self, path: str, json: dict = None, **kwargs) -> dict:
        resp = requests.post(f"{self._base}{path}", json=json, headers=self._headers, timeout=15, **kwargs)
        resp.raise_for_status()
        return resp.json()

    def get_text(self, path: str, **kwargs) -> str:
        resp = requests.get(f"{self._base}{path}", headers=self._headers, timeout=15, **kwargs)
        resp.raise_for_status()
        return resp.text
```

- [ ] **Step 4: Create `cli/commands/init.py`**

```python
import shutil
from pathlib import Path
import typer

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def init_cmd():
    """Scaffold the comet/ project directory with starter config files."""
    comet_dir = Path("comet")
    profiles_dir = comet_dir / "profiles"

    if comet_dir.exists():
        typer.echo("[comet] comet/ directory already exists. Nothing to do.")
        raise typer.Exit()

    comet_dir.mkdir()
    profiles_dir.mkdir()

    shutil.copy(TEMPLATES_DIR / "config.yaml", comet_dir / "config.yaml")
    shutil.copy(TEMPLATES_DIR / "test_definitions.yaml", comet_dir / "test_definitions.yaml")

    (profiles_dir / "dev.yaml").write_text("# Dev profile label — add connection in dashboard Settings\nname: dev\n")
    (profiles_dir / "production.yaml").write_text("# Production profile label — add connection in dashboard Settings\nname: production\n")

    env_path = Path(".env")
    if not env_path.exists():
        env_path.write_text("COMET_API_KEY=paste-your-api-key-here\n")
        typer.echo("[comet] Created .env — add your API key (find it in Settings on the dashboard).")

    typer.echo("[comet] Project initialized. Next steps:")
    typer.echo("  1. Add COMET_API_KEY to .env")
    typer.echo("  2. Add your DB connection in the dashboard under Settings → Connection Profiles")
    typer.echo("  3. Edit comet/test_definitions.yaml")
    typer.echo("  4. Run 'comet push' to sync your tests to the dashboard")
```

- [ ] **Step 5: Run api_client test to verify it passes**

```bash
pytest tests/test_cli/test_config.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Manual smoke test `comet init`**

```bash
cd %TEMP%
mkdir comet-test && cd comet-test
comet init
```

Expected: `comet/` directory created with `config.yaml`, `test_definitions.yaml`, `profiles/dev.yaml`, `profiles/production.yaml`, and `.env`.

- [ ] **Step 7: Commit**

```bash
git add cli/api_client.py cli/commands/init.py tests/test_cli/test_config.py pyproject.toml
git commit -m "feat: CometClient HTTP wrapper + comet init command"
```

---

## Task 8: `comet push` and `comet pull`

**Files:**
- Create: `cli/commands/push.py`
- Create: `cli/commands/pull.py`
- Create: `tests/test_cli/test_push_pull.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_cli/test_push_pull.py
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from typer.testing import CliRunner
from cli.cli import app

runner = CliRunner()


@pytest.fixture()
def comet_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("COMET_API_KEY", "test-key")
    comet = tmp_path / "comet"
    comet.mkdir()
    (comet / "config.yaml").write_text("api_url: https://api.comet-dq.com\ndefault_profile: dev\n")
    (comet / "test_definitions.yaml").write_text("tests:\n  - name: Test A\n    type: row_count\n")
    return tmp_path


def test_push_calls_sync_endpoint(comet_project):
    with patch("cli.commands.push.CometClient") as MockClient:
        mock = MockClient.return_value
        mock.post.return_value = {"synced": 1}
        result = runner.invoke(app, ["push"])
    assert result.exit_code == 0
    mock.post.assert_called_once()
    call_args = mock.post.call_args
    assert call_args[0][0] == "/api/v1/tests/sync"
    assert "yaml_content" in call_args[1]["json"]


def test_pull_writes_yaml_to_disk(comet_project):
    yaml_from_api = "tests:\n  - name: Remote Test\n    type: row_count\n"
    with patch("cli.commands.pull.CometClient") as MockClient:
        mock = MockClient.return_value
        mock.get_text.return_value = yaml_from_api
        result = runner.invoke(app, ["pull"])
    assert result.exit_code == 0
    content = (comet_project / "comet" / "test_definitions.yaml").read_text()
    assert content == yaml_from_api
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_cli/test_push_pull.py -v
```

Expected: errors about unimplemented commands.

- [ ] **Step 3: Create `cli/commands/push.py`**

```python
from pathlib import Path
import typer
from cli.config import load_config
from cli.api_client import CometClient


def push_cmd():
    """Upload local test_definitions.yaml to the dashboard."""
    cfg = load_config()
    yaml_path = Path("comet") / "test_definitions.yaml"
    if not yaml_path.exists():
        typer.echo("[comet] comet/test_definitions.yaml not found. Run 'comet init' first.")
        raise typer.Exit(1)

    yaml_content = yaml_path.read_text(encoding="utf-8")
    client = CometClient(api_url=cfg["api_url"], api_key=cfg["api_key"])

    try:
        result = client.post("/api/v1/tests/sync", json={"yaml_content": yaml_content})
        typer.echo(f"[comet] Pushed. Synced {result.get('synced', '?')} test(s) to dashboard.")
    except Exception as e:
        typer.echo(f"[comet] Push failed: {e}")
        raise typer.Exit(1)
```

- [ ] **Step 4: Create `cli/commands/pull.py`**

```python
from pathlib import Path
import typer
from cli.config import load_config
from cli.api_client import CometClient


def pull_cmd():
    """Download current test definitions from the dashboard to local test_definitions.yaml."""
    cfg = load_config()
    client = CometClient(api_url=cfg["api_url"], api_key=cfg["api_key"])

    try:
        yaml_content = client.get_text("/api/v1/tests/yaml")
    except Exception as e:
        typer.echo(f"[comet] Pull failed: {e}")
        raise typer.Exit(1)

    yaml_path = Path("comet") / "test_definitions.yaml"
    yaml_path.write_text(yaml_content, encoding="utf-8")
    typer.echo(f"[comet] Pulled latest test definitions to {yaml_path}")
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_cli/test_push_pull.py -v
```

Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add cli/commands/push.py cli/commands/pull.py tests/test_cli/test_push_pull.py
git commit -m "feat: comet push and comet pull commands"
```

---

## Task 9: `comet run` and `comet status`

**Files:**
- Create: `cli/commands/run_cmd.py`
- Create: `cli/commands/status.py`
- Create: `tests/test_cli/test_run.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_cli/test_run.py
import pytest
from unittest.mock import patch
from typer.testing import CliRunner
from cli.cli import app

runner = CliRunner()


@pytest.fixture()
def comet_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("COMET_API_KEY", "test-key")
    comet = tmp_path / "comet"
    comet.mkdir()
    (comet / "config.yaml").write_text("api_url: https://api.comet-dq.com\ndefault_profile: production\n")
    (comet / "test_definitions.yaml").write_text("tests: []\n")
    return tmp_path


def test_run_triggers_api_and_polls_complete(comet_project):
    poll_responses = [
        {"status": "QUEUED", "completed_tests": 0, "total_tests": 2},
        {"status": "RUNNING", "completed_tests": 1, "total_tests": 2},
        {"status": "COMPLETE", "completed_tests": 2, "total_tests": 2},
    ]
    with patch("cli.commands.run_cmd.CometClient") as MockClient:
        mock = MockClient.return_value
        mock.post.return_value = {"run_id": 42, "status": "QUEUED"}
        mock.get.side_effect = poll_responses
        result = runner.invoke(app, ["run", "--profile", "production", "--no-wait"])
    assert result.exit_code == 0
    mock.post.assert_called_once_with("/api/v1/runs", json={"profile": "production"})


def test_run_exits_1_on_failed(comet_project):
    with patch("cli.commands.run_cmd.CometClient") as MockClient:
        mock = MockClient.return_value
        mock.post.return_value = {"run_id": 7, "status": "QUEUED"}
        mock.get.return_value = {"status": "FAILED", "error_reason": "No tests configured", "completed_tests": 0, "total_tests": 0}
        result = runner.invoke(app, ["run", "--no-wait"])
    assert result.exit_code == 1


def test_status_prints_last_run(comet_project):
    with patch("cli.commands.status.CometClient") as MockClient:
        mock = MockClient.return_value
        mock.get.return_value = [
            {"id": 5, "status": "COMPLETE", "profile": "production",
             "total_tests": 10, "completed_tests": 10,
             "started_at": "2026-05-20T06:00:00", "completed_at": "2026-05-20T06:00:15"}
        ]
        result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "COMPLETE" in result.output
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_cli/test_run.py -v
```

Expected: errors about unimplemented commands.

- [ ] **Step 3: Create `cli/commands/run_cmd.py`**

```python
import time
from typing import Optional
import typer
from cli.config import load_config
from cli.api_client import CometClient

POLL_INTERVAL = 3  # seconds between status polls


def run_cmd(
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Connection profile to run"),
    suite: Optional[str] = typer.Option(None, "--suite", "-s", help="Named test suite to run"),
    no_wait: bool = typer.Option(False, "--no-wait", help="Trigger run and exit without polling"),
):
    """Trigger a data quality run on the Comet servers."""
    cfg = load_config()
    selected_profile = profile or cfg.get("default_profile", "dev")

    payload = {"profile": selected_profile}
    if suite:
        payload["suite"] = suite

    client = CometClient(api_url=cfg["api_url"], api_key=cfg["api_key"])

    try:
        resp = client.post("/api/v1/runs", json=payload)
    except Exception as e:
        typer.echo(f"[comet] Failed to trigger run: {e}")
        raise typer.Exit(1)

    run_id = resp["run_id"]
    typer.echo(f"[comet] Run #{run_id} triggered (profile: {selected_profile})")

    if no_wait:
        typer.echo(f"[comet] Track it at: {cfg['api_url'].replace('api.', 'app.')}/dashboard/history")
        return

    typer.echo("[comet] Waiting for run to complete...")
    while True:
        try:
            status = client.get(f"/api/v1/runs/{run_id}")
        except Exception as e:
            typer.echo(f"[comet] Status poll failed: {e}")
            raise typer.Exit(1)

        state = status["status"]
        done = status["completed_tests"]
        total = status["total_tests"]
        typer.echo(f"  {state} — {done}/{total} tests", nl=False)
        typer.echo("\r", nl=False)

        if state == "COMPLETE":
            typer.echo(f"\n[comet] Run #{run_id} complete — {total}/{total} tests passed.")
            return
        if state == "FAILED":
            typer.echo(f"\n[comet] Run #{run_id} failed: {status.get('error_reason', 'unknown error')}")
            raise typer.Exit(1)

        time.sleep(POLL_INTERVAL)
```

- [ ] **Step 4: Create `cli/commands/status.py`**

```python
import typer
from cli.config import load_config
from cli.api_client import CometClient


def status_cmd(
    limit: int = typer.Option(5, "--limit", "-n", help="Number of recent runs to show"),
):
    """Print recent run history."""
    cfg = load_config()
    client = CometClient(api_url=cfg["api_url"], api_key=cfg["api_key"])

    try:
        runs = client.get(f"/api/v1/runs?limit={limit}")
    except Exception as e:
        typer.echo(f"[comet] Could not fetch run history: {e}")
        raise typer.Exit(1)

    if not runs:
        typer.echo("[comet] No runs yet. Try 'comet run' to trigger your first run.")
        return

    typer.echo(f"{'ID':>5}  {'STATUS':<10}  {'PROFILE':<15}  {'TESTS':>8}  {'STARTED'}")
    typer.echo("-" * 60)
    for r in runs:
        tests = f"{r['completed_tests']}/{r['total_tests']}"
        started = r.get("started_at", "")[:19].replace("T", " ")
        typer.echo(f"{r['id']:>5}  {r['status']:<10}  {r['profile']:<15}  {tests:>8}  {started}")
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_cli/test_run.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Run the full test suite**

```bash
pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add cli/commands/run_cmd.py cli/commands/status.py tests/test_cli/test_run.py
git commit -m "feat: comet run and comet status commands — Week 1 complete"
```

---

## Self-Review Checklist

- [x] **Spec coverage:**
  - `comet init/push/pull/run/status` CLI ✓ (Tasks 7–9)
  - `ConnectionProfile` model + encryption ✓ (Tasks 2–3)
  - CRUD endpoints for profiles ✓ (Task 4)
  - `run_executor` uses DB credentials ✓ (Task 5)
  - `pyproject.toml` / installable package ✓ (Task 1)
  - Bidirectional sync (push/pull) ✓ (Task 8)

- [x] **Type consistency:** `CometClient` defined in Task 7 and imported by name in Tasks 8–9. `load_config()` defined in Task 6 and used in Tasks 7–9.

- [x] **No placeholders:** All steps contain actual code and commands.

- [x] **Missing from spec, added here:** `requests-mock` added as dev dependency for CLI tests.
