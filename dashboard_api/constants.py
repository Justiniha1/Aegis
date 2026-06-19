"""Shared constants for the dashboard API.

Single source of truth for values that were previously duplicated across routers.
"""

# The 8 builtin test types. Must match the check module names under
# backend/tests/builtin/ and the TYPE_LABELS keys in frontend/src/lib/constants.ts.
# Used server-side to validate type filters on the results and runs endpoints.
TEST_TYPES = frozenset({
    "null_check",
    "duplicate_check",
    "unique_check",
    "row_count",
    "schema_check",
    "range_check",
    "relationship_check",
    "custom_sql",
})

# dbt-sourced result types produced by `comet dbt publish`. These are ingest-only
# labels (not executable check types), but the results GET filter must accept them
# so the dashboard can filter dbt results by kind.
DBT_TEST_TYPES = frozenset({
    "dbt_not_null",
    "dbt_unique",
    "dbt_relationships",
    "dbt_accepted_values",
    "dbt_test",
})
