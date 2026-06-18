"""Shared fixtures for backend engine characterization tests.

These tests use a real on-disk SQLite database (via the production DatabaseConnector)
rather than mocks, so they exercise the same code path the engine uses at runtime.
A temp-file DB (not :memory:) is required because each execute_query() opens its own
connection, and separate :memory: connections would see separate empty databases.
"""

import pytest
from sqlalchemy import text

from backend.core.database_connector import DatabaseConnector


@pytest.fixture
def connector_factory(tmp_path):
    """Return a factory that builds a DatabaseConnector over a fresh temp SQLite file
    and runs any number of setup SQL statements to seed tables."""
    counter = {"n": 0}

    def _make(*setup_sql: str) -> DatabaseConnector:
        db_path = tmp_path / f"chk_{counter['n']}.db"
        counter["n"] += 1
        conn = DatabaseConnector({"connection_url": f"sqlite:///{db_path}"})
        if setup_sql:
            with conn.get_sqlalchemy_engine().begin() as c:
                for stmt in setup_sql:
                    c.execute(text(stmt))
        return conn

    return _make


def make_test(**kwargs) -> dict:
    """Build a test-definition dict shaped the way TestEngine passes it to check modules.

    Always carries the internal '_test_id' key the modules require.
    """
    base = {"_test_id": "t1", "name": "Sample Test"}
    base.update(kwargs)
    return base
