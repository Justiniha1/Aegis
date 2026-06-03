import os
import pytest
from pathlib import Path

def test_load_config_reads_yaml_and_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AEGIS_API_KEY", "test-key-from-env")

    aegis_dir = tmp_path / "aegis"
    aegis_dir.mkdir()
    (aegis_dir / "config.yaml").write_text(
        "api_url: https://api.aegis-dq.com\ndefault_profile: production\n"
    )

    from cli.config import load_config
    cfg = load_config()
    assert cfg["api_url"] == "https://api.aegis-dq.com"
    assert cfg["default_profile"] == "production"
    assert cfg["api_key"] == "test-key-from-env"


def test_load_config_without_file_uses_defaults(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AEGIS_API_KEY", "test-key-defaults")
    monkeypatch.setattr("cli.config.load_dotenv", lambda: None)

    from cli.config import load_config
    cfg = load_config()
    assert cfg["api_url"] == "https://api.aegis-dq.com"
    assert cfg["default_profile"] == "dev"
    assert cfg["api_key"] == "test-key-defaults"


def test_load_config_file_overrides_defaults(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AEGIS_API_KEY", "test-key-override")
    monkeypatch.setattr("cli.config.load_dotenv", lambda: None)

    aegis_dir = tmp_path / "aegis"
    aegis_dir.mkdir()
    (aegis_dir / "config.yaml").write_text("api_url: http://localhost:8000\n")

    from cli.config import load_config
    cfg = load_config()
    assert cfg["api_url"] == "http://localhost:8000"


def test_load_config_raises_when_no_api_key(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AEGIS_API_KEY", raising=False)
    monkeypatch.setattr("cli.config.load_dotenv", lambda: None)  # prevent project .env from re-setting the key

    aegis_dir = tmp_path / "aegis"
    aegis_dir.mkdir()
    (aegis_dir / "config.yaml").write_text("api_url: https://api.aegis-dq.com\n")

    from cli.config import load_config
    with pytest.raises(SystemExit):
        load_config()


def test_api_client_get_raises_on_401(requests_mock):
    from cli.api_client import AegisClient
    requests_mock.get("https://api.aegis-dq.com/api/v1/runs/latest", status_code=401)
    client = AegisClient(api_url="https://api.aegis-dq.com", api_key="bad-key")
    import requests
    with pytest.raises(requests.HTTPError):
        client.get("/api/v1/runs/latest")
