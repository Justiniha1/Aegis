"""Concurrency-safety tests (H5 completed_tests, H8 active-run guard).

H8: a partial unique index enforces at most one active (QUEUED/RUNNING) run per client
at the database level, and the trigger endpoint converts the resulting IntegrityError
into the same 409 as the in-process guard (race-proof, not just check-then-insert).
H5: Run.completed_tests is incremented with an atomic SQL UPDATE so concurrent result
batches cannot clobber each other's increments.
"""

import pytest
from sqlalchemy.exc import IntegrityError
from fastapi.testclient import TestClient

from dashboard_api.auth import hash_key
from dashboard_api.database import get_db
from dashboard_api.models import Base, Client, Run, TestDefinition


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
    c = Client(name="co", email="t@t.com", api_key_hash=hash_key(raw_key))
    db.add(c)
    db.commit()
    cid = c.id
    db.close()
    yield TestClient(app), {"X-Api-Key": raw_key}, Session, cid, monkeypatch
    app.dependency_overrides.clear()


def _run(client_id, status, **kw):
    return Run(client_id=client_id, profile="dev", status=status,
               total_tests=kw.get("total", 0), completed_tests=kw.get("completed", 0))


# ── H8 ───────────────────────────────────────────────────────────────────────
def test_db_enforces_one_active_run_per_client(env):
    _, _, Session, cid, _ = env
    db = Session()
    db.add(_run(cid, "QUEUED"))
    db.commit()
    db.add(_run(cid, "RUNNING"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.close()


def test_db_allows_many_terminal_runs(env):
    _, _, Session, cid, _ = env
    db = Session()
    db.add(_run(cid, "COMPLETE"))
    db.add(_run(cid, "COMPLETE"))
    db.add(_run(cid, "FAILED"))
    db.commit()  # terminal runs are excluded from the partial index — no conflict
    assert db.query(Run).filter(Run.client_id == cid).count() == 3
    db.close()


def test_trigger_returns_409_when_insert_races(env):
    tc, headers, Session, cid, monkeypatch = env
    # An enabled test so the pre-flight count passes.
    db = Session()
    db.add(TestDefinition(client_id=cid, name="t", type="row_count",
                          severity="MEDIUM", enabled=True, config={}, profile="dev"))
    db.add(_run(cid, "QUEUED"))  # an active run already exists
    db.commit()
    db.close()

    # Simulate the race: the in-process guard sees no active run, so the code proceeds
    # to insert — and the DB index must catch it, surfacing 409 (not 500).
    monkeypatch.setattr("dashboard_api.routers.runs.active_run", lambda db, client_id: None)
    r = tc.post("/api/v1/runs", json={"profile": "dev"}, headers=headers)
    assert r.status_code == 409


# ── H5 ───────────────────────────────────────────────────────────────────────
def test_completed_tests_accumulates_across_batches(env):
    tc, headers, Session, cid, _ = env
    db = Session()
    run = _run(cid, "RUNNING", total=5, completed=0)
    db.add(run)
    db.commit()
    run_id = run.id
    db.close()

    def _result(i):
        return {"test_id": f"t{i}", "name": f"T{i}", "type": "row_count",
                "status": "PASSED", "severity": "MEDIUM", "metrics": {}, "message": "ok"}

    tc.post("/api/v1/results",
            json={"results": [_result(1), _result(2)], "run_id": run_id}, headers=headers)
    tc.post("/api/v1/results",
            json={"results": [_result(3), _result(4), _result(5)], "run_id": run_id}, headers=headers)

    db = Session()
    assert db.query(Run).filter(Run.id == run_id).first().completed_tests == 5
    db.close()
