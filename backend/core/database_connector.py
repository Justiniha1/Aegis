import re
from pathlib import Path
from urllib.parse import quote_plus

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

_ENV_VAR_PATTERN = re.compile(r"^\$\{([A-Z0-9_]+)\}$")


def build_connection_url(profile: dict) -> str:
    """Build a SQLAlchemy URL from a connection profile dict.

    Supported types:
      sqlite      -> sqlite:///path/to/db.sqlite
      postgresql  -> postgresql://user:pass@host:port/db
      mysql       -> mysql+pymysql://user:pass@host:port/db
      mssql       -> mssql+pyodbc://user:pass@host:port/db?driver=ODBC+Driver+17+for+SQL+Server
      snowflake   -> snowflake://user:pass@account/db?warehouse=WH&role=R
      other       -> uses 'connection_url' field directly
    """
    db_type = profile.get("type", "").lower().rstrip("/")

    # Loud-fail on any unresolved ${ENV_VAR} reference before anything else.
    # The error names only the variable — never its (literal) value.
    for value in profile.values():
        if isinstance(value, str):
            m = _ENV_VAR_PATTERN.match(value)
            if m:
                var_name = m.group(1)
                raise ValueError(
                    f"Required environment variable {var_name} is not set for this "
                    "connection profile — set it on the runner before scheduling."
                )

    # Direct URL override — advanced escape hatch for any database/driver.
    # NOTE (IN-02): the ${ENV} loud-fail above only matches a field whose ENTIRE value is
    # "${VAR}", so an env reference embedded inside a connection_url (e.g.
    # "postgresql://u:${PW}@h/db") is NOT auto-resolved or guarded, and a hardcoded password
    # here is accepted as-is. This is intentional — connection_url is for users who need full
    # control. For credential safety prefer the structured fields (type/host/username/password
    # with password set to a standalone "${VAR}"), which do get the unset-env loud-fail.
    if "connection_url" in profile:
        return profile["connection_url"]

    if db_type == "sqlite":
        raw_path = profile.get("path", ":memory:")
        # Resolve relative paths from the config directory
        p = Path(raw_path)
        if not p.is_absolute():
            config_dir = Path(__file__).parent.parent / "config"
            p = (config_dir / p).resolve()
        return f"sqlite:///{p}"

    user = quote_plus(str(profile.get("username", "")))
    password = quote_plus(str(profile.get("password", "")))
    host = profile.get("host", "localhost")
    database = profile.get("database", "")

    if db_type in ("postgresql", "postgres"):
        port = profile.get("port", 5432)
        return f"postgresql://{user}:{password}@{host}:{port}/{database}"

    if db_type == "mysql":
        port = profile.get("port", 3306)
        return f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"

    if db_type == "mssql":
        port = profile.get("port", 1433)
        driver = profile.get("driver", "ODBC Driver 17 for SQL Server").replace(" ", "+")
        return (
            f"mssql+pyodbc://{user}:{password}@{host}:{port}/{database}"
            f"?driver={driver}"
        )

    if db_type == "snowflake":
        account = str(profile.get("account", "")).strip()
        if account.endswith(".snowflakecomputing.com"):
            account = account[: -len(".snowflakecomputing.com")]
        params = []
        if profile.get("warehouse"):
            params.append(f"warehouse={quote_plus(str(profile['warehouse']))}")
        if profile.get("role"):
            params.append(f"role={quote_plus(str(profile['role']))}")
        query = ("?" + "&".join(params)) if params else ""
        return f"snowflake://{user}:{password}@{account}/{database}{query}"

    raise ValueError(
        f"Unsupported database type: '{db_type}'. "
        "Use one of: sqlite, postgresql, mysql, mssql, snowflake, or set 'connection_url' directly."
    )


class DatabaseConnector:
    def __init__(self, profile: dict):
        url = build_connection_url(profile)
        self._engine: Engine = create_engine(url)

    def execute_query(self, sql: str, params: dict | None = None) -> pd.DataFrame:
        """Run a read query and return a DataFrame.

        `params` are bound as SQL parameters (e.g. {"min_value": 0}) so caller-supplied
        VALUES never need string interpolation. Identifiers (table/column names) cannot
        be bound and must be validated by the caller before being formatted into `sql`.
        """
        with self._engine.connect() as conn:
            return pd.read_sql(text(sql), conn, params=params or {})

    def get_sqlalchemy_engine(self) -> Engine:
        return self._engine

    def test_connection(self) -> bool:
        try:
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
