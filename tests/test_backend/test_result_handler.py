"""Characterization tests for result_handler.

Pins the numpy-scalar sanitization (the np.int64 JSON fix) and the silent fall-back
behavior of send_to_dashboard when unconfigured.
"""

import numpy as np

from backend.core import result_handler


def test_sanitize_converts_numpy_int():
    out = result_handler._sanitize({"count": np.int64(5)})
    assert out == {"count": 5}
    assert isinstance(out["count"], int)


def test_sanitize_converts_numpy_float():
    out = result_handler._sanitize({"pct": np.float64(0.5)})
    assert out["pct"] == 0.5
    assert isinstance(out["pct"], float)


def test_sanitize_passes_through_native_types():
    payload = {"a": 1, "b": "s", "c": [1, 2], "d": None, "e": True}
    assert result_handler._sanitize(payload) == payload


def test_sanitize_stringifies_unknown_objects():
    class Weird:
        def __str__(self):
            return "weird"

    out = result_handler._sanitize({"x": Weird()})
    assert out == {"x": "weird"}


def test_send_to_dashboard_returns_false_when_unconfigured(monkeypatch):
    monkeypatch.setattr(result_handler, "_API_URL", "")
    monkeypatch.setattr(result_handler, "_API_KEY", "")
    assert result_handler.send_to_dashboard([], "2026-01-01T00:00:00") is False
