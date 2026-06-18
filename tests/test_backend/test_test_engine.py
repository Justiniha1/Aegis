"""Characterization tests for TestEngine orchestration.

Focuses on the branches not covered elsewhere: unknown-profile SKIP, unimplemented
test-type ERROR, exception-to-ERROR conversion, and the fail-safe on_result callback
(a callback that raises must not stop subsequent tests).
"""

from backend.core.config_loader import (
    DQFConfig,
    EngineConfig,
    TestDefinition as _TestDefinition,
)
from backend.core.test_engine import TestEngine as _TestEngine


def _engine(tests, connections=None):
    cfg = DQFConfig(
        engine=EngineConfig(engine="simple", default_profile="dev",
                            default_severity="MEDIUM", alerts={}),
        connections=connections or {},
        tests=tests,
    )
    return _TestEngine(cfg)


def _td(name, type="null_check", profile="dev", enabled=True, raw=None):
    return _TestDefinition(
        name=name, test_id=name, type=type, profile=profile,
        severity="MEDIUM", enabled=enabled, tags=[], raw=raw or {},
    )


def test_unknown_profile_yields_skipped():
    eng = _engine([_td("a", profile="missing")])
    results = eng.run()
    assert len(results) == 1
    assert results[0]["status"] == "SKIPPED"
    assert "not found" in results[0]["message"]


def test_disabled_tests_are_not_run(tmp_path):
    conn = {"default": {"connection_url": f"sqlite:///{tmp_path / 'd.db'}"}}
    eng = _engine([_td("a", profile="default", enabled=False)], connections=conn)
    assert eng.run() == []


def test_unimplemented_type_yields_error(tmp_path):
    conn = {"default": {"connection_url": f"sqlite:///{tmp_path / 'd.db'}"}}
    eng = _engine([_td("a", type="does_not_exist", profile="default")], connections=conn)
    results = eng.run()
    assert results[0]["status"] == "ERROR"
    assert "not implemented yet" in results[0]["message"]


def test_check_exception_becomes_error(tmp_path):
    # Valid profile + valid type, but the table does not exist -> the check raises,
    # and the engine converts the exception into an ERROR result rather than crashing.
    conn = {"default": {"connection_url": f"sqlite:///{tmp_path / 'd.db'}"}}
    raw = {"table": "no_such_table", "column": "x"}
    eng = _engine([_td("a", type="null_check", profile="default", raw=raw)], connections=conn)
    results = eng.run()
    assert results[0]["status"] == "ERROR"


def test_on_result_callback_failure_does_not_stop_run():
    eng = _engine([_td("a", profile="missing"), _td("b", profile="missing")])

    seen = []

    def boom(result):
        seen.append(result["name"])
        raise RuntimeError("callback bug")

    results = eng.run(on_result=boom)
    # Both tests still ran and produced results despite the callback raising each time.
    assert [r["name"] for r in results] == ["a", "b"]
    assert seen == ["a", "b"]
