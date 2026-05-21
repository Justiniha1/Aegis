import pytest
from unittest.mock import patch
from typer.testing import CliRunner
from cli.cli import app

runner = CliRunner()


@pytest.fixture()
def aegis_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AEGIS_API_KEY", "test-key")
    aegis = tmp_path / "aegis"
    aegis.mkdir()
    (aegis / "config.yaml").write_text("api_url: https://api.aegis-dq.com\ndefault_profile: production\n")
    (aegis / "test_definitions.yaml").write_text("tests: []\n")
    return tmp_path


def test_run_triggers_api_and_polls_complete(aegis_project):
    poll_responses = [
        {"status": "QUEUED", "completed_tests": 0, "total_tests": 2},
        {"status": "RUNNING", "completed_tests": 1, "total_tests": 2},
        {"status": "COMPLETE", "completed_tests": 2, "total_tests": 2},
    ]
    with patch("cli.commands.run_cmd.AegisClient") as MockClient:
        mock = MockClient.return_value
        mock.post.return_value = {"run_id": 42, "status": "QUEUED"}
        mock.get.side_effect = poll_responses
        result = runner.invoke(app, ["run", "--profile", "production", "--no-wait"])
    assert result.exit_code == 0
    mock.post.assert_called_once_with("/api/v1/runs", json={"profile": "production"})


def test_run_exits_1_on_failed(aegis_project):
    with patch("cli.commands.run_cmd.AegisClient") as MockClient:
        mock = MockClient.return_value
        mock.post.return_value = {"run_id": 7, "status": "QUEUED"}
        mock.get.return_value = {"status": "FAILED", "error_reason": "No tests configured", "completed_tests": 0, "total_tests": 0}
        result = runner.invoke(app, ["run"])
    assert result.exit_code == 1


def test_status_prints_last_run(aegis_project):
    with patch("cli.commands.status.AegisClient") as MockClient:
        mock = MockClient.return_value
        mock.get.return_value = [
            {"id": 5, "status": "COMPLETE", "profile": "production",
             "total_tests": 10, "completed_tests": 10,
             "started_at": "2026-05-20T06:00:00", "completed_at": "2026-05-20T06:00:15"}
        ]
        result = runner.invoke(app, ["status"])
    assert result.exit_code == 0
    assert "COMPLETE" in result.output
