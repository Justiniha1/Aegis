"""Resolve connection profiles for the dashboard.

Precedence: the per-client uploaded YAML (via `aegis push`) if present, else the
on-disk engine config (DQF_CONNECTION_YAML_PATH). Profile NAMES are safe to
expose; full connection dicts are used only internally by the run executor.
Secrets remain ${ENV} in the YAML and are resolved from the environment at run time.
"""
import yaml as _yaml

from backend.core.config_loader import _resolve_env_vars
from dashboard_api import models
from dashboard_api.profile_loader import _resolve_path


def get_yaml_text(db, client_id: int) -> str:
    row = (
        db.query(models.ConnectionConfig)
        .filter(models.ConnectionConfig.client_id == client_id)
        .first()
    )
    if row and row.yaml_text:
        return row.yaml_text
    path = _resolve_path()
    try:
        return path.read_text(encoding="utf-8") if path.exists() else ""
    except OSError:
        return ""


def _parse(yaml_text: str) -> dict:
    try:
        data = _yaml.safe_load(yaml_text) or {}
    except _yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def parse_error(yaml_text: str) -> str | None:
    """Return a short error message if yaml_text is present but not valid YAML, else None.

    Lets callers distinguish 'profile not found' (empty/valid config without the profile)
    from 'connection config is corrupt' (unparseable YAML). The message is intentionally
    generic and never echoes file contents, so no secrets can leak.
    """
    if not yaml_text or not yaml_text.strip():
        return None
    try:
        _yaml.safe_load(yaml_text)
    except _yaml.YAMLError:
        return "connection config is not valid YAML"
    return None


def profile_names(yaml_text: str):
    """Return (names, default_name). A profile is a top-level mapping not starting with '_'."""
    data = _parse(yaml_text)
    names = [
        k for k, v in data.items()
        if isinstance(k, str) and not k.startswith("_") and isinstance(v, dict)
    ]
    return names, (names[0] if names else None)


def resolve_profile(yaml_text: str, name: str):
    """Return the env-resolved connection dict for `name`, or None."""
    data = _resolve_env_vars(_parse(yaml_text))
    prof = data.get(name)
    return prof if isinstance(prof, dict) else None


# ---------------------------------------------------------------------------
# Capability helpers — Pattern 3: derive from UNRESOLVED type, never secrets
# ---------------------------------------------------------------------------

_WEBSITE_SCHEDULABLE_TYPES = {"postgresql", "postgres", "mysql", "mssql", "snowflake"}


def profile_types(yaml_text: str) -> dict:
    """Return a mapping of profile name -> db type string (lowercased, unresolved).

    Uses _parse only — no ${ENV} resolution — so secrets are never read.
    Internal profiles starting with '_' are excluded (same rule as profile_names).
    """
    data = _parse(yaml_text)
    return {
        k: str(v.get("type", "")).lower()
        for k, v in data.items()
        if isinstance(k, str) and not k.startswith("_") and isinstance(v, dict)
    }


def is_website_schedulable(db_type: str) -> bool:
    """Return True if the DB type is reachable by the hosted runner (cloud DBs only).

    Derived from the UNRESOLVED YAML type label — never from resolved credentials.
    """
    return db_type.lower().rstrip("/") in _WEBSITE_SCHEDULABLE_TYPES
