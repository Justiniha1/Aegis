from backend.core.database_connector import DatabaseConnector


def run(connector: DatabaseConnector, test: dict) -> dict:
    table = test["table"]
    min_rows = test.get("min_rows")
    max_rows = test.get("max_rows")
    timeframe = test.get("timeframe", "all_time")
    date_column = test.get("date_column")

    where_clause = ""
    if timeframe != "all_time" and date_column:
        if timeframe == "daily":
            where_clause = f"WHERE DATE({date_column}) = DATE('now')"
        elif timeframe == "weekly":
            where_clause = f"WHERE {date_column} >= DATE('now', '-7 days')"
        elif timeframe == "monthly":
            where_clause = f"WHERE {date_column} >= DATE('now', '-30 days')"

    df = connector.execute_query(
        f"SELECT COUNT(*) AS row_count FROM {table} {where_clause}"
    )
    count = int(df["row_count"].iloc[0])

    failures = []
    if min_rows is not None and count < min_rows:
        failures.append(f"count ({count}) < min_rows ({min_rows})")
    if max_rows is not None and count > max_rows:
        failures.append(f"count ({count}) > max_rows ({max_rows})")

    passed = len(failures) == 0
    return {
        "test_id": test["_test_id"],
        "name": test["name"],
        "type": "row_count",
        "status": "PASSED" if passed else "FAILED",
        "severity": test.get("severity", "MEDIUM"),
        "metrics": {
            "row_count": count,
            "min_rows": min_rows,
            "max_rows": max_rows,
            "timeframe": timeframe,
        },
        "message": (
            f"{table} has {count} rows — within expected range"
            if passed else
            f"{table} row count check failed: " + "; ".join(failures)
        ),
    }
