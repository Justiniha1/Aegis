"""Characterization tests for config_loader helpers.

Pins behavior of the pure helpers (_name_to_id, _deduplicate_test_ids, build_engine_test,
_resolve_env_vars) that both load paths depend on, before any refactor touches them.
"""

import os

from backend.core.config_loader import (
    TestDefinition as _TestDefinition,
    _name_to_id,
    _deduplicate_test_ids,
    _resolve_env_vars,
    build_engine_test,
)


def _td(test_id: str) -> "_TestDefinition":
    return _TestDefinition(
        name=test_id, test_id=test_id, type="null_check", profile="dev",
        severity="MEDIUM", enabled=True, tags=[], raw={},
    )


def test_name_to_id_normalizes():
    assert _name_to_id("Customer Email Null Check") == "customer_email_null_check"
    assert _name_to_id("  Weird!!Name  ") == "weird_name"
    assert _name_to_id("already_ok") == "already_ok"


def test_deduplicate_appends_numeric_suffixes():
    out = _deduplicate_test_ids([_td("a"), _td("a"), _td("a")])
    assert [t.test_id for t in out] == ["a", "a_2", "a_3"]


def test_deduplicate_skips_already_taken_suffix():
    # 'a', then 'a' (->a_2), then a literal 'a_2' must not collide.
    out = _deduplicate_test_ids([_td("a"), _td("a"), _td("a_2")])
    ids = [t.test_id for t in out]
    assert ids[0] == "a"
    assert ids[1] == "a_2"
    assert ids[2] == "a_2_2"
    assert len(set(ids)) == 3


def test_build_engine_test_merges_config_into_raw():
    td = build_engine_test(
        name="My Check", type="null_check", severity="HIGH", profile="prod",
        enabled=True, tags=["t"], config={"table": "users", "column": "email"},
    )
    assert td.test_id == "my_check"
    assert td.raw["table"] == "users"
    assert td.raw["column"] == "email"
    assert td.raw["severity"] == "HIGH"
    assert td.raw["tags"] == ["t"]


def test_build_engine_test_handles_none_config_and_tags():
    td = build_engine_test(
        name="X", type="row_count", severity="LOW", profile="dev",
        enabled=False, tags=None, config=None,
    )
    assert td.tags == []
    assert td.raw["enabled"] is False


def test_resolve_env_vars_substitutes_set_vars(monkeypatch):
    monkeypatch.setenv("COMET_TEST_VAR", "secret")
    out = _resolve_env_vars({"password": "${COMET_TEST_VAR}", "host": "db"})
    assert out == {"password": "secret", "host": "db"}


def test_resolve_env_vars_leaves_unset_as_is(monkeypatch):
    monkeypatch.delenv("COMET_UNSET_VAR", raising=False)
    out = _resolve_env_vars({"password": "${COMET_UNSET_VAR}"})
    assert out == {"password": "${COMET_UNSET_VAR}"}


def test_resolve_env_vars_recurses_into_lists_and_dicts(monkeypatch):
    monkeypatch.setenv("COMET_V", "v")
    out = _resolve_env_vars({"a": ["${COMET_V}", {"b": "${COMET_V}"}]})
    assert out == {"a": ["v", {"b": "v"}]}
