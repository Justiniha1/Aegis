from sqlalchemy import inspect as sa_inspect

from backend.core.database_connector import DatabaseConnector

# Map of YAML type names → sets of SQLAlchemy type name substrings
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
    table = test["table"]
    expected_columns: dict = test.get("expected_columns", {})

    inspector = sa_inspect(connector.get_sqlalchemy_engine())
    try:
        actual_cols = {
            col["name"]: str(col["type"])
            for col in inspector.get_columns(table)
        }
    except Exception as e:
        return {
            "test_id": test["_test_id"],
            "name": test["name"],
            "type": "schema_check",
            "status": "ERROR",
            "severity": test.get("severity", "MEDIUM"),
            "metrics": {},
            "message": f"Could not inspect table '{table}': {e}",
        }

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

    return {
        "test_id": test["_test_id"],
        "name": test["name"],
        "type": "schema_check",
        "status": "PASSED" if passed else "FAILED",
        "severity": test.get("severity", "MEDIUM"),
        "metrics": {
            "expected_columns": list(expected_columns.keys()),
            "actual_columns": list(actual_cols.keys()),
            "missing_columns": missing,
            "type_mismatches": type_mismatches,
        },
        "message": (
            f"{table} schema matches expectations"
            if passed else
            f"{table} schema issues: " + "; ".join(issues)
        ),
    }
