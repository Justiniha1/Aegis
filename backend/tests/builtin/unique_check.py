from backend.core.database_connector import DatabaseConnector


def run(connector: DatabaseConnector, test: dict) -> dict:
    table = test["table"]
    raw_cols = test.get("columns") or [test.get("column")]
    columns = [c for c in raw_cols if c]

    cols_sql = ", ".join(columns)
    df = connector.execute_query(
        f"SELECT COUNT(*) AS total, COUNT(DISTINCT {cols_sql}) AS distinct_count "
        f"FROM {table}"
    )
    total = int(df["total"].iloc[0])
    distinct = int(df["distinct_count"].iloc[0])
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
