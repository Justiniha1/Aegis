import os
import pytest
from unittest.mock import patch, MagicMock
from cryptography.fernet import Fernet
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from dashboard_api.models import Base, Client, Run, ConnectionProfile
from dashboard_api.auth import hash_key
from dashboard_api.encryption import encrypt


@pytest.fixture()
def db_session(monkeypatch, tmp_path):
    monkeypatch.setenv("AEGIS_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-32-chars-xxxxxxxxxxxxx")
    engine = create_engine(f"sqlite:///{tmp_path}/exec.db", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    db = Session()
    client = Client(name="co", api_key_hash=hash_key("key123"))
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
    monkeypatch.setenv("AEGIS_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-32-chars-xxxxxxxxxxxxx")
    engine = create_engine(f"sqlite:///{tmp_path}/noprofile.db", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    db = Session()
    client = Client(name="co2", api_key_hash=hash_key("key456"))
    db.add(client)
    db.commit()
    run = Run(client_id=client.id, profile="missing", status="QUEUED", total_tests=0, completed_tests=0)
    db.add(run)
    db.commit()
    run_id = run.id
    client_id = client.id
    db.close()

    from dashboard_api.run_executor import execute_run
    with patch("dashboard_api.run_executor.SessionLocal", return_value=Session()):
        execute_run(run_id=run_id, client_id=client_id, profile="missing", type_filter=None)

    db2 = Session()
    updated = db2.query(Run).filter(Run.id == run_id).first()
    assert updated.status == "FAILED"
    assert "missing" in updated.error_reason
    assert "Settings" in updated.error_reason or "not found" in updated.error_reason
    db2.close()


def test_execute_run_fails_when_decrypt_fails(monkeypatch, tmp_path):
    """Run should transition to FAILED if ConnectionProfile has invalid encrypted data."""
    monkeypatch.setenv("AEGIS_ENCRYPTION_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-32-chars-xxxxxxxxxxxxx")
    engine = create_engine(f"sqlite:///{tmp_path}/badencrypt.db", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    db = Session()
    client = Client(name="co3", api_key_hash=hash_key("key789"))
    db.add(client)
    db.commit()
    db.refresh(client)
    run = Run(client_id=client.id, profile="broken", status="QUEUED", total_tests=0, completed_tests=0)
    db.add(run)
    db.commit()
    db.refresh(run)
    profile = ConnectionProfile(
        client_id=client.id,
        name="broken",
        connection_url_encrypted="not-valid-fernet-data",
        db_type="sqlite",
    )
    db.add(profile)
    db.commit()
    run_id = run.id
    client_id = client.id
    db.close()

    from dashboard_api.run_executor import execute_run
    with patch("dashboard_api.run_executor.SessionLocal", return_value=Session()):
        execute_run(run_id=run_id, client_id=client_id, profile="broken", type_filter=None)

    db2 = Session()
    updated = db2.query(Run).filter(Run.id == run_id).first()
    assert updated.status == "FAILED"
    assert "Could not decrypt" in updated.error_reason
    db2.close()
