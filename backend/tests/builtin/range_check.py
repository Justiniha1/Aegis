from backend.core.database_connector import DatabaseConnector


def run(connector: DatabaseConnector, test: dict) -> dict:
    table = test["table"]
    column = test["column"]
    min_value = test.get("min_value")
    max_value = test.get("max_value")
    max_outliers = test.get("max_outliers", 0)

    conditions = []
    if min_value is not None:
        conditions.append(f"{column} < {min_value}")
    if max_value is not None:
        conditions.append(f"{column} > {max_value}")

    where = " OR ".join(conditions) if conditions else "1=0"

    df = connector.execute_query(
        f"SELECT COUNT(*) AS outlier_count FROM {table} WHERE {where}"
    )
    df_total = connector.execute_query(f"SELECT COUNT(*) AS total FROM {table}")
    outlier_count = int(df["outlier_count"].iloc[0])
    total = int(df_total["total"].iloc[0])

    passed = outlier_count <= max_outliers
    range_desc = f"[{min_value}, {max_value}]"
    return {
        "test_id": test["_test_id"],
        "name": test["name"],
        "type": "range_check",
        "status": "PASSED" if passed else "FAILED",
        "severity": test.get("severity", "MEDIUM"),
        "metrics": {
            "total_rows": total,
            "outlier_count": outlier_count,
            "max_outliers_allowed": max_outliers,
            "min_value": min_value,
            "max_value": max_value,
        },
        "message": (
            f"{table}.{column} has {outlier_count} outlier(s) outside {range_desc} "
            f"— within allowed limit ({max_outliers})"
            if passed else
            f"{outlier_count} value(s) in {table}.{column} are outside {range_desc} "
            f"(max allowed: {max_outliers})"
        ),
    }
