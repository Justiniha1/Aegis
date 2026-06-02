import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from dashboard_api.models import Base, Client, ConnectionProfile
from dashboard_api.database import get_db
from dashboard_api.auth import hash_key
from dashboard_api.encryption import decrypt


def test_connection_profile_model_fields():
    cols = {c.name for c in ConnectionProfile.__table__.columns}
    assert cols == {"id", "client_id", "name", "db_type", "host", "port",
                    "database", "username", "sqlite_path", "secret_env",
                    "secret_encrypted", "created_at"}


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
    yield TestClient(app), {"X-Api-Key": raw_key}, TestingSession
    app.dependency_overrides.clear()


def _create(tc, headers, **body):
    return tc.post("/api/v1/profiles", json=body, headers=headers)


def test_create_returns_structure_never_secret(client_app):
    tc, headers, _ = client_app
    r = _create(tc, headers, name="staging", db_type="postgresql", host="h", port=5432,
                database="analytics", username="reader",
                secret_env="AEGIS_STAGING_PASSWORD", secret_value="s3cret")
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "staging"
    assert body["secret_env"] == "AEGIS_STAGING_PASSWORD"
    assert body["host"] == "h"
    assert "secret_value" not in body and "secret_encrypted" not in body


def test_list_profiles(client_app):
    tc, headers, _ = client_app
    _create(tc, headers, name="dev", db_type="sqlite", sqlite_path="/app/data/x.db")
    r = tc.get("/api/v1/profiles", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_create_existing_name_updates_in_place(client_app):
    tc, headers, _ = client_app
    _create(tc, headers, name="staging", db_type="postgresql", host="old", username="u", secret_value="x")
    r = _create(tc, headers, name="staging", db_type="postgresql", host="new", username="u", secret_value="x")
    assert r.status_code == 201
    assert r.json()["host"] == "new"
    listed = tc.get("/api/v1/profiles", headers=headers).json()
    assert [p["name"] for p in listed].count("staging") == 1


def test_update_without_secret_preserves_existing_secret(client_app):
    tc, headers, Session = client_app
    pid = _create(tc, headers, name="staging", db_type="postgresql", host="h", username="u",
                  secret_value="keepme").json()["id"]
    r = tc.put(f"/api/v1/profiles/{pid}", json={"host": "h2"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["host"] == "h2"
    db = Session()
    row = db.query(ConnectionProfile).filter_by(id=pid).first()
    assert decrypt(row.secret_encrypted) == "keepme"
    db.close()


def test_empty_secret_value_does_not_clobber_existing(client_app):
    tc, headers, Session = client_app
    pid = _create(tc, headers, name="staging", db_type="postgresql", host="h", username="u",
                  secret_value="keepme").json()["id"]
    # re-upsert (and PUT) with an empty secret_value — must preserve the stored secret
    _create(tc, headers, name="staging", db_type="postgresql", host="h2", username="u", secret_value="")
    tc.put(f"/api/v1/profiles/{pid}", json={"host": "h3", "secret_value": ""}, headers=headers)
    db = Session()
    row = db.query(ConnectionProfile).filter_by(id=pid).first()
    assert decrypt(row.secret_encrypted) == "keepme"
    db.close()


def test_sqlite_profile_no_secret(client_app):
    tc, headers, _ = client_app
    r = _create(tc, headers, name="dev", db_type="sqlite", sqlite_path="/app/data/x.db")
    assert r.status_code == 201
    assert r.json()["secret_env"] is None


def test_delete_profile(client_app):
    tc, headers, _ = client_app
    _create(tc, headers, name="dev", db_type="sqlite", sqlite_path="/app/data/x.db")
    pid = tc.get("/api/v1/profiles", headers=headers).json()[0]["id"]
    assert tc.delete(f"/api/v1/profiles/{pid}", headers=headers).status_code == 204
    assert tc.get("/api/v1/profiles", headers=headers).json() == []
