"""Security tests for the builtin checks (SQL identifier injection + custom_sql eval).

These are written red-first: against the pre-fix code an injected identifier is
interpolated straight into SQL (raising or executing), and custom_sql's eval() will
happily evaluate attribute-access expressions. After the fix, injected identifiers are
rejected with a clean ERROR result and the assertion evaluator refuses anything beyond
comparisons/boolean/arithmetic on the provided names.
"""

from backend.tests.builtin import (
    null_check,
    duplicate_check,
    range_check,
    unique_check,
    relationship_check,
    row_count,
    custom_sql,
)
from tests.test_backend.conftest import make_test


INJECTION = "x; DROP TABLE t; --"
INJECTION_TABLE = "t WHERE 1=1; --"


def test_null_check_rejects_injected_column(connector_factory):
    conn = connector_factory("CREATE TABLE t (x INTEGER)", "INSERT INTO t (x) VALUES (1)")
    r = null_check.run(conn, make_test(table="t", column=INJECTION))
    assert r["status"] == "ERROR"
    assert "Invalid identifier" in r["message"]


def test_null_check_rejects_injected_table(connector_factory):
    conn = connector_factory("CREATE TABLE t (x INTEGER)", "INSERT INTO t (x) VALUES (1)")
    r = null_check.run(conn, make_test(table=INJECTION_TABLE, column="x"))
    assert r["status"] == "ERROR"
    assert "Invalid identifier" in r["message"]


def test_range_check_rejects_injected_column(connector_factory):
    conn = connector_factory("CREATE TABLE t (x INTEGER)", "INSERT INTO t (x) VALUES (1)")
    r = range_check.run(conn, make_test(table="t", column=INJECTION, min_value=0))
    assert r["status"] == "ERROR"
    assert "Invalid identifier" in r["message"]


def test_duplicate_check_rejects_injected_column(connector_factory):
    conn = connector_factory("CREATE TABLE t (x INTEGER)", "INSERT INTO t (x) VALUES (1)")
    r = duplicate_check.run(conn, make_test(table="t", columns=["x", INJECTION]))
    assert r["status"] == "ERROR"
    assert "Invalid identifier" in r["message"]


def test_unique_check_rejects_injected_column(connector_factory):
    conn = connector_factory("CREATE TABLE t (x INTEGER)", "INSERT INTO t (x) VALUES (1)")
    r = unique_check.run(conn, make_test(table="t", columns=[INJECTION]))
    assert r["status"] == "ERROR"
    assert "Invalid identifier" in r["message"]


def test_relationship_check_rejects_injected_identifier(connector_factory):
    conn = connector_factory(
        "CREATE TABLE parent (id INTEGER)",
        "CREATE TABLE child (parent_id INTEGER)",
    )
    r = relationship_check.run(
        conn,
        make_test(
            source_table="child", source_column=INJECTION,
            target_table="parent", target_column="id",
        ),
    )
    assert r["status"] == "ERROR"
    assert "Invalid identifier" in r["message"]


def test_row_count_rejects_injected_date_column(connector_factory):
    conn = connector_factory("CREATE TABLE t (x INTEGER, d TEXT)")
    r = row_count.run(
        conn, make_test(table="t", min_rows=1, timeframe="daily", date_column=INJECTION)
    )
    assert r["status"] == "ERROR"
    assert "Invalid identifier" in r["message"]


def test_qualified_identifier_is_allowed(connector_factory):
    # schema.table style identifiers must still be accepted (no regression).
    conn = connector_factory("CREATE TABLE t (x INTEGER)", "INSERT INTO t (x) VALUES (1)")
    r = null_check.run(conn, make_test(table="main.t", column="x"))
    assert r["status"] in ("PASSED", "FAILED")  # executed successfully against main.t


def test_custom_sql_blocks_attribute_access(connector_factory):
    # eval() would evaluate `result.__class__` to a truthy class object -> PASSED.
    # The safe evaluator must reject attribute access -> ERROR.
    conn = connector_factory("CREATE TABLE t (x INTEGER)", "INSERT INTO t (x) VALUES (1)")
    r = custom_sql.run(
        conn,
        make_test(query="SELECT COUNT(*) AS cnt FROM t", assertion="result.__class__"),
    )
    assert r["status"] == "ERROR"
    assert r["message"].startswith("Assertion evaluation failed:")


def test_custom_sql_blocks_function_calls(connector_factory):
    conn = connector_factory("CREATE TABLE t (x INTEGER)", "INSERT INTO t (x) VALUES (1)")
    r = custom_sql.run(
        conn,
        make_test(query="SELECT COUNT(*) AS cnt FROM t", assertion="len(str(result)) > 0"),
    )
    assert r["status"] == "ERROR"


def test_custom_sql_allows_chained_and_boolean_comparisons(connector_factory):
    conn = connector_factory("CREATE TABLE t (x INTEGER)", "INSERT INTO t (x) VALUES (1), (2), (3)")
    r = custom_sql.run(
        conn,
        make_test(query="SELECT COUNT(*) AS cnt FROM t", assertion="0 < result and result <= 3"),
    )
    assert r["status"] == "PASSED"
