"""Tests for client provisioning access control.

POST /api/v1/clients mints an account + API key. It must NOT be open to the public in
production: clients are provisioned by the operator. Gating is via X-Admin-Token, which
is required whenever COMET_ADMIN_TOKEN is configured (and mandatory in production). Local
development with no token stays open so `make seed` works with zero config.
"""

import pytest
from fastapi.testclient import TestClient

from dashboard_api.database import get_db
from dashboard_api.models import Base


@pytest.fixture()
def app_client(monkeypatch, tmp_path):
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-32-chars-xxxxxxxxx")
    monkeypatch.delenv("COMET_ADMIN_TOKEN", raising=False)
    monkeypatch.delenv("COMET_ENV", raising=False)

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
    yield TestClient(app), monkeypatch
    app.dependency_overrides.clear()


def _body(name="acme"):
    return {"name": name, "email": f"{name}@x.com", "password": "pw12345"}


def test_create_client_open_in_dev_without_token(app_client):
    tc, _ = app_client
    r = tc.post("/api/v1/clients", json=_body("acme"))
    assert r.status_code == 201
    assert "api_key" in r.json()


def test_create_client_requires_token_when_configured(app_client):
    tc, mp = app_client
    mp.setenv("COMET_ADMIN_TOKEN", "s3cret")
    # No token -> rejected
    assert tc.post("/api/v1/clients", json=_body("a")).status_code == 403
    # Wrong token -> rejected
    r_wrong = tc.post("/api/v1/clients", json=_body("b"), headers={"X-Admin-Token": "nope"})
    assert r_wrong.status_code == 403
    # Correct token -> created
    r_ok = tc.post("/api/v1/clients", json=_body("c"), headers={"X-Admin-Token": "s3cret"})
    assert r_ok.status_code == 201


def test_create_client_required_in_production_even_without_configured_token(app_client):
    # Defense in depth: if somehow running in production with no token, the endpoint must
    # not be open. (Boot guardrail also blocks this config, but the route stays safe.)
    tc, mp = app_client
    mp.setenv("COMET_ENV", "production")
    assert tc.post("/api/v1/clients", json=_body("d")).status_code == 403
