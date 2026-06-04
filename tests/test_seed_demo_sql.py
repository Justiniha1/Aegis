# tests/test_seed_demo_sql.py
"""Static validation of the demo seed SQL. No live DB required."""
from pathlib import Path

import pytest

SEED = Path("deploy/demo/db/seed_demo.sql")


def _sql() -> str:
    return SEED.read_text(encoding="utf-8")


def test_seed_file_exists():
    assert SEED.is_file(), f"missing {SEED}"


def test_seed_is_idempotent_shaped():
    sql = _sql().lower()
    # Idempotent reset: must drop before create so re-running resets cleanly.
    assert "drop table if exists orders" in sql
    assert "drop table if exists customers" in sql
    assert "create table customers" in sql
    assert "create table orders" in sql


def test_seed_inserts_enough_rows_to_pass_checks():
    sql = _sql().lower()
    # Demo row_count check requires >= 1 customer; we seed many. Sanity: at least
    # 1 customer insert statement and 1 order insert statement exist.
    assert sql.count("into customers") >= 1
    assert sql.count("into orders") >= 1
    # Foreign-key column present so the relationship_check has something to validate.
    assert "customer_id" in sql
