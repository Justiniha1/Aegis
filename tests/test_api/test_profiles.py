from dashboard_api.models import ConnectionProfile

def test_connection_profile_model_fields():
    """Verify the model has the expected columns before hitting a DB."""
    cols = {c.name for c in ConnectionProfile.__table__.columns}
    assert cols == {"id", "client_id", "name", "connection_url_encrypted", "db_type", "created_at"}


import os
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from dashboard_api.models import Base, Client
from dashboard_api.database import get_db
from dashboard_api.auth import hash_key


@pytest.fixture()
def client_app(monkeypatch, tmp_path):
    monkeypatch.setenv("AEGIS_ENCRYPTION_KEY", Fernet.generate_key().decode())
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

    raw_key = "test-api-key-abc123"
    db = TestingSession()
    db.add(Client(name="testco", email="test@test.com", api_key_hash=hash_key(raw_key)))
    db.commit()
    db.close()

    yield TestClient(app), {"X-Api-Key": raw_key}
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
