"""CometAPIClient falls back to the baked hosted URL when COMET_API_URL is unset."""
import pytest

from comet_dq._client import CometAPIClient, DEFAULT_API_URL


def test_base_defaults_to_hosted_url_when_env_unset(monkeypatch):
    monkeypatch.delenv("COMET_API_URL", raising=False)
    client = CometAPIClient(api_key="k")
    assert client._base == DEFAULT_API_URL


def test_env_is_ignored(monkeypatch):
    """COMET_API_URL is no longer honored — the hosted URL is fixed and not env-configurable."""
    monkeypatch.setenv("COMET_API_URL", "http://localhost:8000")
    client = CometAPIClient(api_key="k")
    assert client._base == DEFAULT_API_URL


def test_constructor_arg_sets_base(monkeypatch):
    """The api_url= constructor arg is the only override (internal/testing)."""
    monkeypatch.setenv("COMET_API_URL", "http://localhost:8000")  # ignored
    client = CometAPIClient(api_url="http://explicit", api_key="k")
    assert client._base == "http://explicit"


def test_missing_api_key_still_raises(monkeypatch):
    monkeypatch.delenv("COMET_API_URL", raising=False)
    monkeypatch.delenv("COMET_API_KEY", raising=False)
    with pytest.raises(ValueError):
        CometAPIClient()
