import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from typer.testing import CliRunner
from cli.cli import app

runner = CliRunner()


@pytest.fixture()
def comet_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("COMET_API_KEY", "test-key")
    comet = tmp_path / "comet"
    comet.mkdir()
    (comet / "config.yaml").write_text("api_url: https://api.comet-dq.com\ndefault_profile: dev\n")
    (comet / "test_definitions.yaml").write_text(
        "engine: Simple\n"
        "settings:\n"
        "  default_profile: dev\n"
        "  default_severity: MEDIUM\n"
        "tests:\n"
        "- name: Local Test\n"
        "  type: row_count\n"
    )
    return tmp_path


def test_push_calls_sync_endpoint(comet_project):
    with patch("cli.commands.push.CometClient") as MockClient:
        mock = MockClient.return_value
        mock.post.return_value = {"synced": 1}
        result = runner.invoke(app, ["push"])
    assert result.exit_code == 0
    mock.post.assert_called_once()
    call_args = mock.post.call_args
    assert call_args[0][0] == "/api/v1/tests/sync"
    assert "yaml_content" in call_args[1]["json"]


def test_pull_replaces_tests_and_preserves_settings(comet_project):
    """pull swaps in the server's tests but keeps the local engine/settings sections."""
    yaml_from_api = "tests:\n- name: Remote Test\n  type: row_count\n  profile: demo\n"
    with patch("cli.commands.pull.CometClient") as MockClient:
        mock = MockClient.return_value
        mock.get_text.return_value = yaml_from_api
        result = runner.invoke(app, ["pull"])
    assert result.exit_code == 0
    content = (comet_project / "comet" / "test_definitions.yaml").read_text()
    # Local engine/settings preserved (not wiped by the server's tests-only YAML).
    assert "engine: Simple" in content
    assert "default_profile: dev" in content
    assert "default_severity: MEDIUM" in content
    # Server tests swapped in; the old local test is gone.
    assert "Remote Test" in content
    assert "Local Test" not in content


def test_pull_writes_server_yaml_when_no_local_file(tmp_path, monkeypatch):
    """With no local file to preserve, pull writes the server's tests as-is."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("COMET_API_KEY", "test-key")
    (tmp_path / "comet").mkdir()
    yaml_from_api = "tests:\n- name: Remote Test\n  type: row_count\n"
    with patch("cli.commands.pull.CometClient") as MockClient:
        mock = MockClient.return_value
        mock.get_text.return_value = yaml_from_api
        result = runner.invoke(app, ["pull"])
    assert result.exit_code == 0
    content = (tmp_path / "comet" / "test_definitions.yaml").read_text()
    assert "Remote Test" in content
