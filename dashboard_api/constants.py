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
