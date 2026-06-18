from sqlalchemy import inspect as sa_inspect

from backend.core.database_connector import DatabaseConnector
from backend.tests.builtin._common import InvalidIdentifier, error, result, safe_identifier

TYPE = "schema_check"

TYPE_MAP = {
    "integer": {"int", "bigint", "smallint"},
    "float": {"float", "double", "numeric", "decimal", "real"},
    "string": {"varchar", "text", "char", "clob", "nvarchar", "nchar"},
    "boolean": {"bool"},
    "date": {"date"},
    "datetime": {"datetime", "timestamp"},
}


def _type_matches(sa_type_str: str, expected: str) -> bool:
    sa_lower = sa_type_str.lower()
    aliases = TYPE_MAP.get(expected.lower(), {expected.lower()})
    return any(alias in sa_lower for alias in aliases)


def run(connector: DatabaseConnector, test: dict) -> dict:
    table = test.get("table", "").strip()
    if not table:
        return error(test, TYPE, "Missing required field: table")

    try:
        table = safe_identifier(table)
    except InvalidIdentifier as e:
        return error(test, TYPE, str(e))

    expected_columns = test.get("expected_columns") or {}
    if not expected_columns:
        return error(test, TYPE, "expected_columns must be provided and non-empty")
    if not isinstance(expected_columns, dict):
        return error(test, TYPE, "expected_columns must be a mapping of column_name: type")

    inspector = sa_inspect(connector.get_sqlalchemy_engine())
    try:
        actual_cols = {
            col["name"]: str(col["type"])
            for col in inspector.get_columns(table)
        }
    except Exception as e:
        return error(test, TYPE, f"Could not inspect table '{table}': {e}")

    missing = []
    type_mismatches = []

    for col_name, expected_type in expected_columns.items():
        if col_name not in actual_cols:
            missing.append(col_name)
        elif not _type_matches(actual_cols[col_name], expected_type):
            type_mismatches.append(
                f"{col_name}: expected {expected_type}, got {actual_cols[col_name]}"
            )

    passed = not missing and not type_mismatches
    issues = (
        [f"Missing columns: {missing}"] if missing else []
    ) + (
        [f"Type mismatches: {type_mismatches}"] if type_mismatches else []
    )

    # Data-residency: report only on the columns the client declared in expected_columns.
    # The full discovered column list (actual_cols) is intentionally NOT emitted — it would
    # disclose schema the client never asked to involve (e.g. an undeclared PII column).
    return result(
        test, TYPE,
        "PASSED" if passed else "FAILED",
        {
            "expected_columns": list(expected_columns.keys()),
            "missing_columns": missing,
            "type_mismatches": type_mismatches,
        },
        (
            f"{table} schema matches expectations"
            if passed else
            f"{table} schema issues: " + "; ".join(issues)
        ),
    )
