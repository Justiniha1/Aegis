from backend.core.database_connector import DatabaseConnector
from backend.tests.builtin._common import InvalidIdentifier, error, result, safe_identifier, to_int

TYPE = "null_check"


def run(connector: DatabaseConnector, test: dict) -> dict:
    table = test.get("table", "").strip()
    column = test.get("column", "").strip()

    if not table:
        return error(test, TYPE, "Missing required field: table")
    if not column:
        return error(test, TYPE, "Missing required field: column")

    try:
        table = safe_identifier(table)
        column = safe_identifier(column)
    except InvalidIdentifier as e:
        return error(test, TYPE, str(e))

    threshold = test.get("threshold", 0.0)

    df = connector.execute_query(
        f"SELECT COUNT(*) AS total, "
        f"SUM(CASE WHEN {column} IS NULL THEN 1 ELSE 0 END) AS null_count "
        f"FROM {table}"
    )
    total = to_int(df, "total")

    if total == 0:
        return result(
            test, TYPE, "SKIPPED",
            {"total_rows": 0},
            f"Table '{table}' is empty — null check skipped",
        )

    null_count = to_int(df, "null_count")
    null_pct = null_count / total
    passed = null_pct <= threshold
    return result(
        test, TYPE,
        "PASSED" if passed else "FAILED",
        {
            "total_rows": total,
            "null_count": null_count,
            "null_percentage": round(null_pct, 4),
            "threshold": threshold,
        },
        (
            f"Null percentage ({null_pct:.2%}) is within threshold ({threshold:.2%})"
            if passed else
            f"Null percentage ({null_pct:.2%}) exceeds threshold ({threshold:.2%}) "
            f"— {null_count} null(s) in {table}.{column}"
        ),
    )
