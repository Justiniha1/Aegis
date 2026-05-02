from backend.core.database_connector import DatabaseConnector


def run(connector: DatabaseConnector, test: dict) -> dict:
    table = test.get("table", "").strip()
    if not table:
        return _error(test, "Missing required field: table")

    # Support both 'column' (singular) and 'columns' (list)
    raw_cols = test.get("columns") or [test.get("column")]
    columns = [c for c in raw_cols if c]
    if not columns:
        return _error(test, "At least one column must be specified for unique_check")

    cols_sql = ", ".join(columns)

    df_total = connector.execute_query(
        f"SELECT COUNT(*) AS total FROM {table}"
    )
    total = int(df_total["total"].iloc[0])

    df_distinct = connector.execute_query(
        f"SELECT COUNT(*) AS distinct_count "
        f"FROM (SELECT DISTINCT {cols_sql} FROM {table}) sub"
    )
    distinct = int(df_distinct["distinct_count"].iloc[0])
    duplicates = total - distinct

    passed = duplicates == 0
    return {
        "test_id": test["_test_id"],
        "name": test["name"],
        "type": "unique_check",
        "status": "PASSED" if passed else "FAILED",
        "severity": test.get("severity", "MEDIUM"),
        "metrics": {
            "total_rows": total,
            "distinct_values": distinct,
            "duplicate_count": duplicates,
            "columns_checked": columns,
        },
        "message": (
            f"{cols_sql} is fully unique in {table}"
            if passed else
            f"{duplicates} duplicate(s) found — {cols_sql} is not unique in {table}"
        ),
    }


def _error(test: dict, msg: str) -> dict:
    return {
        "test_id": test["_test_id"],
        "name": test["name"],
        "type": "unique_check",
        "status": "ERROR",
        "severity": test.get("severity", "MEDIUM"),
        "metrics": {},
        "message": msg,
    }
