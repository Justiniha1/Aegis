"""Characterization tests for the 8 builtin data-quality checks.

Purpose: lock the CURRENT observable behavior (result-dict shape, status, metrics,
messages, error branches) of every check before the Tier A dedup refactor extracts
a shared _common helper. These must stay green through that refactor.

Where a test pins behavior that the audit flagged as a bug (e.g. row_count's silent
all-rows fallback, custom_sql's eval), it is labelled so the later Tier C fix knows
to update it deliberately.
"""

from backend.tests.builtin import (
    null_check,
    duplicate_check,
    range_check,
    row_count,
    unique_check,
    schema_check,
    relationship_check,
    custom_sql,
)
from tests.test_backend.conftest import make_test


# Every check returns these top-level keys.
RESULT_KEYS = {"test_id", "name", "type", "status", "severity", "metrics", "message"}


# --------------------------------------------------------------------------- null_check
def test_null_check_missing_table_is_error(connector_factory):
    conn = connector_factory()
    r = null_check.run(conn, make_test(column="x"))
    assert r["status"] == "ERROR"
    assert r["message"] == "Missing required field: table"
    assert r["type"] == "null_check"
    assert r["metrics"] == {}
    assert set(r) == RESULT_KEYS


def test_null_check_missing_column_is_error(connector_factory):
    conn = connector_factory()
    r = null_check.run(conn, make_test(table="t"))
    assert r["status"] == "ERROR"
    assert r["message"] == "Missing required field: column"


def test_null_check_empty_table_is_skipped(connector_factory):
    conn = connector_factory("CREATE TABLE t (x INTEGER)")
    r = null_check.run(conn, make_test(table="t", column="x"))
    assert r["status"] == "SKIPPED"
    assert r["metrics"] == {"total_rows": 0}
    assert r["message"] == "Table 't' is empty — null check skipped"


def test_null_check_within_threshold_passes(connector_factory):
    conn = connector_factory(
        "CREATE TABLE t (x INTEGER)",
        "INSERT INTO t (x) VALUES (1), (2), (3), (4)",
    )
    r = null_check.run(conn, make_test(table="t", column="x", threshold=0.0))
    assert r["status"] == "PASSED"
    assert r["metrics"] == {
        "total_rows": 4,
        "null_count": 0,
        "null_percentage": 0.0,
        "threshold": 0.0,
    }


def test_null_check_exceeds_threshold_fails(connector_factory):
    conn = connector_factory(
        "CREATE TABLE t (x INTEGER)",
        "INSERT INTO t (x) VALUES (1), (NULL), (NULL), (4)",
    )
    r = null_check.run(conn, make_test(table="t", column="x", threshold=0.0, severity="HIGH"))
    assert r["status"] == "FAILED"
    assert r["severity"] == "HIGH"
    assert r["metrics"]["null_count"] == 2
    assert r["metrics"]["null_percentage"] == 0.5
    assert "exceeds threshold" in r["message"]


def test_null_check_default_severity_is_medium(connector_factory):
    conn = connector_factory("CREATE TABLE t (x INTEGER)", "INSERT INTO t (x) VALUES (1)")
    r = null_check.run(conn, make_test(table="t", column="x"))
    assert r["severity"] == "MEDIUM"


# ---------------------------------------------------------------------- duplicate_check
def test_duplicate_check_missing_table_is_error(connector_factory):
    conn = connector_factory()
    r = duplicate_check.run(conn, make_test(columns=["x"]))
    assert r["status"] == "ERROR"
    assert r["message"] == "Missing required field: table"


def test_duplicate_check_no_columns_is_error(connector_factory):
    conn = connector_factory("CREATE TABLE t (x INTEGER)")
    r = duplicate_check.run(conn, make_test(table="t"))
    assert r["status"] == "ERROR"
    assert r["message"] == "At least one column must be specified for duplicate_check"


def test_duplicate_check_within_max_allowed_passes(connector_factory):
    conn = connector_factory(
        "CREATE TABLE t (x INTEGER)",
        "INSERT INTO t (x) VALUES (1), (2), (3)",
    )
    r = duplicate_check.run(conn, make_test(table="t", columns=["x"]))
    assert r["status"] == "PASSED"
    assert r["metrics"]["duplicate_groups"] == 0
    assert r["metrics"]["columns_checked"] == ["x"]
    assert r["metrics"]["total_rows"] == 3


def test_duplicate_check_detects_duplicates(connector_factory):
    conn = connector_factory(
        "CREATE TABLE t (x INTEGER)",
        "INSERT INTO t (x) VALUES (1), (1), (2), (2), (3)",
    )
    r = duplicate_check.run(conn, make_test(table="t", columns=["x"]))
    assert r["status"] == "FAILED"
    assert r["metrics"]["duplicate_groups"] == 2


