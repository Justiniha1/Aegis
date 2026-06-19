import json
import shutil
from pathlib import Path

import pytest

from cli.dbt.artifacts import DbtArtifactsError, load_artifacts, resolve_target_dir

FIXTURES = Path(__file__).parent.parent / "fixtures" / "dbt"


def test_resolve_prefers_explicit_target_dir(monkeypatch):
    monkeypatch.setenv("DBT_TARGET_PATH", "/from/env")
    assert resolve_target_dir(target_dir="/explicit", project_dir="/proj") == Path("/explicit")


def test_resolve_uses_env_when_no_explicit(monkeypatch):
    monkeypatch.setenv("DBT_TARGET_PATH", "/from/env")
    assert resolve_target_dir(target_dir=None, project_dir="/proj") == Path("/from/env")


def test_resolve_uses_project_dir_then_default(monkeypatch):
    monkeypatch.delenv("DBT_TARGET_PATH", raising=False)
    assert resolve_target_dir(target_dir=None, project_dir="/proj") == Path("/proj/target")
    assert resolve_target_dir(target_dir=None, project_dir=None) == Path("target")


def test_load_artifacts_reads_both_files(tmp_path):
    shutil.copy(FIXTURES / "run_results.json", tmp_path / "run_results.json")
    shutil.copy(FIXTURES / "manifest.json", tmp_path / "manifest.json")
    run_results, manifest = load_artifacts(tmp_path)
    assert "results" in run_results
    assert "nodes" in manifest


def test_load_artifacts_missing_file_raises(tmp_path):
    with pytest.raises(DbtArtifactsError) as exc:
        load_artifacts(tmp_path)
    assert "dbt test" in str(exc.value)


def test_load_artifacts_bad_json_raises(tmp_path):
    (tmp_path / "manifest.json").write_text("{not json", encoding="utf-8")
    (tmp_path / "run_results.json").write_text("{}", encoding="utf-8")
    with pytest.raises(DbtArtifactsError):
        load_artifacts(tmp_path)
