from backend.core.database_connector import DatabaseConnector


def run(connector: DatabaseConnector, test: dict) -> dict:
    table = test["table"]
    column = test["column"]
    threshold = test.get("threshold", 0.0)

    df = connector.execute_query(
        f"SELECT COUNT(*) AS total, "
        f"SUM(CASE WHEN {column} IS NULL THEN 1 ELSE 0 END) AS null_count "
        f"FROM {table}"
    )
    total = int(df["total"].iloc[0])
    null_count = int(df["null_count"].iloc[0])
    null_pct = null_count / total if total > 0 else 0.0

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