def test_duplicate_check_accepts_singular_column(connector_factory):
    conn = connector_factory(
        "CREATE TABLE t (x INTEGER)",
        "INSERT INTO t (x) VALUES (1), (1)",
    )
    r = duplicate_check.run(conn, make_test(table="t", column="x"))
    assert r["status"] == "FAILED"
    assert r["metrics"]["columns_checked"] == ["x"]


# -------------------------------------------------------------------------- range_check
def test_range_check_missing_column_is_error(connector_factory):
    conn = connector_factory("CREATE TABLE t (x INTEGER)")
    r = range_check.run(conn, make_test(table="t", min_value=0))
    assert r["status"] == "ERROR"
    assert r["message"] == "Missing required field: column"


def test_range_check_no_bounds_is_error(connector_factory):
    conn = connector_factory("CREATE TABLE t (x INTEGER)")
    r = range_check.run(conn, make_test(table="t", column="x"))
    assert r["status"] == "ERROR"
    assert r["message"] == "At least one of min_value or max_value must be specified"


def test_range_check_within_bounds_passes(connector_factory):
    conn = connector_factory(
        "CREATE TABLE t (x INTEGER)",
        "INSERT INTO t (x) VALUES (5), (6), (7)",
    )
    r = range_check.run(conn, make_test(table="t", column="x", min_value=0, max_value=10))
    assert r["status"] == "PASSED"
    assert r["metrics"]["outlier_count"] == 0


def test_range_check_counts_outliers(connector_factory):
    conn = connector_factory(
        "CREATE TABLE t (x INTEGER)",
        "INSERT INTO t (x) VALUES (-1), (5), (20)",
    )
    r = range_check.run(conn, make_test(table="t", column="x", min_value=0, max_value=10))
    assert r["status"] == "FAILED"
    assert r["metrics"]["outlier_count"] == 2
    assert r["metrics"]["min_value"] == 0
    assert r["metrics"]["max_value"] == 10


# ---------------------------------------------------------------------------- row_count
def test_row_count_missing_table_is_error(connector_factory):
    conn = connector_factory()
    r = row_count.run(conn, make_test(min_rows=1))
    assert r["status"] == "ERROR"
    assert r["message"] == "Missing required field: table"


def test_row_count_no_bounds_is_error(connector_factory):
    conn = connector_factory("CREATE TABLE t (x INTEGER)")
    r = row_count.run(conn, make_test(table="t"))
    assert r["status"] == "ERROR"
    assert r["message"] == "At least one of min_rows or max_rows must be specified"


def test_row_count_timeframe_requires_date_column(connector_factory):
    conn = connector_factory("CREATE TABLE t (x INTEGER)")
    r = row_count.run(conn, make_test(table="t", min_rows=1, timeframe="daily"))
    assert r["status"] == "ERROR"
    assert r["message"] == "date_column is required when timeframe is 'daily'"


def test_row_count_all_time_counts_all_rows(connector_factory):
    conn = connector_factory(
        "CREATE TABLE t (x INTEGER)",
        "INSERT INTO t (x) VALUES (1), (2), (3)",
    )
    r = row_count.run(conn, make_test(table="t", min_rows=1, max_rows=10))
    assert r["status"] == "PASSED"
    assert r["metrics"]["row_count"] == 3
    assert r["metrics"]["timeframe"] == "all_time"


def test_row_count_below_min_fails(connector_factory):
    conn = connector_factory(
        "CREATE TABLE t (x INTEGER)",
        "INSERT INTO t (x) VALUES (1)",
    )
    r = row_count.run(conn, make_test(table="t", min_rows=5))
    assert r["status"] == "FAILED"
    assert "min_rows" in r["message"]


# ------------------------------------------------------------------------- unique_check
def test_unique_check_no_columns_is_error(connector_factory):
    conn = connector_factory("CREATE TABLE t (x INTEGER)")
    r = unique_check.run(conn, make_test(table="t"))
    assert r["status"] == "ERROR"
    assert r["message"] == "At least one column must be specified for unique_check"


def test_unique_check_all_unique_passes(connector_factory):
    conn = connector_factory(
        "CREATE TABLE t (x INTEGER)",
        "INSERT INTO t (x) VALUES (1), (2), (3)",
    )
    r = unique_check.run(conn, make_test(table="t", columns=["x"]))
    assert r["status"] == "PASSED"
    assert r["metrics"]["duplicate_count"] == 0
    assert r["metrics"]["distinct_values"] == 3


