"""Shared helpers for the builtin data-quality checks.

Every check returns the same result-dict shape and used to carry its own identical
copy of an `_error` helper plus inline `int(df[col].iloc[0])` scalar extraction.
Centralizing them here keeps each check module focused on its own check logic and
gives the (security-sensitive) SQL/identifier handling a single home to evolve.
"""

import re

from backend.core.database_connector import DatabaseConnector

# Table/column identifiers cannot be supplied as SQL bind parameters, so they are
# validated against a strict allowlist instead: a bare identifier, optionally
# schema-qualified (e.g. "users" or "main.users"). Valid identifiers are returned
# unchanged so legitimate SQL is byte-identical to before; anything containing
# whitespace, quotes, punctuation, or statement separators is rejected. Values
# (e.g. range bounds) are passed as bind parameters and never go through here.
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?$")


class InvalidIdentifier(ValueError):
    """Raised when a table/column identifier fails allowlist validation."""


def safe_identifier(name: str) -> str:
    """Return `name` if it is a valid (optionally schema-qualified) SQL identifier.

    Rejects anything that could break out of an identifier position in a query,
    closing the SQL-injection vector for the f-string-built check queries.
    """
    if not isinstance(name, str) or not _IDENTIFIER_RE.match(name):
        raise InvalidIdentifier(f"Invalid identifier: {name!r}")
    return name


def result(test: dict, type_name: str, status: str, metrics: dict, message: str) -> dict:
    """Build the standard check result dict shared by all checks."""
    return {
        "test_id": test["_test_id"],
        "name": test["name"],
        "type": type_name,
        "status": status,
        "severity": test.get("severity", "MEDIUM"),
        "metrics": metrics,
        "message": message,
    }


def error(test: dict, type_name: str, message: str) -> dict:
    """Build an ERROR result (empty metrics) for validation/runtime failures."""
    return result(test, type_name, "ERROR", {}, message)


def to_int(df, column: str) -> int:
    """Extract the first cell of `column` as a native Python int.

    SQL COUNT(*) aggregates come back as numpy ints inside the DataFrame; callers
    need plain ints for comparisons and JSON serialization downstream.
    """
    return int(df[column].iloc[0])
