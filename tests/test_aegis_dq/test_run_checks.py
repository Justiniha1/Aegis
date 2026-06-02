"""Unit tests for aegis_dq.run_checks().

Tests mock AegisAPIClient so no network or server is needed.
"""
import pytest
from unittest.mock import MagicMock, patch

from aegis_dq._run import run_checks, AegisDQChecksFailed, AegisDQRunTimeout


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

COMPLETE_RUN = {
    "id": 42,
    "status": "COMPLETE",
    "profile": "dev",
    "total_tests": 5,
    "completed_tests": 5,
    "error": None,
}

FAILED_RUN = {
    "id": 43,
    "status": "FAILED",
    "profile": "dev",
    "total_tests": 5,
    "completed_tests": 3,
    "error": {"reason": "null_check failed on column email", "at_test": 3},
}


def _mock_client(run_id: int, final_run: dict) -> MagicMock:
    """Return a mock AegisAPIClient that returns a fixed run_id and final_run dict."""
    client = MagicMock()
    client.trigger_run.return_value = run_id
    client.wait_for_run.return_value = final_run
    return client


# ---------------------------------------------------------------------------
# Happy path: COMPLETE run
# ---------------------------------------------------------------------------

def test_run_checks_returns_run_dict_on_complete(monkeypatch):
    monkeypatch.setenv("AEGIS_API_URL", "http://fake-aegis")
    monkeypatch.setenv("AEGIS_API_KEY", "test-key")

    with patch("aegis_dq._run.AegisAPIClient", return_value=_mock_client(42, COMPLETE_RUN)):
        result = run_checks(profile="dev")

    assert result["status"] == "COMPLETE"
    assert result["id"] == 42


def test_run_checks_does_not_raise_on_complete(monkeypatch):
    monkeypatch.setenv("AEGIS_API_URL", "http://fake-aegis")
    monkeypatch.setenv("AEGIS_API_KEY", "test-key")

    with patch("aegis_dq._run.AegisAPIClient", return_value=_mock_client(42, COMPLETE_RUN)):
        # Should not raise
        run_checks(profile="dev")


# ---------------------------------------------------------------------------
# Failure path: FAILED run
# ---------------------------------------------------------------------------

def test_run_checks_raises_on_failed_run(monkeypatch):
    monkeypatch.setenv("AEGIS_API_URL", "http://fake-aegis")
    monkeypatch.setenv("AEGIS_API_KEY", "test-key")

    with patch("aegis_dq._run.AegisAPIClient", return_value=_mock_client(43, FAILED_RUN)):
        with pytest.raises(AegisDQChecksFailed) as exc_info:
            run_checks(profile="dev")

    err = exc_info.value
    assert err.run_id == 43
    assert err.profile == "dev"
    assert "null_check failed on column email" in err.reason


def test_checks_failed_exception_is_exception_subclass():
    err = AegisDQChecksFailed(run_id=1, profile="prod", reason="bad data")
    assert isinstance(err, Exception)
    assert not isinstance(err, SystemExit)


def test_checks_failed_message_contains_profile_and_run_id():
    err = AegisDQChecksFailed(run_id=7, profile="staging", reason="schema mismatch")
    msg = str(err)
    assert "staging" in msg
    assert "7" in msg


# ---------------------------------------------------------------------------
# Credential injection paths
# ---------------------------------------------------------------------------

def test_run_checks_passes_explicit_creds_to_client(monkeypatch):
    # Ensure env vars are absent so we can confirm explicit args are used
    monkeypatch.delenv("AEGIS_API_URL", raising=False)
    monkeypatch.delenv("AEGIS_API_KEY", raising=False)

    with patch("aegis_dq._run.AegisAPIClient") as mock_cls:
        mock_cls.return_value = _mock_client(42, COMPLETE_RUN)
        run_checks(profile="dev", api_url="http://custom-host", api_key="explicit-key")
        mock_cls.assert_called_once_with(api_url="http://custom-host", api_key="explicit-key")


def test_run_checks_raises_value_error_when_creds_missing(monkeypatch):
    monkeypatch.delenv("AEGIS_API_URL", raising=False)
    monkeypatch.delenv("AEGIS_API_KEY", raising=False)

    with pytest.raises(ValueError):
        run_checks(profile="dev")


# ---------------------------------------------------------------------------
# Timeout path: AegisDQRunTimeout (max_wait_seconds)
# ---------------------------------------------------------------------------

def _timeout_client(run_id: int) -> MagicMock:
    """Mock AegisAPIClient whose wait_for_run raises TimeoutError (deadline hit)."""
    client = MagicMock()
    client.trigger_run.return_value = run_id
    client.wait_for_run.side_effect = TimeoutError("deadline exceeded")
    return client


def test_run_checks_raises_run_timeout_when_client_times_out(monkeypatch):
    monkeypatch.setenv("AEGIS_API_URL", "http://fake-aegis")
    monkeypatch.setenv("AEGIS_API_KEY", "test-key")

    with patch("aegis_dq._run.AegisAPIClient", return_value=_timeout_client(42)):
        with pytest.raises(AegisDQRunTimeout) as exc_info:
            run_checks(profile="dev", max_wait_seconds=30)

    err = exc_info.value
    assert err.profile == "dev"
    assert err.run_id == 42
    assert err.max_wait_seconds == 30


def test_run_timeout_exception_message_contains_profile_run_id_and_deadline():
    err = AegisDQRunTimeout(profile="staging", run_id=99, max_wait_seconds=120)
    msg = str(err)
    assert "staging" in msg
    assert "99" in msg
    assert "120" in msg


def test_run_timeout_is_exception_subclass():
    err = AegisDQRunTimeout(profile="p", run_id=1, max_wait_seconds=60)
    assert isinstance(err, Exception)
    assert not isinstance(err, SystemExit)


def test_run_checks_without_max_wait_seconds_does_not_raise_timeout(monkeypatch):
    monkeypatch.setenv("AEGIS_API_URL", "http://fake-aegis")
    monkeypatch.setenv("AEGIS_API_KEY", "test-key")

    with patch("aegis_dq._run.AegisAPIClient", return_value=_mock_client(42, COMPLETE_RUN)):
        result = run_checks(profile="dev")

    assert result["status"] == "COMPLETE"


def test_run_checks_passes_max_wait_seconds_to_wait_for_run(monkeypatch):
    monkeypatch.setenv("AEGIS_API_URL", "http://fake-aegis")
    monkeypatch.setenv("AEGIS_API_KEY", "test-key")

    with patch("aegis_dq._run.AegisAPIClient") as mock_cls:
        mock_cls.return_value = _mock_client(42, COMPLETE_RUN)
        run_checks(profile="dev", max_wait_seconds=45)
        call = mock_cls.return_value.wait_for_run.call_args
        passed = call.kwargs.get("max_wait_seconds", None)
        if passed is None and call.args:
            passed = 45 if 45 in call.args else None
        assert passed == 45, f"max_wait_seconds not forwarded to wait_for_run: {call}"