def test_unique_check_detects_duplicates(connector_factory):
    conn = connector_factory(
        "CREATE TABLE t (x INTEGER)",
        "INSERT INTO t (x) VALUES (1), (1), (2)",
    )
    r = unique_check.run(conn, make_test(table="t", columns=["x"]))
    assert r["status"] == "FAILED"
    assert r["metrics"]["duplicate_count"] == 1


# ------------------------------------------------------------------------- schema_check
def test_schema_check_no_expected_columns_is_error(connector_factory):
    conn = connector_factory("CREATE TABLE t (x INTEGER)")
    r = schema_check.run(conn, make_test(table="t"))
    assert r["status"] == "ERROR"
    assert r["message"] == "expected_columns must be provided and non-empty"


def test_schema_check_matching_schema_passes(connector_factory):
    conn = connector_factory("CREATE TABLE t (id INTEGER, name TEXT)")
    r = schema_check.run(
        conn, make_test(table="t", expected_columns={"id": "integer", "name": "string"})
    )
    assert r["status"] == "PASSED"
    assert r["metrics"]["missing_columns"] == []
    assert r["metrics"]["type_mismatches"] == []


def test_schema_check_reports_missing_column(connector_factory):
    conn = connector_factory("CREATE TABLE t (id INTEGER)")
    r = schema_check.run(
        conn, make_test(table="t", expected_columns={"id": "integer", "missing": "string"})
    )
    assert r["status"] == "FAILED"
    assert r["metrics"]["missing_columns"] == ["missing"]


# ------------------------------------------------------------------- relationship_check
def test_relationship_check_missing_fields_is_error(connector_factory):
    conn = connector_factory()
    r = relationship_check.run(conn, make_test(source_table="a"))
    assert r["status"] == "ERROR"
    assert r["message"].startswith("Missing required field(s):")


def test_relationship_check_no_orphans_passes(connector_factory):
    conn = connector_factory(
        "CREATE TABLE parent (id INTEGER)",
        "CREATE TABLE child (parent_id INTEGER)",
        "INSERT INTO parent (id) VALUES (1), (2)",
        "INSERT INTO child (parent_id) VALUES (1), (2)",
    )
    r = relationship_check.run(
        conn,
        make_test(
            source_table="child", source_column="parent_id",
            target_table="parent", target_column="id",
        ),
    )
    assert r["status"] == "PASSED"
    assert r["metrics"]["orphan_count"] == 0


def test_relationship_check_detects_orphans(connector_factory):
    conn = connector_factory(
        "CREATE TABLE parent (id INTEGER)",
        "CREATE TABLE child (parent_id INTEGER)",
        "INSERT INTO parent (id) VALUES (1)",
        "INSERT INTO child (parent_id) VALUES (1), (99)",
    )
    r = relationship_check.run(
        conn,
        make_test(
            source_table="child", source_column="parent_id",
            target_table="parent", target_column="id",
        ),
    )
    assert r["status"] == "FAILED"
    assert r["metrics"]["orphan_count"] == 1


# ----------------------------------------------------------------------------- custom_sql
def test_custom_sql_no_query_is_error(connector_factory):
    conn = connector_factory()
    r = custom_sql.run(conn, make_test(assertion="result == 0"))
    assert r["status"] == "ERROR"
    assert r["message"] == "No query provided"


def test_custom_sql_no_assertion_is_error(connector_factory):
    conn = connector_factory()
    r = custom_sql.run(conn, make_test(query="SELECT 1"))
    assert r["status"] == "ERROR"
    assert r["message"] == "No assertion provided"


def test_custom_sql_assertion_passes(connector_factory):
    conn = connector_factory(
        "CREATE TABLE t (x INTEGER)",
        "INSERT INTO t (x) VALUES (1), (2), (3)",
    )
    r = custom_sql.run(
        conn, make_test(query="SELECT COUNT(*) AS cnt FROM t", assertion="result == 3")
    )
    assert r["status"] == "PASSED"
    # The query's result value is never transmitted (data-residency); pass/fail still computed.
    assert "result_value" not in r["metrics"]


def test_custom_sql_assertion_fails(connector_factory):
    conn = connector_factory(
        "CREATE TABLE t (x INTEGER)",
        "INSERT INTO t (x) VALUES (1)",
    )
    r = custom_sql.run(
        conn, make_test(query="SELECT COUNT(*) AS cnt FROM t", assertion="result == 99")
    )
    assert r["status"] == "FAILED"


def test_custom_sql_bad_assertion_is_error(connector_factory):
    conn = connector_factory(
        "CREATE TABLE t (x INTEGER)",
        "INSERT INTO t (x) VALUES (1)",
    )
    r = custom_sql.run(
        conn, make_test(query="SELECT COUNT(*) AS cnt FROM t", assertion="this is not python")
    )
    assert r["status"] == "ERROR"
    assert r["message"].startswith("Assertion evaluation failed:")
