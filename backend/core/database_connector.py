from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def build_connection_url(profile: dict) -> str:
    """Build a SQLAlchemy URL from a connection profile dict.

    Supported types:
      sqlite      → sqlite:///path/to/db.sqlite
      postgresql  → postgresql://user:pass@host:port/db
      mysql       → mysql+pymysql://user:pass@host:port/db
      mssql       → mssql+pyodbc://user:pass@host:port/db?driver=ODBC+Driver+17+for+SQL+Server
      other       → uses 'connection_url' field directly
    """
    db_type = profile.get("type", "").lower().rstrip("/")

    # Direct URL override — any database
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

    user = profile.get("username", "")
    password = profile.get("password", "")
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

    raise ValueError(
        f"Unsupported database type: '{db_type}'. "
        "Use one of: sqlite, postgresql, mysql, mssql, or set 'connection_url' directly."
    )


class DatabaseConnector:
    def __init__(self, profile: dict):
        url = build_connection_url(profile)
        self._engine: Engine = create_engine(url)

    def execute_query(self, sql: str) -> pd.DataFrame:
        with self._engine.connect() as conn:
            return pd.read_sql(text(sql), conn)

    def get_sqlalchemy_engine(self) -> Engine:
        return self._engine

    def test_connection(self) -> bool:
        try:
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
