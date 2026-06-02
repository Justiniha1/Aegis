import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from dashboard_api.models import Base, Client, Run
from dashboard_api.auth import hash_key


def test_execute_run_fails_when_profile_not_in_yaml(monkeypatch, tmp_path):
    """Run -> FAILED when the requested profile is absent from the connection YAML."""
    monkeypatch.setenv("AEGIS_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-32-chars-xxxxxxxxxxxxx")
    conn = tmp_path / "database_connection.yaml"
    conn.write_text("dev:\n  type: sqlite\n  path: ./x.db\n", encoding="utf-8")
    monkeypatch.setenv("DQF_CONNECTION_YAML_PATH", str(conn))

    engine = create_engine(f"sqlite:///{tmp_path}/noprofile.db", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    client = Client(name="co2", api_key_hash=hash_key("key456"))
    db.add(client); db.commit()
    run = Run(client_id=client.id, profile="missing", status="QUEUED", total_tests=0, completed_tests=0)
    db.add(run); db.commit()
    run_id, client_id = run.id, client.id
    db.close()

    from unittest.mock import patch
    from dashboard_api.run_executor import execute_run
    with patch("dashboard_api.run_executor.SessionLocal", return_value=Session()):
        execute_run(run_id=run_id, client_id=client_id, profile="missing", type_filter=None)

    db2 = Session()
    updated = db2.query(Run).filter(Run.id == run_id).first()
    assert updated.status == "FAILED"
    assert "not found" in updated.error_reason
    db2.close()
