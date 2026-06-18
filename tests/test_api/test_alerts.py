"""Tests for scheduled-run failure alerting (webhook channel).

Alerts fire when a scheduled run FAILED to execute, or COMPLETEd but found failing/error
tests. A clean run produces no alert. Delivery is fail-safe — a broken webhook never
affects run execution.
"""

import types

import pytest
import requests

from dashboard_api import alerts


def _run(status="COMPLETE", run_id=1, profile="dev", total_tests=3, error_reason=None):
    return types.SimpleNamespace(
        id=run_id, status=status, profile=profile,
        total_tests=total_tests, error_reason=error_reason,
    )


# ── decision logic ───────────────────────────────────────────────────────────
def test_failed_run_produces_message():
    msg = alerts.build_alert_message("Acme", _run(status="FAILED", error_reason="boom"), 0, 0)
    assert msg and "FAILED" in msg and "boom" in msg


def test_complete_with_failures_produces_message():
    msg = alerts.build_alert_message("Acme", _run(status="COMPLETE"), failed_count=2, error_count=1)
    assert msg and "2 failed" in msg and "1 error" in msg


def test_clean_complete_produces_no_message():
    assert alerts.build_alert_message("Acme", _run(status="COMPLETE"), 0, 0) is None


def test_in_flight_run_produces_no_message():
    assert alerts.build_alert_message("Acme", _run(status="RUNNING"), 0, 0) is None


# ── delivery ─────────────────────────────────────────────────────────────────
def test_send_webhook_posts_text_and_fields(requests_mock):
    requests_mock.post("https://hooks.example.com/x", json={"ok": True})
    ok = alerts.send_webhook("https://hooks.example.com/x", "alert message", _run(run_id=9))
    assert ok is True
    body = requests_mock.last_request.json()
    assert body["text"] == "alert message"
    assert body["run_id"] == 9


def test_send_webhook_is_failsafe_on_error(requests_mock):
    requests_mock.post("https://hooks.example.com/x", exc=requests.exceptions.ConnectionError)
    # Must not raise; returns False.
    assert alerts.send_webhook("https://hooks.example.com/x", "m", _run()) is False


# ── end-to-end orchestration ─────────────────────────────────────────────────
@pytest.fixture()
def alert_db(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from dashboard_api.models import Base

    engine = create_engine(
        f"sqlite:///{tmp_path}/a.db", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    monkeypatch.setattr(alerts, "SessionLocal", Session)
    return Session


def _seed(Session, *, webhook, run_status, results=()):
    from dashboard_api.models import Client, Run, TestResult

    db = Session()
    c = Client(name="Acme", api_key_hash="h", alert_webhook_url=webhook)
    db.add(c)
    db.commit()
    run = Run(client_id=c.id, profile="dev", status=run_status,
              total_tests=3, completed_tests=len(results), error_reason="boom")
    db.add(run)
    db.commit()
    for status in results:
        db.add(TestResult(client_id=c.id, run_id=run.id, test_id="t", test_name="t",
                          test_type="row_count", status=status, severity="HIGH",
                          metrics={}, message="", run_at=run.started_at))
    db.commit()
    cid, rid = c.id, run.id
    db.close()
    return cid, rid


def test_alert_fires_webhook_for_failed_run(alert_db, requests_mock):
    requests_mock.post("https://hooks.example.com/x", json={"ok": True})
    cid, rid = _seed(alert_db, webhook="https://hooks.example.com/x", run_status="FAILED")
    alerts.maybe_send_run_alert(rid, cid)
    assert requests_mock.called
    assert "FAILED" in requests_mock.last_request.json()["text"]


def test_alert_fires_for_complete_run_with_failures(alert_db, requests_mock):
    requests_mock.post("https://hooks.example.com/x", json={"ok": True})
    cid, rid = _seed(alert_db, webhook="https://hooks.example.com/x",
                     run_status="COMPLETE", results=("PASSED", "FAILED"))
    alerts.maybe_send_run_alert(rid, cid)
    assert requests_mock.called


def test_no_alert_when_webhook_unset(alert_db, requests_mock):
    m = requests_mock.post("https://hooks.example.com/x", json={"ok": True})
    cid, rid = _seed(alert_db, webhook=None, run_status="FAILED")
    alerts.maybe_send_run_alert(rid, cid)
    assert not m.called


def test_no_alert_for_clean_complete(alert_db, requests_mock):
    m = requests_mock.post("https://hooks.example.com/x", json={"ok": True})
    cid, rid = _seed(alert_db, webhook="https://hooks.example.com/x",
                     run_status="COMPLETE", results=("PASSED", "PASSED"))
    alerts.maybe_send_run_alert(rid, cid)
    assert not m.called
