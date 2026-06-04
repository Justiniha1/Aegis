"""AegisAPIClient falls back to the baked hosted URL when AEGIS_API_URL is unset."""
import pytest

from aegis_dq._client import AegisAPIClient, DEFAULT_API_URL


def test_base_defaults_to_hosted_url_when_env_unset(monkeypatch):
    monkeypatch.delenv("AEGIS_API_URL", raising=False)
    client = AegisAPIClient(api_key="k")
    assert client._base == DEFAULT_API_URL


def test_env_overrides_default(monkeypatch):
    monkeypatch.setenv("AEGIS_API_URL", "http://localhost:8000")
    client = AegisAPIClient(api_key="k")
    assert client._base == "http://localhost:8000"


def test_constructor_arg_overrides_env(monkeypatch):
    monkeypatch.setenv("AEGIS_API_URL", "http://localhost:8000")
    client = AegisAPIClient(api_url="http://explicit", api_key="k")
    assert client._base == "http://explicit"


def test_missing_api_key_still_raises(monkeypatch):
    monkeypatch.delenv("AEGIS_API_URL", raising=False)
    monkeypatch.delenv("AEGIS_API_KEY", raising=False)
    with pytest.raises(ValueError):
        AegisAPIClient()
