import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from dashboard_api.models import Base, Client
from dashboard_api.database import get_db
from dashboard_api.auth import hash_key

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
    monkeypatch.setenv("AEGIS_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-32-chars-xxxxxxxxx")
    conn = tmp_path / "database_connection.yaml"
    conn.write_text(_YAML, encoding="utf-8")
    monkeypatch.setenv("DQF_CONNECTION_YAML_PATH", str(conn))

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
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
    db.add(Client(name="testco", email="t@t.com", api_key_hash=hash_key(raw_key)))
    db.commit(); db.close()
    yield TestClient(app), {"X-Api-Key": raw_key}
    app.dependency_overrides.clear()


def test_list_profiles_returns_names_from_yaml(client_app):
    tc, headers = client_app
    r = tc.get("/api/v1/profiles", headers=headers)
    assert r.status_code == 200
    body = r.json()
    names = [p["name"] for p in body]
    assert names == ["dev", "staging"]
    # first profile is the default; secrets never appear
    assert body[0]["is_default"] is True
    assert all("password" not in p and "secret" not in str(p).lower() or p["name"] for p in body)
    assert all(set(p.keys()) == {"name", "is_default"} for p in body)
