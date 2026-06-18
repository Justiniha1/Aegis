from backend.core.database_connector import DatabaseConnector
from backend.tests.builtin._common import InvalidIdentifier, error, result, safe_identifier, to_int

TYPE = "range_check"


def run(connector: DatabaseConnector, test: dict) -> dict:
    table = test.get("table", "").strip()
    column = test.get("column", "").strip()

    if not table:
        return error(test, TYPE, "Missing required field: table")
    if not column:
        return error(test, TYPE, "Missing required field: column")

    try:
        table = safe_identifier(table)
        column = safe_identifier(column)
    except InvalidIdentifier as e:
        return error(test, TYPE, str(e))

    min_value = test.get("min_value")
    max_value = test.get("max_value")
    max_outliers = test.get("max_outliers", 0)

    if min_value is None and max_value is None:
        return error(test, TYPE, "At least one of min_value or max_value must be specified")

    # Bounds are VALUES — bound as SQL parameters, not interpolated. This closes the
    # injection vector and lets string/date bounds work (no longer assumed numeric).
    conditions = []
    params: dict = {}
    if min_value is not None:
        conditions.append(f"{column} < :min_value")
        params["min_value"] = min_value
    if max_value is not None:
        conditions.append(f"{column} > :max_value")
        params["max_value"] = max_value

    where = " OR ".join(conditions)

    df = connector.execute_query(
        f"SELECT COUNT(*) AS outlier_count FROM {table} WHERE {where}", params
    )
    df_total = connector.execute_query(f"SELECT COUNT(*) AS total FROM {table}")
    outlier_count = to_int(df, "outlier_count")
    total = to_int(df_total, "total")

    passed = outlier_count <= max_outliers
    range_desc = f"[{min_value}, {max_value}]"
    return result(
        test, TYPE,
        "PASSED" if passed else "FAILED",
        {
            "total_rows": total,
            "outlier_count": outlier_count,
            "max_outliers_allowed": max_outliers,
            "min_value": min_value,
            "max_value": max_value,
        },
        (
            f"{table}.{column} has {outlier_count} outlier(s) outside {range_desc} "
            f"— within allowed limit ({max_outliers})"
            if passed else
            f"{outlier_count} value(s) in {table}.{column} are outside {range_desc} "
            f"(max allowed: {max_outliers})"
        ),
    )
