"""Data-residency tests: checks emit metadata/metrics only, never raw record values.

custom_sql redacts the query result by default; it is exposed only when the test sets
expose_value=True AND the value is numeric (i.e. a metric). A non-numeric result (a
record value such as an email) is never transmitted. schema_check reports only on the
client-declared expected columns and never enumerates the table's full column list.

The assertion text and declared column names are client-authored CONFIG (not data pulled
from the database), so they may appear in results — these tests guard the DATA path.
"""

from backend.tests.builtin import custom_sql, schema_check
from tests.test_backend.conftest import make_test


def test_custom_sql_never_transmits_result_value(connector_factory):
    # custom_sql emits only the pass/fail outcome; the query's result value is never
    # placed in metrics or echoed in the message.
    conn = connector_factory(
        "CREATE TABLE t (email TEXT)", "INSERT INTO t (email) VALUES ('secret@x.com')"
    )
    r = custom_sql.run(conn, make_test(query="SELECT email AS v FROM t", assertion="result != ''"))
    assert r["status"] == "PASSED"
    assert "result_value" not in r["metrics"]
    assert "secret@x.com" not in str(r["metrics"])
    assert "secret@x.com" not in r["message"]


def test_schema_check_does_not_enumerate_actual_columns(connector_factory):
    conn = connector_factory("CREATE TABLE t (id INTEGER, secret_ssn TEXT)")
    r = schema_check.run(conn, make_test(table="t", expected_columns={"id": "integer"}))
    assert r["status"] == "PASSED"
    assert "actual_columns" not in r["metrics"]
    # an undeclared column the client never asked about must not leak
    assert "secret_ssn" not in str(r["metrics"])
    assert "secret_ssn" not in r["message"]
