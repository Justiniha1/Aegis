"""Tests for is_website_schedulable predicate and the capability-aware profiles endpoint.

Capability is derived from the UNRESOLVED YAML type — no ${ENV} resolution, no secrets.
"""
import pytest
from fastapi.testclient import TestClient

from dashboard_api.models import Base, Client
from dashboard_api.database import get_db
from dashboard_api.auth import hash_key

# Fixture YAML: dev=sqlite (not schedulable), staging=postgres (schedulable).
# The staging profile has an unresolved ${} secret — must NOT be required to parse capability.
_YAML = """\
dev:
  type: sqlite
  path: ../../data/raw/sample_ecommerce.db
staging:
  type: postgres
  host: ${STAGING_DB_HOST}
  username: u
  password: ${STAGING_DB_PASSWORD}
"""


@pytest.fixture()
def client_app(monkeypatch, tmp_path):
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-32-chars-xxxxxxxxx")
    conn = tmp_path / "database_connection.yaml"
    conn.write_text(_YAML, encoding="utf-8")
    monkeypatch.setenv("DQF_CONNECTION_YAML_PATH", str(conn))

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    engine = create_engine(
        f"sqlite:///{tmp_path}/test.db",
        connect_args={"check_same_thread": False},
    )
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
    raw_key = "test-api-key-abc123"
    db = TestingSession()
    db.add(Client(name="testco", email="t@t.com", api_key_hash=hash_key(raw_key)))
    db.commit()
    db.close()
    yield TestClient(app), {"X-Api-Key": raw_key}
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Unit tests for the shared predicate
# ---------------------------------------------------------------------------

def test_is_website_schedulable_true_types():
    """Returns True for all cloud-reachable DB types (any case, trailing slash tolerated)."""
    from dashboard_api.connection_source import is_website_schedulable

    assert is_website_schedulable("postgresql") is True
    assert is_website_schedulable("postgres") is True
    assert is_website_schedulable("mysql") is True
    assert is_website_schedulable("mssql") is True
    assert is_website_schedulable("snowflake") is True
    # case insensitive
    assert is_website_schedulable("PostgreSQL") is True
    assert is_website_schedulable("MySQL") is True
    assert is_website_schedulable("Snowflake") is True
    # trailing slash tolerated
    assert is_website_schedulable("postgres/") is True


def test_is_website_schedulable_false_types():
    """Returns False for sqlite, empty string, and unknown types."""
    from dashboard_api.connection_source import is_website_schedulable

    assert is_website_schedulable("sqlite") is False
    assert is_website_schedulable("") is False
    assert is_website_schedulable("unknown") is False
    assert is_website_schedulable("mongodb") is False


def test_profile_types_no_env_resolution(monkeypatch):
    """profile_types returns (name->type) without requiring ${ENV} vars to be set."""
    from dashboard_api.connection_source import profile_types

    yaml_text = """\
dev:
  type: sqlite
  path: ./db.db
staging:
  type: postgres
  host: ${STAGING_DB_HOST}
  password: ${STAGING_DB_PASSWORD}
"""
    # Ensure the env vars are NOT set — function must not raise.
    monkeypatch.delenv("STAGING_DB_HOST", raising=False)
    monkeypatch.delenv("STAGING_DB_PASSWORD", raising=False)

    types = profile_types(yaml_text)
    assert types == {"dev": "sqlite", "staging": "postgres"}


# ---------------------------------------------------------------------------
# Endpoint capability tests
# ---------------------------------------------------------------------------

def test_profiles_endpoint_includes_capability(client_app):
    """GET /api/v1/profiles returns db_type and website_schedulable per profile."""
    tc, headers = client_app
    r = tc.get("/api/v1/profiles", headers=headers)
    assert r.status_code == 200
    body = r.json()

    by_name = {p["name"]: p for p in body}
    assert "dev" in by_name
    assert "staging" in by_name

    dev = by_name["dev"]
    assert dev["db_type"] == "sqlite"
    assert dev["website_schedulable"] is False

    staging = by_name["staging"]
    assert staging["db_type"] == "postgres"
    assert staging["website_schedulable"] is True


def test_profiles_endpoint_never_leaks_secrets(client_app):
    """Profile response carries exactly {name, is_default, db_type, website_schedulable} — no secrets."""
    tc, headers = client_app
    r = tc.get("/api/v1/profiles", headers=headers)
    assert r.status_code == 200
    body = r.json()

    response_text = str(body)
    assert "password" not in response_text
    assert "${" not in response_text

    expected_keys = {"name", "is_default", "db_type", "website_schedulable"}
    for item in body:
        assert set(item.keys()) == expected_keys, (
            f"Profile '{item.get('name')}' has unexpected keys: {set(item.keys())}"
        )
