from backend.core.database_connector import DatabaseConnector
from backend.tests.builtin._common import InvalidIdentifier, error, result, safe_identifier, to_int

TYPE = "unique_check"


def run(connector: DatabaseConnector, test: dict) -> dict:
    table = test.get("table", "").strip()
    if not table:
        return error(test, TYPE, "Missing required field: table")

    # Support both 'column' (singular) and 'columns' (list)
    raw_cols = test.get("columns") or [test.get("column")]
    columns = [c for c in raw_cols if c]
    if not columns:
        return error(test, TYPE, "At least one column must be specified for unique_check")

    try:
        table = safe_identifier(table)
        columns = [safe_identifier(c) for c in columns]
    except InvalidIdentifier as e:
        return error(test, TYPE, str(e))

    cols_sql = ", ".join(columns)

    df_total = connector.execute_query(f"SELECT COUNT(*) AS total FROM {table}")
    total = to_int(df_total, "total")

    df_distinct = connector.execute_query(
        f"SELECT COUNT(*) AS distinct_count "
        f"FROM (SELECT DISTINCT {cols_sql} FROM {table}) sub"
    )
    distinct = to_int(df_distinct, "distinct_count")
    duplicates = total - distinct

    passed = duplicates == 0
    return result(
        test, TYPE,
        "PASSED" if passed else "FAILED",
        {
            "total_rows": total,
            "distinct_values": distinct,
            "duplicate_count": duplicates,
            "columns_checked": columns,
        },
        (
            f"{cols_sql} is fully unique in {table}"
            if passed else
            f"{duplicates} duplicate(s) found — {cols_sql} is not unique in {table}"
        ),
    )
