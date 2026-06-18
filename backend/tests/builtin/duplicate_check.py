from backend.core.database_connector import DatabaseConnector
from backend.tests.builtin._common import InvalidIdentifier, error, result, safe_identifier, to_int

TYPE = "duplicate_check"


def run(connector: DatabaseConnector, test: dict) -> dict:
    table = test.get("table", "").strip()
    if not table:
        return error(test, TYPE, "Missing required field: table")

    # Support both 'column' (singular) and 'columns' (list)
    raw_cols = test.get("columns") or [test.get("column")]
    columns = [c for c in raw_cols if c]
    if not columns:
        return error(test, TYPE, "At least one column must be specified for duplicate_check")

    try:
        table = safe_identifier(table)
        columns = [safe_identifier(c) for c in columns]
    except InvalidIdentifier as e:
        return error(test, TYPE, str(e))

    max_allowed = test.get("max_allowed", 0)

    cols_sql = ", ".join(columns)
    df_dups = connector.execute_query(
        f"SELECT COUNT(*) AS dup_groups "
        f"FROM ("
        f"  SELECT {cols_sql}, COUNT(*) AS cnt FROM {table} "
        f"  GROUP BY {cols_sql} HAVING COUNT(*) > 1"
        f") sub"
    )
    dup_groups = to_int(df_dups, "dup_groups")

    df_total = connector.execute_query(f"SELECT COUNT(*) AS total FROM {table}")
    total = to_int(df_total, "total")

    passed = dup_groups <= max_allowed
    return result(
        test, TYPE,
        "PASSED" if passed else "FAILED",
        {
            "total_rows": total,
            "duplicate_groups": dup_groups,
            "max_allowed": max_allowed,
            "columns_checked": columns,
        },
        (
            f"No excess duplicates found on {cols_sql}"
            if passed else
            f"{dup_groups} duplicate group(s) found on [{cols_sql}] in {table} "
            f"(max allowed: {max_allowed})"
        ),
    )
