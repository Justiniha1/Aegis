import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from typer.testing import CliRunner
from cli.cli import app

runner = CliRunner()


@pytest.fixture()
def aegis_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AEGIS_API_KEY", "test-key")
    aegis = tmp_path / "aegis"
    aegis.mkdir()
    (aegis / "config.yaml").write_text("api_url: https://api.aegis-dq.com\ndefault_profile: dev\n")
    (aegis / "test_definitions.yaml").write_text("tests:\n  - name: Test A\n    type: row_count\n")
    return tmp_path


def test_push_calls_sync_endpoint(aegis_project):
    with patch("cli.commands.push.AegisClient") as MockClient:
        mock = MockClient.return_value
        mock.post.return_value = {"synced": 1}
        result = runner.invoke(app, ["push"])
    assert result.exit_code == 0
    mock.post.assert_called_once()
    call_args = mock.post.call_args
    assert call_args[0][0] == "/api/v1/tests/sync"
    assert "yaml_content" in call_args[1]["json"]


def test_pull_writes_yaml_to_disk(aegis_project):
    yaml_from_api = "tests:\n  - name: Remote Test\n    type: row_count\n"
    with patch("cli.commands.pull.AegisClient") as MockClient:
        mock = MockClient.return_value
        mock.get_text.return_value = yaml_from_api
        result = runner.invoke(app, ["pull"])
    assert result.exit_code == 0
    content = (aegis_project / "aegis" / "test_definitions.yaml").read_text()
    assert content == yaml_from_api
