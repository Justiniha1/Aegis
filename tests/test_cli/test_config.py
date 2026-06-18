import os
import pytest
from pathlib import Path

def test_config_yaml_is_fully_ignored(tmp_path, monkeypatch):
    """config.yaml is no longer read at all: even a present file does not affect config."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("COMET_API_KEY", "test-key-from-env")
    monkeypatch.delenv("COMET_API_URL", raising=False)
    monkeypatch.setattr("cli.config.load_dotenv", lambda *a, **k: None)

    comet_dir = tmp_path / "comet"
    comet_dir.mkdir()
    # A stray config.yaml with overrides must have no effect.
    (comet_dir / "config.yaml").write_text(
        "api_url: http://evil.example.com\ndefault_profile: production\n"
    )

    from cli.config import load_config
    cfg = load_config()
    assert cfg["api_url"] == "https://aegis-production-fa56.up.railway.app"
    assert cfg["default_profile"] == "dev"
    assert cfg["api_key"] == "test-key-from-env"


def test_load_config_without_file_uses_defaults(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("COMET_API_KEY", "test-key-defaults")
    monkeypatch.delenv("COMET_API_URL", raising=False)
    monkeypatch.setattr("cli.config.load_dotenv", lambda *a, **k: None)

    from cli.config import load_config
    cfg = load_config()
    assert cfg["api_url"] == "https://aegis-production-fa56.up.railway.app"
    assert cfg["default_profile"] == "dev"
    assert cfg["api_key"] == "test-key-defaults"


def test_config_yaml_cannot_override_api_url(tmp_path, monkeypatch):
    """The hosted api_url is fixed: a value in config.yaml must be ignored."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("COMET_API_KEY", "test-key-override")
    monkeypatch.delenv("COMET_API_URL", raising=False)
    monkeypatch.setattr("cli.config.load_dotenv", lambda *a, **k: None)

    comet_dir = tmp_path / "comet"
    comet_dir.mkdir()
    (comet_dir / "config.yaml").write_text("api_url: http://evil.example.com\n")

    from cli.config import load_config
    cfg = load_config()
    assert cfg["api_url"] == "https://aegis-production-fa56.up.railway.app"


def test_comet_api_url_env_is_ignored(tmp_path, monkeypatch):
    """COMET_API_URL is no longer honored: the hosted URL is fixed; clients cannot repoint it."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("COMET_API_KEY", "test-key-dev")
    monkeypatch.setenv("COMET_API_URL", "http://localhost:8000")
    monkeypatch.setattr("cli.config.load_dotenv", lambda *a, **k: None)

    from cli.config import load_config
    cfg = load_config()
    assert cfg["api_url"] == "https://aegis-production-fa56.up.railway.app"


def test_load_config_raises_when_no_api_key(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("COMET_API_KEY", raising=False)
    monkeypatch.setattr("cli.config.load_dotenv", lambda *a, **k: None)  # prevent project .env from re-setting the key
    monkeypatch.setattr("cli.config.find_dotenv", lambda *a, **k: "")  # don't let a real .env up the tree leak in

    comet_dir = tmp_path / "comet"
    comet_dir.mkdir()
    (comet_dir / "config.yaml").write_text("api_url: https://api.comet-dq.com\n")

    from cli.config import load_config
    with pytest.raises(SystemExit):
        load_config()


def test_api_client_get_raises_on_401(requests_mock):
    # A 401 is now translated into a friendly CometAPIError (H11) rather than leaking
    # the raw requests.HTTPError with its embedded URL.
    from cli.api_client import CometClient, CometAPIError
    requests_mock.get("https://api.comet-dq.com/api/v1/runs/latest", status_code=401)
    client = CometClient(api_url="https://api.comet-dq.com", api_key="bad-key")
    with pytest.raises(CometAPIError) as ei:
        client.get("/api/v1/runs/latest")
    assert "COMET_API_KEY" in str(ei.value)
