"""API tests for the schedules CRUD router.

Tenant isolation, capability guardrail, secret-leak prevention.
"""
import pytest
from fastapi.testclient import TestClient

from dashboard_api.models import Base, Client
from dashboard_api.database import get_db
from dashboard_api.auth import hash_key

# Two-profile YAML: dev=sqlite (not schedulable), staging=postgres (schedulable)
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
    """Single-client fixture for basic schedule tests."""
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


@pytest.fixture()
def two_client_app(monkeypatch, tmp_path):
    """Two-client fixture for tenant-isolation tests."""
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

    raw_key_a = "api-key-client-a"
    raw_key_b = "api-key-client-b"
    db = TestingSession()
    db.add(Client(name="client-a", email="a@test.com", api_key_hash=hash_key(raw_key_a)))
    db.add(Client(name="client-b", email="b@test.com", api_key_hash=hash_key(raw_key_b)))
    db.commit()
    db.close()

    tc = TestClient(app)
    yield tc, {"X-Api-Key": raw_key_a}, {"X-Api-Key": raw_key_b}
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Test: create schedule on schedulable profile (postgres) -> 201 with metadata
# ---------------------------------------------------------------------------

def test_create_schedule_on_schedulable_profile(client_app):
    tc, headers = client_app
    r = tc.post(
        "/api/v1/schedules",
        json={"profile": "staging", "preset": "daily", "at_hour": 6},
        headers=headers,
    )
    assert r.status_code in (200, 201), r.text
    body = r.json()
    assert body["profile"] == "staging"
    assert body["preset"] == "daily"
    assert body["enabled"] is True
    assert body["next_run_at"] is not None


# ---------------------------------------------------------------------------
# Test: sqlite profile is rejected with 400
# ---------------------------------------------------------------------------

def test_create_schedule_on_sqlite_rejected(client_app):
    tc, headers = client_app
    r = tc.post(
        "/api/v1/schedules",
        json={"profile": "dev", "preset": "daily", "at_hour": 6},
        headers=headers,
    )
    assert r.status_code == 400, r.text
    detail = r.json().get("detail", "")
    assert "cannot be scheduled" in detail or "not schedulable" in detail.lower(), (
        f"Expected 'cannot be scheduled' in detail, got: {detail}"
    )


# ---------------------------------------------------------------------------
# Test: unknown profile is rejected with 400
# ---------------------------------------------------------------------------

def test_create_unknown_profile_rejected(client_app):
    tc, headers = client_app
    r = tc.post(
        "/api/v1/schedules",
        json={"profile": "nonexistent", "preset": "daily", "at_hour": 6},
        headers=headers,
    )
    assert r.status_code == 400, r.text
    detail = r.json().get("detail", "")
    assert "not found" in detail.lower(), f"Expected 'not found' in detail, got: {detail}"


# ---------------------------------------------------------------------------
# Test: duplicate (client, profile) -> 409
# ---------------------------------------------------------------------------

def test_unique_per_profile(client_app):
    tc, headers = client_app
    # First create succeeds
    r1 = tc.post(
        "/api/v1/schedules",
        json={"profile": "staging", "preset": "daily", "at_hour": 6},
        headers=headers,
    )
    assert r1.status_code in (200, 201), r1.text

    # Second create for same profile must fail
    r2 = tc.post(
        "/api/v1/schedules",
        json={"profile": "staging", "preset": "hourly"},
        headers=headers,
    )
    assert r2.status_code in (409, 400), r2.text
    detail = r2.json().get("detail", "")
    assert "already has a schedule" in detail.lower() or "already" in detail.lower(), (
        f"Expected 'already has a schedule' in detail, got: {detail}"
    )


# ---------------------------------------------------------------------------
# Test: list -> pause -> delete lifecycle
# ---------------------------------------------------------------------------

