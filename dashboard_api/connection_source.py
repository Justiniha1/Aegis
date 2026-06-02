"""Resolve connection profiles for the dashboard.

Precedence: the per-client uploaded YAML (via `aegis push`) if present, else the
on-disk engine config (DQF_CONNECTION_YAML_PATH). Profile NAMES are safe to
expose; full connection dicts are used only internally by the run executor.
Secrets remain ${ENV} in the YAML and are resolved from the environment at run time.
"""
import yaml as _yaml

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
    from backend.core.config_loader import _resolve_env_vars
    data = _resolve_env_vars(_parse(yaml_text))
    prof = data.get(name)
    return prof if isinstance(prof, dict) else None
