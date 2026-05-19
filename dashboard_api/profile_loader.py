"""Reads profile NAMES from backend/config/database_connection.yaml.

Security (per Phase 2 security_constraints): names only — never connection
strings or any sub-key credentials. The dashboard API runs in the customer
infra tier and MUST NOT expose engine-tier config secrets.
"""
import os
from pathlib import Path
from typing import Optional

import yaml

# Resolve order:
#   1. DQF_CONNECTION_YAML_PATH env var (Docker-compose can override).
#   2. ../backend/config/database_connection.yaml (relative to dashboard_api package).
_DEFAULT_PATH = Path(__file__).parent.parent / "backend" / "config" / "database_connection.yaml"


def _resolve_path() -> Path:
    env = os.getenv("DQF_CONNECTION_YAML_PATH", "")
    if env:
        return Path(env)
    return _DEFAULT_PATH


def load_profile_names() -> tuple[list[str], Optional[str]]:
    """Return (profile_names, default_profile_name).

    default_profile_name is the YAML's first top-level key (current convention
    per database_connection.yaml — `dev` is first). Returns ([], None) if the
    file is missing or unparseable — fail-safe so missing YAML never 500s the
    dashboard.
    """
    path = _resolve_path()
    if not path.exists():
        return [], None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError:
        return [], None
    if not isinstance(data, dict):
        return [], None
    names = [k for k in data.keys() if isinstance(k, str) and not k.startswith("_")]
    default = names[0] if names else None
    return names, default
