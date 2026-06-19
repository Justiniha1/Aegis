"""Pure translation of dbt artifacts into Comet result dicts. No I/O.

Joins dbt's run_results.json (outcomes) and manifest.json (metadata) on dbt's
stable `unique_id`. Only manifest nodes with resource_type == "test" are emitted;
model/seed/snapshot run-results and unknown unique_ids are skipped.
"""
from __future__ import annotations

# dbt generic test names that map to a dedicated Comet dbt_* type.
# Anything else (singular/custom/dbt_utils) falls into the generic dbt_test bucket.
_GENERIC_TYPES = {"not_null", "unique", "relationships", "accepted_values"}

# dbt status -> Comet status. A dbt "warn" still means the data violated the
# client's rule, so a health dashboard surfaces it as FAILED.
_STATUS_MAP = {
    "pass": "PASSED",
    "fail": "FAILED",
    "error": "ERROR",
    "skipped": "SKIPPED",
    "warn": "FAILED",
}

# dbt config severity -> Comet severity.
_SEVERITY_MAP = {
    "ERROR": "HIGH",
    "WARN": "MEDIUM",
}


def _map_type(node: dict) -> str:
    meta = node.get("test_metadata") or {}
    name = meta.get("name")
    if name in _GENERIC_TYPES:
        return f"dbt_{name}"
    return "dbt_test"


def _map_status(dbt_status) -> str:
    return _STATUS_MAP.get(str(dbt_status).lower(), "ERROR")


def _map_severity(node: dict) -> str:
    sev = (node.get("config") or {}).get("severity")
    return _SEVERITY_MAP.get(str(sev).upper(), "MEDIUM")


def _default_message(node: dict, result: dict) -> str:
    name = node.get("name") or result.get("unique_id") or "dbt test"
    status = str(result.get("status", "")).lower()
    if status == "pass":
        return f"dbt test {name} passed"
    failures = result.get("failures")
    if failures:
        return f"dbt test {name} {status} ({failures} failing rows)"
    return f"dbt test {name} {status}"


def translate(run_results: dict, manifest: dict) -> list[dict]:
    """Return Comet result dicts for every dbt test outcome in run_results."""
    nodes = manifest.get("nodes") or {}
    out: list[dict] = []
    for r in run_results.get("results") or []:
        uid = r.get("unique_id")
        node = nodes.get(uid)
        if not node or node.get("resource_type") != "test":
            continue
        out.append({
            "test_id": uid,
            "name": node.get("name") or uid,
            "type": _map_type(node),
            "status": _map_status(r.get("status")),
            "severity": _map_severity(node),
            "metrics": {
                "failures": r.get("failures"),
                "execution_time": r.get("execution_time"),
                "dbt_unique_id": uid,
            },
            "message": r.get("message") or _default_message(node, r),
        })
    return out