def test_list_and_pause_and_delete(client_app):
    tc, headers = client_app

    # Create
    r = tc.post(
        "/api/v1/schedules",
        json={"profile": "staging", "preset": "hourly"},
        headers=headers,
    )
    assert r.status_code in (200, 201), r.text
    sched_id = r.json()["id"]

    # List shows it
    r = tc.get("/api/v1/schedules", headers=headers)
    assert r.status_code == 200
    ids = [s["id"] for s in r.json()]
    assert sched_id in ids

    # Pause (PATCH enabled=false)
    r = tc.patch(
        f"/api/v1/schedules/{sched_id}",
        json={"enabled": False},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["enabled"] is False

    # Delete
    r = tc.delete(f"/api/v1/schedules/{sched_id}", headers=headers)
    assert r.status_code in (200, 204), r.text

    # GET after delete -> 404
    r = tc.get(f"/api/v1/schedules/{sched_id}", headers=headers)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Test: tenant isolation — cross-client access returns 404, never 403
# ---------------------------------------------------------------------------

def test_tenant_isolation_404(two_client_app):
    tc, headers_a, headers_b = two_client_app

    # Client A creates a schedule
    r = tc.post(
        "/api/v1/schedules",
        json={"profile": "staging", "preset": "daily", "at_hour": 6},
        headers=headers_a,
    )
    assert r.status_code in (200, 201), r.text
    sched_id = r.json()["id"]

    # Client B tries to GET client A's schedule — must 404
    r = tc.get(f"/api/v1/schedules/{sched_id}", headers=headers_b)
    assert r.status_code == 404, f"Expected 404, got {r.status_code}"

    # Client B PATCH -> 404
    r = tc.patch(
        f"/api/v1/schedules/{sched_id}",
        json={"enabled": False},
        headers=headers_b,
    )
    assert r.status_code == 404, f"Expected 404, got {r.status_code}"

    # Client B DELETE -> 404
    r = tc.delete(f"/api/v1/schedules/{sched_id}", headers=headers_b)
    assert r.status_code == 404, f"Expected 404, got {r.status_code}"

    # Client B list must NOT show client A's schedule
    r = tc.get("/api/v1/schedules", headers=headers_b)
    assert r.status_code == 200
    b_ids = [s["id"] for s in r.json()]
    assert sched_id not in b_ids


# ---------------------------------------------------------------------------
# Test: responses contain no secrets
# ---------------------------------------------------------------------------

def test_response_has_no_secrets(client_app):
    tc, headers = client_app
    r = tc.post(
        "/api/v1/schedules",
        json={"profile": "staging", "preset": "daily", "at_hour": 6},
        headers=headers,
    )
    assert r.status_code in (200, 201), r.text
    body = r.json()
    body_str = str(body)

    assert "password" not in body_str.lower(), "Response leaks 'password'"
    assert "${" not in body_str, "Response leaks unresolved env var reference"

    # Keys must only be ScheduleOut fields
    allowed_keys = {"id", "client_id", "profile", "preset", "cron", "enabled",
                    "last_run_at", "next_run_at"}
    extra_keys = set(body.keys()) - allowed_keys
    assert not extra_keys, f"Unexpected keys in ScheduleOut: {extra_keys}"


# ---------------------------------------------------------------------------
# Test (WR-01): PATCH re-derives capability — a downgraded profile is rejected
# ---------------------------------------------------------------------------

def test_patch_rejects_profile_downgraded_to_non_schedulable(monkeypatch, tmp_path):
    """If a profile is downgraded to sqlite after its schedule exists, PATCH that would
    keep it enabled must be rejected with 400 (the create guard alone is not enough)."""
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-32-chars-xxxxxxxxx")
    conn = tmp_path / "database_connection.yaml"
    conn.write_text(_YAML, encoding="utf-8")  # staging=postgres (schedulable)
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
    raw_key = "downgrade-test-key"
    db = TestingSession()
    db.add(Client(name="dc", email="dc@test.com", api_key_hash=hash_key(raw_key)))
    db.commit()
    db.close()
    headers = {"X-Api-Key": raw_key}

    try:
        tc = TestClient(app)
        # Create a schedule while staging is still postgres (schedulable)
        r = tc.post(
            "/api/v1/schedules",
            json={"profile": "staging", "preset": "daily", "at_hour": 6},
            headers=headers,
        )
        assert r.status_code in (200, 201), r.text
        sched_id = r.json()["id"]

        # Downgrade staging to sqlite (non-schedulable) by rewriting the YAML
        conn.write_text(
            "dev:\n  type: sqlite\n  path: x.db\n"
            "staging:\n  type: sqlite\n  path: y.db\n",
            encoding="utf-8",
        )

        # PATCH that leaves the schedule enabled must now be rejected
        r = tc.patch(
            f"/api/v1/schedules/{sched_id}",
            json={"preset": "hourly"},
            headers=headers,
        )
        assert r.status_code == 400, r.text
        assert "cannot be scheduled" in r.json().get("detail", ""), r.text

        # Pausing (enabled=False) must still be allowed so operators can turn it off
        r = tc.patch(
            f"/api/v1/schedules/{sched_id}",
            json={"enabled": False},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["enabled"] is False
    finally:
        app.dependency_overrides.clear()
