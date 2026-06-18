"""Security tests for auth handling (H4) and credential-at-rest enforcement (H3).

H4: get_client_any_auth must distinguish an invalid/expired bearer token (clear 401)
from a missing credential, instead of silently swallowing the decode error.
H3: POST /profiles/sync must reject connection YAML containing literal secrets so
plaintext passwords never persist server-side; ${ENV} references stay allowed.
"""

import pytest
from fastapi.testclient import TestClient

from dashboard_api import auth
from dashboard_api.auth import hash_key
from dashboard_api.database import get_db
from dashboard_api.models import Base, Client


@pytest.fixture()
def client_app(monkeypatch, tmp_path):
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-32-chars-xxxxxxxxx")
    conn = tmp_path / "database_connection.yaml"
    conn.write_text("dev:\n  type: sqlite\n  path: ./d.db\n", encoding="utf-8")
    monkeypatch.setenv("DQF_CONNECTION_YAML_PATH", str(conn))

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(
        f"sqlite:///{tmp_path}/test.db", connect_args={"check_same_thread": False}
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
    c = Client(name="testco", email="t@t.com", api_key_hash=hash_key(raw_key))
    db.add(c)
    db.commit()
    client_id = c.id
    db.close()
    yield TestClient(app), {"X-Api-Key": raw_key}, client_id
    app.dependency_overrides.clear()


# ── H4: JWT handling in get_client_any_auth ──────────────────────────────────
def test_valid_api_key_authenticates(client_app):
    tc, headers, _ = client_app
    assert tc.get("/api/v1/profiles", headers=headers).status_code == 200


def test_valid_jwt_authenticates(client_app):
    tc, _, client_id = client_app
    token = auth.create_access_token(client_id)
    r = tc.get("/api/v1/profiles", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


def test_missing_credential_is_401_auth_required(client_app):
    tc, _, _ = client_app
    r = tc.get("/api/v1/profiles")
    assert r.status_code == 401


def test_invalid_bearer_token_reports_invalid_not_generic(client_app):
    tc, _, _ = client_app
    r = tc.get("/api/v1/profiles", headers={"Authorization": "Bearer not.a.real.token"})
    assert r.status_code == 401
    # Must distinguish a bad credential from a missing one (no silent swallow).
    assert r.json()["detail"] == "Invalid or expired token"


# ── H3: reject literal secrets at upload ─────────────────────────────────────
_ENV_YAML = "prod:\n  type: postgres\n  host: db\n  username: u\n  password: ${PROD_DB_PASSWORD}\n"
_LITERAL_PW_YAML = "prod:\n  type: postgres\n  host: db\n  username: u\n  password: hunter2\n"
_LITERAL_URL_YAML = "prod:\n  connection_url: postgresql://u:hunter2@db:5432/app\n"
_ENV_URL_YAML = "prod:\n  connection_url: postgresql://u:${PROD_DB_PASSWORD}@db:5432/app\n"


def test_sync_allows_env_reference_password(client_app):
    tc, headers, _ = client_app
    r = tc.post("/api/v1/profiles/sync", json={"yaml_content": _ENV_YAML}, headers=headers)
    assert r.status_code == 200


def test_sync_rejects_literal_password(client_app):
    tc, headers, _ = client_app
    r = tc.post("/api/v1/profiles/sync", json={"yaml_content": _LITERAL_PW_YAML}, headers=headers)
    assert r.status_code == 422
    assert "password" in r.json()["detail"].lower()


def test_sync_rejects_literal_password_in_connection_url(client_app):
    tc, headers, _ = client_app
    r = tc.post("/api/v1/profiles/sync", json={"yaml_content": _LITERAL_URL_YAML}, headers=headers)
    assert r.status_code == 422


def test_sync_allows_env_reference_in_connection_url(client_app):
    tc, headers, _ = client_app
    r = tc.post("/api/v1/profiles/sync", json={"yaml_content": _ENV_URL_YAML}, headers=headers)
    assert r.status_code == 200


# ── client self-service settings (alert webhook) ─────────────────────────────
def test_patch_me_sets_and_clears_alert_webhook(client_app):
    tc, _, client_id = client_app
    token = auth.create_access_token(client_id)
    auth_h = {"Authorization": f"Bearer {token}"}

    r = tc.patch("/api/v1/clients/me", json={"alert_webhook_url": "https://hooks.x/y"}, headers=auth_h)
    assert r.status_code == 200
    assert r.json()["alert_webhook_url"] == "https://hooks.x/y"

    # Empty string clears it.
    r2 = tc.patch("/api/v1/clients/me", json={"alert_webhook_url": ""}, headers=auth_h)
    assert r2.status_code == 200
    assert r2.json()["alert_webhook_url"] is None


def test_patch_me_requires_auth(client_app):
    tc, _, _ = client_app
    assert tc.patch("/api/v1/clients/me", json={"alert_webhook_url": "x"}).status_code in (401, 403)
