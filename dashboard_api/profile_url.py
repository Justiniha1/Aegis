"""Reconstruct a SQLAlchemy connection URL from a stored ConnectionProfile + its secret.

Single source of URL assembly so the run executor and tests agree. The secret VALUE
is never stored in the URL at rest — it is supplied at call time (decrypted from
secret_encrypted, or resolved from the environment).
"""
from urllib.parse import quote_plus

_DRIVERS = {
    "postgresql": "postgresql",
    "postgres": "postgresql",
    "mysql": "mysql+pymysql",
    "mssql": "mssql+pyodbc",
}


def build_connection_url(profile, secret_value: str | None) -> str:
    db_type = (profile.db_type or "").lower()

    if db_type == "sqlite":
        path = profile.sqlite_path or ""
        return f"sqlite:///{path}"

    driver = _DRIVERS.get(db_type)
    if driver is None:
        raise ValueError(f"Unsupported db_type '{profile.db_type}' for URL assembly")

    if secret_value is None:
        raise ValueError(f"Profile '{getattr(profile, 'name', '?')}' ({db_type}) requires a secret")

    user = quote_plus(profile.username or "")
    pw = quote_plus(secret_value)
    host = profile.host or "localhost"
    port = profile.port
    database = profile.database or ""
    hostpart = f"{host}:{port}" if port else host
    return f"{driver}://{user}:{pw}@{hostpart}/{database}"
