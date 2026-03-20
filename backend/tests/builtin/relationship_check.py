from backend.core.database_connector import DatabaseConnector


def run(connector: DatabaseConnector, test: dict) -> dict:
    source_table = test["source_table"]
    source_column = test["source_column"]
    target_table = test["target_table"]
    target_column = test["target_column"]
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
    orphan_count = int(df["orphan_count"].iloc[0])
    total = int(df_total["total"].iloc[0])
    orphan_pct = orphan_count / total if total > 0 else 0.0

    passed = orphan_count <= max_orphans
    return {
        "test_id": test["_test_id"],
        "name": test["name"],
        "type": "relationship_check",
        "status": "PASSED" if passed else "FAILED",
        "severity": test.get("severity", "MEDIUM"),
        "metrics": {
            "total_source_rows": total,
            "orphan_count": orphan_count,
            "orphan_percentage": round(orphan_pct, 4),
            "max_orphans_allowed": max_orphans,
        },
        "message": (
            f"{source_table}.{source_column} → {target_table}.{target_column}: "
            f"{orphan_count} orphan(s) — within allowed limit ({max_orphans})"
            if passed else
            f"{orphan_count} orphaned record(s) in {source_table}.{source_column} "
            f"have no match in {target_table}.{target_column} "
            f"(max allowed: {max_orphans})"
        ),
    }
