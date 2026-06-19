import shutil
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from cli.cli import app

runner = CliRunner()
FIXTURES = Path(__file__).parent.parent / "fixtures" / "dbt"


@pytest.fixture()
def dbt_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("COMET_API_KEY", "test-key")
    target = tmp_path / "target"
    target.mkdir()
    shutil.copy(FIXTURES / "run_results.json", target / "run_results.json")
    shutil.copy(FIXTURES / "manifest.json", target / "manifest.json")
    return tmp_path


def test_publish_posts_results_under_dbt_profile(dbt_project):
    with patch("cli.commands.dbt_cmd.CometClient") as MockClient:
        mock = MockClient.return_value
        mock.post.return_value = {"stored": 6, "run_id": 99}
        result = runner.invoke(app, ["dbt", "publish"])
    assert result.exit_code == 0, result.output
    assert "Published 6" in result.output
    # Verify the batch shape posted to the ingest endpoint.
    path, kwargs = mock.post.call_args[0][0], mock.post.call_args[1]
    assert path == "/api/v1/results"
    payload = kwargs["json"]
    assert payload["run_profile"] == "dbt"
    assert len(payload["results"]) == 6
    assert "run_timestamp" in payload


def test_publish_missing_artifacts_errors(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("COMET_API_KEY", "test-key")
    with patch("cli.commands.dbt_cmd.CometClient") as MockClient:
        result = runner.invoke(app, ["dbt", "publish"])
        MockClient.return_value.post.assert_not_called()
    assert result.exit_code == 1
    assert "Couldn't find dbt artifacts" in result.output


def test_publish_respects_target_dir_flag(dbt_project, monkeypatch):
    # Move artifacts to a custom dir; default ./target still exists but we point elsewhere.
    custom = dbt_project / "custom_target"
    custom.mkdir()
    shutil.copy(FIXTURES / "run_results.json", custom / "run_results.json")
    shutil.copy(FIXTURES / "manifest.json", custom / "manifest.json")
    with patch("cli.commands.dbt_cmd.CometClient") as MockClient:
        MockClient.return_value.post.return_value = {"stored": 6}
        result = runner.invoke(app, ["dbt", "publish", "--target-dir", str(custom)])
    assert result.exit_code == 0, result.output
    assert "Published 6" in result.output
