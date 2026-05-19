from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from dashboard_api import models, schemas
from dashboard_api.auth import get_current_client_jwt
from dashboard_api.database import get_db

router = APIRouter(prefix="/api/v1/runs", tags=["runs"])


def _to_run_out(r: models.Run) -> schemas.RunOut:
    """Compose a RunOut from a Run row, folding error_reason + error_at_test into the nested error object."""
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


@router.post("", response_model=schemas.RunTriggerOut, status_code=202)
def trigger_run(
    body: schemas.RunCreate,
    client=Depends(get_current_client_jwt),
    db: Session = Depends(get_db),
):
    """Trigger a new run. SKELETON — Wave 1 (plan 02-02) implements the actual trigger.

    This skeleton validates the contract (auth + body shape) and returns 501 so the
    frontend wire-up in plans 02-03/02-04 can be developed against a real auth-gated
    endpoint while 02-02 lands in parallel.
    """
    # Validate profile exists — full validation will be in 02-02 (against YAML)
    # type_filter validation also in 02-02
    raise HTTPException(status_code=501, detail="Run trigger not yet implemented — see plan 02-02")


@router.get("", response_model=list[schemas.RunOut])
def list_runs(
    limit: int = 50,
    client=Depends(get_current_client_jwt),
    db: Session = Depends(get_db),
):
    """Return recent runs for the authenticated client, newest first. Scoped by client_id (D-24)."""
    if limit > 200:
        limit = 200
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
    client=Depends(get_current_client_jwt),
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
