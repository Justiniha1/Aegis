"""Shared query builders used by more than one router/runtime.

Centralizes filters that were previously hand-written in multiple places so they
cannot drift — notably the "enabled tests for a profile" selection (used by both
the pre-flight count in runs.py and the actual run in run_executor.py) and the
D-09 active-run guard (used by both runs.py and the scheduler).
"""
from typing import Optional

from sqlalchemy.orm import Query, Session

from dashboard_api import models

# Active = not yet finished. Shared by the trigger endpoint and the scheduler so
# the D-09 concurrency policy is defined in exactly one place.
ACTIVE_RUN_STATUSES = ("QUEUED", "RUNNING")


def enabled_tests_query(
    db: Session,
    client_id: int,
    profile: str,
    type_filter: Optional[list[str]] = None,
) -> Query:
    """Enabled TestDefinitions for a client + profile, optionally narrowed by type.

    Returns the unordered Query so callers can `.count()` (pre-flight) or
    `.order_by(...).all()` (execution) off the identical filter.
    """
    q = db.query(models.TestDefinition).filter(
        models.TestDefinition.client_id == client_id,
        models.TestDefinition.enabled == True,  # noqa: E712 (SQLAlchemy comparison)
        models.TestDefinition.profile == profile,
    )
    if type_filter:
        q = q.filter(models.TestDefinition.type.in_(type_filter))
    return q


def active_run(db: Session, client_id: int) -> Optional[models.Run]:
    """The client's in-flight run (QUEUED or RUNNING), or None. D-09 guard."""
    return (
        db.query(models.Run)
        .filter(
            models.Run.client_id == client_id,
            models.Run.status.in_(ACTIVE_RUN_STATUSES),
        )
        .first()
    )
