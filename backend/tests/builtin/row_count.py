from backend.core.database_connector import DatabaseConnector

#look into oracle
def _date_where(dialect: str, date_column: str, timeframe: str) -> str:
    if timeframe == "daily":
        if dialect == "sqlite":
            return f"WHERE DATE({date_column}) = DATE('now')"
        elif dialect in ("postgresql", "postgres"):
            return f"WHERE {date_column}::date = CURRENT_DATE"
        elif dialect == "mysql":
            return f"WHERE DATE({date_column}) = CURDATE()"
        elif dialect == "mssql":
            return f"WHERE CAST({date_column} AS DATE) = CAST(GETDATE() AS DATE)"
    elif timeframe == "weekly":
        if dialect == "sqlite":
            return f"WHERE {date_column} >= DATE('now', '-7 days')"
        elif dialect in ("postgresql", "postgres"):
            return f"WHERE {date_column} >= CURRENT_DATE - INTERVAL '7 days'"
        elif dialect == "mysql":
            return f"WHERE {date_column} >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)"
        elif dialect == "mssql":
            return f"WHERE {date_column} >= DATEADD(day, -7, CAST(GETDATE() AS DATE))"
    elif timeframe == "monthly":
        if dialect == "sqlite":
            return f"WHERE {date_column} >= DATE('now', '-30 days')"
        elif dialect in ("postgresql", "postgres"):
            return f"WHERE {date_column} >= CURRENT_DATE - INTERVAL '30 days'"
        elif dialect == "mysql":
            return f"WHERE {date_column} >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)"
        elif dialect == "mssql":
            return f"WHERE {date_column} >= DATEADD(day, -30, CAST(GETDATE() AS DATE))"
    return ""


def run(connector: DatabaseConnector, test: dict) -> dict:
    table = test["table"]
    min_rows = test.get("min_rows")
    max_rows = test.get("max_rows")
    timeframe = test.get("timeframe", "all_time")
    date_column = test.get("date_column")

    where_clause = ""
    if timeframe != "all_time" and date_column:
        dialect = connector.get_sqlalchemy_engine().dialect.name
        where_clause = _date_where(dialect, date_column, timeframe)

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
