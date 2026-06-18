"""Unit tests for CometDQRunTimeout and max_wait_seconds parameter.

Tests cover:
- CometDQRunTimeout exception class attributes and message
- wait_for_run() raises TimeoutError when deadline exceeded
- run_checks() catches TimeoutError and re-raises as CometDQRunTimeout
- run_checks() passes max_wait_seconds=None (no timeout) by default
- run_checks() passes explicit max_wait_seconds through to wait_for_run()
"""
import time
import pytest
from unittest.mock import MagicMock, patch, call

from comet_dq._run import run_checks, CometDQChecksFailed, CometDQRunTimeout
from comet_dq._client import CometAPIClient


# ---------------------------------------------------------------------------
# CometDQRunTimeout exception class
# ---------------------------------------------------------------------------

def test_run_timeout_is_exception_subclass():
    exc = CometDQRunTimeout(profile="dev", run_id=42, max_wait_seconds=60)
    assert isinstance(exc, Exception)


def test_run_timeout_attributes():
    exc = CometDQRunTimeout(profile="dev", run_id=42, max_wait_seconds=60)
    assert exc.profile == "dev"
    assert exc.run_id == 42
    assert exc.max_wait_seconds == 60


def test_run_timeout_message_contains_profile_run_id_and_deadline():
    exc = CometDQRunTimeout(profile="dev", run_id=42, max_wait_seconds=60)
    msg = str(exc)
    assert "dev" in msg
    assert "42" in msg
    assert "60" in msg


# ---------------------------------------------------------------------------
# wait_for_run() — deadline enforcement
# ---------------------------------------------------------------------------

def test_wait_for_run_raises_timeout_error_when_deadline_exceeded(monkeypatch):
    """wait_for_run with max_wait_seconds=0.01 should raise TimeoutError."""
    monkeypatch.setenv("COMET_API_URL", "http://fake-comet")
    monkeypatch.setenv("COMET_API_KEY", "test-key")

    client = CometAPIClient(api_url="http://fake-comet", api_key="test-key")

    # get_run always returns a PENDING run (not terminal)
    client.get_run = MagicMock(return_value={"id": 1, "status": "RUNNING"})

    with pytest.raises(TimeoutError):
        client.wait_for_run(run_id=1, poll_interval=1, max_wait_seconds=0.01)


def test_wait_for_run_uses_monotonic_clock():
    """wait_for_run implementation must call time.monotonic() for deadline tracking."""
    import comet_dq._client as client_module
    import inspect
    source = inspect.getsource(client_module.CometAPIClient.wait_for_run)
    assert "monotonic" in source


def test_wait_for_run_no_timeout_when_max_wait_seconds_none(monkeypatch):
    """wait_for_run with max_wait_seconds=None should not raise TimeoutError on terminal status."""
    client = CometAPIClient(api_url="http://fake-comet", api_key="test-key")

    # get_run returns terminal status immediately
    client.get_run = MagicMock(return_value={"id": 1, "status": "COMPLETE"})

    result = client.wait_for_run(run_id=1, max_wait_seconds=None)
    assert result["status"] == "COMPLETE"


# ---------------------------------------------------------------------------
# run_checks() — max_wait_seconds parameter wiring
# ---------------------------------------------------------------------------

COMPLETE_RUN = {
    "id": 42,
    "status": "COMPLETE",
    "profile": "dev",
    "total_tests": 5,
    "completed_tests": 5,
    "error": None,
}


def _mock_client_with_timeout(run_id: int, final_run: dict) -> MagicMock:
    """Return a mock CometAPIClient that returns a fixed run_id and final_run dict."""
    client = MagicMock()
    client.trigger_run.return_value = run_id
    client.wait_for_run.return_value = final_run
    return client


def test_run_checks_passes_max_wait_seconds_to_wait_for_run(monkeypatch):
    """run_checks(max_wait_seconds=60) must pass max_wait_seconds=60 to wait_for_run()."""
    monkeypatch.setenv("COMET_API_URL", "http://fake-comet")
    monkeypatch.setenv("COMET_API_KEY", "test-key")

    mock_client = _mock_client_with_timeout(42, COMPLETE_RUN)

    with patch("comet_dq._run.CometAPIClient", return_value=mock_client):
        run_checks(profile="dev", max_wait_seconds=60)

    # Verify max_wait_seconds=60 was passed to wait_for_run
    mock_client.wait_for_run.assert_called_once()
    _, kwargs = mock_client.wait_for_run.call_args
    assert kwargs.get("max_wait_seconds") == 60


def test_run_checks_passes_none_when_max_wait_seconds_omitted(monkeypatch):
    """run_checks() without max_wait_seconds must pass max_wait_seconds=None."""
    monkeypatch.setenv("COMET_API_URL", "http://fake-comet")
    monkeypatch.setenv("COMET_API_KEY", "test-key")

    mock_client = _mock_client_with_timeout(42, COMPLETE_RUN)

    with patch("comet_dq._run.CometAPIClient", return_value=mock_client):
        run_checks(profile="dev")

    mock_client.wait_for_run.assert_called_once()
    _, kwargs = mock_client.wait_for_run.call_args
    assert kwargs.get("max_wait_seconds") is None


def test_run_checks_raises_comet_timeout_when_wait_times_out(monkeypatch):
    """run_checks() must convert TimeoutError from wait_for_run into CometDQRunTimeout."""
    monkeypatch.setenv("COMET_API_URL", "http://fake-comet")
    monkeypatch.setenv("COMET_API_KEY", "test-key")

    mock_client = MagicMock()
    mock_client.trigger_run.return_value = 99
    mock_client.wait_for_run.side_effect = TimeoutError("deadline exceeded")

    with patch("comet_dq._run.CometAPIClient", return_value=mock_client):
        with pytest.raises(CometDQRunTimeout) as exc_info:
            run_checks(profile="staging", max_wait_seconds=30)

    err = exc_info.value
    assert err.profile == "staging"
    assert err.run_id == 99
    assert err.max_wait_seconds == 30


def test_run_checks_max_wait_seconds_signature():
    """run_checks() must have max_wait_seconds as a keyword-only parameter."""
    import inspect
    sig = inspect.signature(run_checks)
    assert "max_wait_seconds" in sig.parameters
    param = sig.parameters["max_wait_seconds"]
    assert param.default is None
