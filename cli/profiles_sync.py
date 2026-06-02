"""Parse local YAML profiles into dashboard API payloads, and back.

Secret model: the env var NAME is non-secret and travels; the env var VALUE is
resolved locally and only sent when present (no-clobber). SQLite profiles carry
no secret.
"""
import os
import re

_TYPE_MAP = {"postgres": "postgresql", "postgresql": "postgresql",
             "mysql": "mysql", "sqlite": "sqlite", "mssql": "mssql"}

_ENV_REF = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")


def default_secret_env(name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9]", "_", name).upper()
    return f"AEGIS_{safe}_PASSWORD"


def env_ref_or_none(value):
    """If value is exactly '${VAR}', return VAR; else None."""
    if not isinstance(value, str):
        return None
    m = _ENV_REF.match(value.strip())
    return m.group(1) if m else None


def parse_yaml_profile(name: str, profile: dict) -> dict:
    """Normalize one YAML profile dict into a structured intermediate.

    Keys: db_type, host, port, database, username, sqlite_path, secret_env,
    and optionally _literal_secret (when the YAML embedded a non-${} password).
    """
    db_type = _TYPE_MAP.get(str(profile.get("type", "")).lower(), str(profile.get("type", "")).lower())
    out = {"db_type": db_type, "host": None, "port": None, "database": None,
           "username": None, "sqlite_path": None, "secret_env": None}

    if db_type == "sqlite":
        out["sqlite_path"] = profile.get("path")
        return out

    out["host"] = profile.get("host")
    out["port"] = profile.get("port")
    out["database"] = profile.get("database")
    out["username"] = profile.get("username")

    raw_pw = profile.get("password")
    ref = env_ref_or_none(raw_pw)
    if ref:
        out["secret_env"] = ref
    else:
        out["secret_env"] = default_secret_env(name)
        if raw_pw:                              # literal password present in YAML
            out["_literal_secret"] = raw_pw
    return out


def profile_to_payload(name: str, parsed: dict):
    """Build the POST body for /api/v1/profiles. Returns (payload, warning_or_None).

    Secret value is taken from the literal YAML password if present, else resolved
    from os.environ[secret_env]. If neither is available, secret_value is omitted
    (the dashboard keeps any existing secret) and a warning string is returned.
    """
    payload = {
        "name": name,
        "db_type": parsed["db_type"],
        "host": parsed["host"],
        "port": parsed["port"],
        "database": parsed["database"],
        "username": parsed["username"],
        "sqlite_path": parsed["sqlite_path"],
        "secret_env": parsed["secret_env"],
    }
    warning = None
    if parsed["db_type"] != "sqlite":
        secret = parsed.get("_literal_secret")
        if secret is None and parsed["secret_env"]:
            secret = os.environ.get(parsed["secret_env"])
        if secret is not None:
            payload["secret_value"] = secret
        else:
            warning = (f"{parsed['secret_env']} not set - kept existing dashboard secret "
                       f"for '{name}'")
    return payload, warning
