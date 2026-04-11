import os
import re 
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any


CONFIG_DIR = Path(__file__).parent.parent / "config"


@dataclass
class EngineConfig:
    engine: str
    default_profile: str
    default_severity: str
    alerts: dict


@dataclass
class TestDefinition:
    name: str
    test_id: str
    type: str
    profile: str
    severity: str
    enabled: bool
    tags: list
    raw: dict  # full original dict for test-type-specific fields


@dataclass
class DQFConfig:
    engine: EngineConfig
    connections: dict[str, dict]
    tests: list[TestDefinition]


def _resolve_env_vars(value: Any) -> Any:
    """Recursively substitute ${VAR} placeholders with environment variables."""
    if isinstance(value, str):
        def replace(m):
            var = m.group(1)
            return os.environ.get(var, m.group(0))  # leave as-is if not set
        return re.sub(r'\$\{(\w+)\}', replace, value)
    if isinstance(value, dict):
        return {k: _resolve_env_vars(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_env_vars(i) for i in value]
    return value


def _name_to_id(name: str) -> str:
    """Convert 'Customer Email Null Check' → 'customer_email_null_check'."""
    return re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')


def _load_yaml(path: Path) -> dict:
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


def load_config_from_api(api_url: str, api_key: str, connections: dict) -> DQFConfig:
    """
    Fetch test definitions from the Dashboard API instead of YAML.
    Falls back to load_config() if the API is unreachable.
    """
    import requests
    try:
        resp = requests.get(
            f"{api_url.rstrip('/')}/api/v1/tests",
            headers={"X-API-Key": api_key},
            timeout=10,
        )
        resp.raise_for_status()
    except Exception as e:
        raise RuntimeError(f"Could not fetch tests from API: {e}")

    raw_list = resp.json()
    engine_cfg = EngineConfig(
        engine="simple",
        default_profile="dev",
        default_severity="MEDIUM",
        alerts={},
    )

    tests = []
    for t in raw_list:
        if not t.get("enabled", True):
            continue
        # Reconstruct the 'raw' dict the test modules expect
        raw = {
            "name": t["name"],
            "type": t["type"],
            "severity": t["severity"],
            "profile": t["profile"],
            "enabled": t["enabled"],
            "tags": t.get("tags", []),
            **t.get("config", {}),
        }
        tests.append(TestDefinition(
            name=t["name"],
            test_id=_name_to_id(t["name"]),
            type=t["type"],
            profile=t["profile"],
            severity=t["severity"],
            enabled=t["enabled"],
            tags=t.get("tags", []),
            raw=raw,
        ))

    return DQFConfig(engine=engine_cfg, connections=connections, tests=tests)


def load_config() -> DQFConfig:
    # Support both singular and plural filename variants
    conn_candidates = [
        CONFIG_DIR / "database_connection.yaml",
        CONFIG_DIR / "database_connections.yaml",
    ]
    conn_path = next((p for p in conn_candidates if p.exists()), None)
    if conn_path is None:
        raise FileNotFoundError(
            f"No database connection config found. Expected one of: "
            + ", ".join(str(p) for p in conn_candidates)
        )

    tests_path = CONFIG_DIR / "test_definitions.yaml"
    if not tests_path.exists():
        raise FileNotFoundError(f"Test definitions not found at {tests_path}")

    raw_connections = _resolve_env_vars(_load_yaml(conn_path))
    raw_tests = _load_yaml(tests_path)

    settings = raw_tests.get("settings", {})
    default_profile = settings.get("default_profile", "dev")
    default_severity = settings.get("default_severity", "MEDIUM")

    engine_cfg = EngineConfig(
        engine=str(raw_tests.get("engine", "simple")).lower(),
        default_profile=default_profile,
        default_severity=default_severity,
        alerts=settings.get("alerts", {}),
    )

    tests = []
    for raw in raw_tests.get("tests", []):
        profile = raw.get("profile", default_profile)
        tests.append(TestDefinition(
            name=raw["name"],
            test_id=_name_to_id(raw["name"]),
            type=raw["type"],
            profile=profile,
            severity=raw.get("severity", default_severity),
            enabled=raw.get("enabled", True),
            tags=raw.get("tags", []),
            raw=raw,
        ))

    return DQFConfig(
        engine=engine_cfg,
        connections=raw_connections,
        tests=tests,
    )
