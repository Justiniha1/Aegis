"""GET /api/v1/results must accept dbt_* type filters (comet dbt publish ingest)."""
import pytest
from fastapi.testclient import TestClient

from dashboard_api.auth import hash_key
from dashboard_api.database import get_db
from dashboard_api.models import Base, Client


_YAML = "dev:\n  type: sqlite\n  path: ./d.db\n"


@pytest.fixture()
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-32-chars-xxxxxxxxx")
    conn = tmp_path / "database_connection.yaml"
    conn.write_text(_YAML, encoding="utf-8")
    monkeypatch.setenv("DQF_CONNECTION_YAML_PATH", str(conn))

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(
        f"sqlite:///{tmp_path}/test.db", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    from dashboard_api.main import app

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    raw_key = "test-api-key-abc123"
    db = Session()
    db.add(Client(name="co", email="t@t.com", api_key_hash=hash_key(raw_key)))
    db.commit()
    db.close()
    yield TestClient(app), {"X-Api-Key": raw_key}
    app.dependency_overrides.clear()


def test_ingest_and_filter_dbt_results(env):
    client, headers = env
    # Ingest a dbt result via the same endpoint comet dbt publish uses.
    batch = {
        "run_profile": "dbt",
        "results": [{
            "test_id": "test.demo.unique_orders_id.bbb222",
            "name": "unique_orders_id",
            "type": "dbt_unique",
            "status": "FAILED",
            "severity": "HIGH",
            "metrics": {"failures": 3},
            "message": "Got 3 results",
        }],
    }
    post = client.post("/api/v1/results", json=batch, headers=headers)
    assert post.status_code == 201, post.text

    # Filtering by the dbt type must be accepted (was 400 before the allowlist change).
    got = client.get("/api/v1/results?test_type=dbt_unique", headers=headers)
    assert got.status_code == 200, got.text
    assert any(r["test_type"] == "dbt_unique" for r in got.json())
