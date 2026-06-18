from backend.core.database_connector import DatabaseConnector
from backend.tests.builtin._common import InvalidIdentifier, error, result, safe_identifier, to_int

TYPE = "relationship_check"


def run(connector: DatabaseConnector, test: dict) -> dict:
    source_table = test.get("source_table", "").strip()
    source_column = test.get("source_column", "").strip()
    target_table = test.get("target_table", "").strip()
    target_column = test.get("target_column", "").strip()

    missing = [
        field for field, value in [
            ("source_table", source_table),
            ("source_column", source_column),
            ("target_table", target_table),
            ("target_column", target_column),
        ]
        if not value
    ]
    if missing:
        return error(test, TYPE, f"Missing required field(s): {', '.join(missing)}")

    try:
        source_table = safe_identifier(source_table)
        source_column = safe_identifier(source_column)
        target_table = safe_identifier(target_table)
        target_column = safe_identifier(target_column)
    except InvalidIdentifier as e:
        return error(test, TYPE, str(e))

    max_orphans = test.get("max_orphans", 0)

    df = connector.execute_query(
        f"SELECT COUNT(*) AS orphan_count "
        f"FROM {source_table} src "
        f"LEFT JOIN {target_table} tgt ON src.{source_column} = tgt.{target_column} "
        f"WHERE tgt.{target_column} IS NULL"
    )
    df_total = connector.execute_query(
        f"SELECT COUNT(*) AS total FROM {source_table}"
    )
    orphan_count = to_int(df, "orphan_count")
    total = to_int(df_total, "total")
    orphan_pct = orphan_count / total if total > 0 else 0.0

    passed = orphan_count <= max_orphans
    return result(
        test, TYPE,
        "PASSED" if passed else "FAILED",
        {
            "total_source_rows": total,
            "orphan_count": orphan_count,
            "orphan_percentage": round(orphan_pct, 4),
            "max_orphans_allowed": max_orphans,
        },
        (
            f"{source_table}.{source_column} → {target_table}.{target_column}: "
            f"{orphan_count} orphan(s) — within allowed limit ({max_orphans})"
            if passed else
            f"{orphan_count} orphaned record(s) in {source_table}.{source_column} "
            f"have no match in {target_table}.{target_column} "
            f"(max allowed: {max_orphans})"
        ),
    )
