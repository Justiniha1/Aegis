# tests/test_demo_dag.py
"""DAG-integrity test for the demo DAG. Skipped if Airflow is not installed."""
import importlib.util
from pathlib import Path

import pytest

pytest.importorskip("airflow", reason="airflow not installed in this environment")

DAG_FILE = Path("deploy/airflow/dags/comet_demo_dag.py")


def _load_dag_module():
    spec = importlib.util.spec_from_file_location("comet_demo_dag", DAG_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_dag_file_exists():
    assert DAG_FILE.is_file(), f"missing {DAG_FILE}"


def test_dag_imports_and_has_expected_shape():
    module = _load_dag_module()
    dag = getattr(module, "dag", None)
    assert dag is not None, "module must expose a top-level `dag`"
    assert dag.dag_id == "comet_demo"
    # Manual trigger only — no schedule.
    assert dag.schedule_interval is None
    task_ids = set(dag.task_ids)
    assert "run_demo_quality_checks" in task_ids


def test_operator_targets_demo_profile():
    module = _load_dag_module()
    task = module.dag.get_task("run_demo_quality_checks")
    assert task.profile == "demo"
