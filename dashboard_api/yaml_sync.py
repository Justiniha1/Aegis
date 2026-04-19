"""
Bidirectional YAML ↔ Database sync for test definitions.

DB → YAML: export_tests_to_yaml() regenerates the YAML file from the database.
           Called after every create/update/delete in the tests router.

The YAML file preserves its existing `engine` and `settings` sections;
only the `tests` list is regenerated from the database.
"""

import os
from pathlib import Path

import yaml
from sqlalchemy.orm import Session

from dashboard_api import models

YAML_PATH = Path(os.getenv("DQF_YAML_PATH", "/app/config/test_definitions.yaml"))

# Fields stored as top-level YAML keys (not inside config)
_STANDARD_KEYS = {"name", "description", "type", "severity", "enabled", "tags", "profile"}


def _db_test_to_yaml_dict(test: models.TestDefinition) -> dict:
    """Convert a DB TestDefinition row back to the YAML dict format."""
    d: dict = {"name": test.name}
    if test.description:
        d["description"] = test.description
    d["type"] = test.type
    d["severity"] = test.severity
    if not test.enabled:
        d["enabled"] = False
    if test.tags:
        d["tags"] = list(test.tags)
    if test.profile and test.profile != "dev":
        d["profile"] = test.profile

    # Flatten config keys into the top-level dict (how the YAML format works)
    if test.config:
        for k, v in test.config.items():
            if k not in _STANDARD_KEYS:
                d[k] = v

    return d


def export_tests_to_yaml(db: Session, client_id: int, yaml_path: Path | None = None) -> None:
    """
    Regenerate the YAML test definitions file from the database.
    Preserves existing `engine` and `settings` sections.
    """
    path = yaml_path or YAML_PATH

    # Read existing YAML to preserve engine/settings
    existing: dict = {}
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                existing = yaml.safe_load(f) or {}
        except Exception:
            existing = {}

    # Query all tests for this client
    tests = (
        db.query(models.TestDefinition)
        .filter(models.TestDefinition.client_id == client_id)
        .order_by(models.TestDefinition.created_at.asc())
        .all()
    )

    # Build the output dict, preserving engine/settings
    output: dict = {}
    if "engine" in existing:
        output["engine"] = existing["engine"]
    if "settings" in existing:
        output["settings"] = existing["settings"]

    output["tests"] = [_db_test_to_yaml_dict(t) for t in tests]

    # Write atomically (write to temp, then rename)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".yaml.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("# ============================================================================\n")
        f.write("# DATA QUALITY FRAMEWORK - TEST DEFINITIONS\n")
        f.write("# ============================================================================\n")
        f.write("# Auto-generated from database. Manual edits will be synced on next engine run.\n")
        f.write("# ============================================================================\n\n")
        yaml.dump(output, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    tmp.replace(path)


def generate_yaml_string(db: Session, client_id: int) -> str:
    """
    Generate the YAML content as a string (for the frontend YAML editor).
    Same logic as export_tests_to_yaml but returns a string instead of writing to disk.
    """
    path = YAML_PATH

    # Read existing YAML to preserve engine/settings
    existing: dict = {}
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                existing = yaml.safe_load(f) or {}
        except Exception:
            existing = {}

    tests = (
        db.query(models.TestDefinition)
        .filter(models.TestDefinition.client_id == client_id)
        .order_by(models.TestDefinition.created_at.asc())
        .all()
    )

    output: dict = {}
    if "engine" in existing:
        output["engine"] = existing["engine"]
    if "settings" in existing:
        output["settings"] = existing["settings"]

    output["tests"] = [_db_test_to_yaml_dict(t) for t in tests]

    return yaml.dump(output, default_flow_style=False, sort_keys=False, allow_unicode=True)
