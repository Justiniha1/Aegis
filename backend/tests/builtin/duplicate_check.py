from backend.core.database_connector import DatabaseConnector


def run(connector: DatabaseConnector, test: dict) -> dict:
    table = test.get("table", "").strip()
    if not table:
        return _error(test, "Missing required field: table")

    # Support both 'column' (singular) and 'columns' (list)
    raw_cols = test.get("columns") or [test.get("column")]
    columns = [c for c in raw_cols if c]
    if not columns:
        return _error(test, "At least one column must be specified for duplicate_check")

    max_allowed = test.get("max_allowed", 0)

    cols_sql = ", ".join(columns)
    df_dups = connector.execute_query(
        f"SELECT COUNT(*) AS dup_groups "
        f"FROM ("
        f"  SELECT {cols_sql}, COUNT(*) AS cnt FROM {table} "
        f"  GROUP BY {cols_sql} HAVING COUNT(*) > 1"
        f") sub"
    )
    dup_groups = int(df_dups["dup_groups"].iloc[0])

    df_total = connector.execute_query(f"SELECT COUNT(*) AS total FROM {table}")
    total = int(df_total["total"].iloc[0])

    passed = dup_groups <= max_allowed
    return {
        "test_id": test["_test_id"],
        "name": test["name"],
        "type": "duplicate_check",
        "status": "PASSED" if passed else "FAILED",
        "severity": test.get("severity", "MEDIUM"),
        "metrics": {
            "total_rows": total,
            "duplicate_groups": dup_groups,
            "max_allowed": max_allowed,
            "columns_checked": columns,
        },
        "message": (
            f"No excess duplicates found on {cols_sql}"
            if passed else
            f"{dup_groups} duplicate group(s) found on [{cols_sql}] in {table} "
            f"(max allowed: {max_allowed})"
        ),
    }


def _error(test: dict, msg: str) -> dict:
    return {
        "test_id": test["_test_id"],
        "name": test["name"],
        "type": "duplicate_check",
        "status": "ERROR",
        "severity": test.get("severity", "MEDIUM"),
        "metrics": {},
        "message": msg,
    }
