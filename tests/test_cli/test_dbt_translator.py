import json
from pathlib import Path

import pytest

from cli.dbt.translator import translate

FIXTURES = Path(__file__).parent.parent / "fixtures" / "dbt"


@pytest.fixture()
def artifacts():
    run_results = json.loads((FIXTURES / "run_results.json").read_text(encoding="utf-8"))
    manifest = json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))
    return run_results, manifest


def _by_id(results):
    return {r["test_id"]: r for r in results}


def test_excludes_models_and_orphans(artifacts):
    results = translate(*artifacts)
    # 6 test nodes resolve; the model run-result and the orphan (no manifest node) are dropped.
    assert len(results) == 6
    ids = {r["test_id"] for r in results}
    assert "model.demo.orders" not in ids
    assert "test.demo.orphan_no_manifest_node.ggg777" not in ids


def test_generic_types_are_prefixed(artifacts):
    r = _by_id(translate(*artifacts))
    assert r["test.demo.not_null_orders_id.aaa111"]["type"] == "dbt_not_null"
    assert r["test.demo.unique_orders_id.bbb222"]["type"] == "dbt_unique"
    assert r["test.demo.relationships_orders_customer_id.ccc333"]["type"] == "dbt_relationships"
    assert r["test.demo.accepted_values_orders_status.ddd444"]["type"] == "dbt_accepted_values"


def test_singular_test_falls_into_generic_bucket(artifacts):
    r = _by_id(translate(*artifacts))
    assert r["test.demo.assert_positive_amount.fff666"]["type"] == "dbt_test"


def test_status_mapping_including_warn_and_skipped(artifacts):
    r = _by_id(translate(*artifacts))
    assert r["test.demo.not_null_orders_id.aaa111"]["status"] == "PASSED"
    assert r["test.demo.unique_orders_id.bbb222"]["status"] == "FAILED"
    assert r["test.demo.relationships_orders_customer_id.ccc333"]["status"] == "ERROR"
    assert r["test.demo.accepted_values_orders_status.ddd444"]["status"] == "FAILED"  # warn -> FAILED
    assert r["test.demo.not_null_orders_total.eee555"]["status"] == "SKIPPED"


def test_severity_mapping(artifacts):
    r = _by_id(translate(*artifacts))
    assert r["test.demo.not_null_orders_id.aaa111"]["severity"] == "HIGH"   # ERROR -> HIGH
    assert r["test.demo.accepted_values_orders_status.ddd444"]["severity"] == "MEDIUM"  # WARN -> MEDIUM


def test_name_and_metrics_and_message(artifacts):
    r = _by_id(translate(*artifacts))
    unique = r["test.demo.unique_orders_id.bbb222"]
    assert unique["name"] == "unique_orders_id"
    assert unique["metrics"] == {
        "failures": 3,
        "execution_time": 0.08,
        "dbt_unique_id": "test.demo.unique_orders_id.bbb222",
    }
    assert unique["message"] == "Got 3 results, configured to fail if != 0"


def test_synthesized_message_when_dbt_message_absent(artifacts):
    r = _by_id(translate(*artifacts))
    # not_null_orders_id passed with message=null -> synthesized pass message
    assert r["test.demo.not_null_orders_id.aaa111"]["message"] == "dbt test not_null_orders_id passed"
