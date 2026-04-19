from backend.core.database_connector import DatabaseConnector


def run(connector: DatabaseConnector, test: dict) -> dict:
    table = test.get("table", "").strip()
    column = test.get("column", "").strip()

    if not table:
        return _error(test, "Missing required field: table")
    if not column:
        return _error(test, "Missing required field: column")

    threshold = test.get("threshold", 0.0)

    df = connector.execute_query(
        f"SELECT COUNT(*) AS total, "
        f"SUM(CASE WHEN {column} IS NULL THEN 1 ELSE 0 END) AS null_count "
        f"FROM {table}"
    )
    total = int(df["total"].iloc[0])
    null_count = int(df["null_count"].iloc[0])

    if total == 0:
        return {
            "test_id": test["_test_id"],
            "name": test["name"],
            "type": "null_check",
            "status": "SKIPPED",
            "severity": test.get("severity", "MEDIUM"),
            "metrics": {"total_rows": 0},
            "message": f"Table '{table}' is empty — null check skipped",
        }

    null_pct = null_count / total
    passed = null_pct <= threshold
    return {
        "test_id": test["_test_id"],
        "name": test["name"],
        "type": "null_check",
        "status": "PASSED" if passed else "FAILED",
        "severity": test.get("severity", "MEDIUM"),
        "metrics": {
            "total_rows": total,
            "null_count": null_count,
            "null_percentage": round(null_pct, 4),
            "threshold": threshold,
        },
        "message": (
            f"Null percentage ({null_pct:.2%}) is within threshold ({threshold:.2%})"
            if passed else
            f"Null percentage ({null_pct:.2%}) exceeds threshold ({threshold:.2%}) "
            f"— {null_count} null(s) in {table}.{column}"
        ),
    }


def _error(test: dict, msg: str) -> dict:
    return {
        "test_id": test["_test_id"],
        "name": test["name"],
        "type": "null_check",
        "status": "ERROR",
        "severity": test.get("severity", "MEDIUM"),
        "metrics": {},
        "message": msg,
    }
