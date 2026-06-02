from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from dashboard_api.limiter import limiter, RUNS_LIMIT_STRING
from sqlalchemy.orm import Session

from dashboard_api import models, schemas
from dashboard_api.auth import get_client_any_auth
from dashboard_api.database import get_db
from dashboard_api.run_executor import execute_run
from dashboard_api import connection_source

router = APIRouter(prefix="/api/v1/runs", tags=["runs"])

# The 8 builtin test types — must match TYPE_LABELS keys in frontend/src/lib/constants.ts.
# Server-side whitelist for type_filter input validation (security_constraints).
_ALLOWED_TYPE_FILTERS = frozenset({
    "null_check",
    "duplicate_check",
    "unique_check",
    "row_count",
    "schema_check",
    "range_check",
    "relationship_check",
    "custom_sql",
})


def _to_run_out(r: models.Run) -> schemas.RunOut:
    err = None
    if r.error_reason:
        err = schemas.RunErrorDetail(reason=r.error_reason, at_test=r.error_at_test)
    return schemas.RunOut(
        id=r.id,
        client_id=r.client_id,
        profile=r.profile,
        type_filter=r.type_filter,
        status=r.status,
        total_tests=r.total_tests,
        completed_tests=r.completed_tests,
        started_at=r.started_at,
        completed_at=r.completed_at,
        error=err,
    )


def _compute_total_tests(profile: str, type_filter: list[str] | None, client_id: int, db: Session) -> int:
    """Count enabled TestDefinitions for this client matching profile + optional type_filter."""
    q = (
        db.query(models.TestDefinition)
        .filter(
            models.TestDefinition.client_id == client_id,
            models.TestDefinition.enabled == True,  # noqa: E712 (SQLAlchemy comparison)
            models.TestDefinition.profile == profile,
        )
    )
    if type_filter:
        q = q.filter(models.TestDefinition.type.in_(type_filter))
    return q.count()


@router.post("", response_model=schemas.RunTriggerOut, status_code=202)
@limiter.limit(RUNS_LIMIT_STRING)
def trigger_run(
    request: Request,
    body: schemas.RunCreate,
    background_tasks: BackgroundTasks,
    client=Depends(get_client_any_auth),
    db: Session = Depends(get_db),
):
    """Trigger a new data quality run for the authenticated client.

    Validates profile + type_filter, creates a Run row in QUEUED state, schedules
    execute_run via FastAPI BackgroundTasks, and returns the run_id + total_tests
    synchronously so the UI can immediately render the in-progress chrome.

    Failure paths (D-14 Type-a — "didn't start"):
    - Unknown profile -> 400 with `Couldn't start — profile {name} not found`
    - Invalid type_filter value -> 400 with `Couldn't start — unknown test type(s) {values}`
    - Zero matching enabled tests -> 400 with `Couldn't start — no enabled tests for profile {name}`
    - Active run exists -> 409 `A run is already in progress` (D-09 defense-in-depth)
    """
    # Validate profile against the connection YAML (uploaded or on-disk, per client).
    yaml_text = connection_source.get_yaml_text(db, client.id)
    available, _default = connection_source.profile_names(yaml_text)
    if body.profile not in available:
        raise HTTPException(
            status_code=400,
            detail=f"Couldn't start — profile '{body.profile}' not found in connection config",
        )

    # Validate type_filter against the builtin whitelist (security_constraints).
    if body.type_filter is not None:
        unknown = [t for t in body.type_filter if t not in _ALLOWED_TYPE_FILTERS]
        if unknown:
            allowed = ", ".join(sorted(_ALLOWED_TYPE_FILTERS))
            unknown_display = [t[:64] for t in unknown[:5]]
            raise HTTPException(
                status_code=400,
                detail=f"Couldn't start — unknown test type(s) {unknown_display} — must be one of [{allowed}]",
            )

    # Pre-flight: compute total_tests against the DB. Zero -> reject (D-14 "no tests configured").
    total = _compute_total_tests(body.profile, body.type_filter, client.id, db)
    if total == 0:
        filter_desc = f" with type_filter {body.type_filter}" if body.type_filter else ""
        raise HTTPException(
            status_code=400,
            detail=f"Couldn't start — no enabled tests for profile '{body.profile}'{filter_desc}",
        )

    # Concurrency policy (D-09): the frontend dedupes triggers, but defend in depth.
    # If this client already has an ACTIVE (QUEUED or RUNNING) run, reject with 409.
    active = (
        db.query(models.Run)
        .filter(
            models.Run.client_id == client.id,
            models.Run.status.in_(["QUEUED", "RUNNING"]),
        )
        .first()
    )
    if active is not None:
        raise HTTPException(
            status_code=409,
            detail="A run is already in progress",
        )

    # Create the Run row.
    run = models.Run(
        client_id=client.id,
        profile=body.profile,
        type_filter=body.type_filter,
        status="QUEUED",
        total_tests=total,
        completed_tests=0,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    # Schedule the engine run. BackgroundTasks runs AFTER this response is sent
    # (verified per FastAPI docs) so the response latency stays <100ms.
    background_tasks.add_task(
        execute_run,
        run_id=run.id,
        client_id=client.id,
        profile=body.profile,
        type_filter=body.type_filter,
    )

    return schemas.RunTriggerOut(
        run_id=run.id,
        total_tests=total,
        status=run.status,
    )


@router.get("", response_model=list[schemas.RunOut])
def list_runs(
    limit: int = Query(50, ge=1, le=200),
    client=Depends(get_client_any_auth),
    db: Session = Depends(get_db),
):
    """Return recent runs for the authenticated client, newest first. Scoped by client_id (D-24)."""
    rows = (
        db.query(models.Run)
        .filter(models.Run.client_id == client.id)
        .order_by(models.Run.started_at.desc())
        .limit(limit)
        .all()
    )
    return [_to_run_out(r) for r in rows]


@router.get("/{run_id}", response_model=schemas.RunOut)
def get_run(
    run_id: int,
    client=Depends(get_client_any_auth),
    db: Session = Depends(get_db),
):
    """Return a single run by id. 404 on cross-client access (per security_constraints — never 403)."""
    r = (
        db.query(models.Run)
        .filter(models.Run.id == run_id, models.Run.client_id == client.id)
        .first()
    )
    if not r:
        # Intentional 404 (not 403) — avoids leaking existence of other clients' runs.
        raise HTTPException(status_code=404, detail="Run not found")
    return _to_run_out(r)
