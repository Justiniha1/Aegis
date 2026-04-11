from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from dashboard_api import models, schemas
from dashboard_api.auth import get_current_client
from dashboard_api.database import get_db

router = APIRouter(prefix="/api/v1/results", tags=["results"])


@router.post("", status_code=201)
def submit_results(
    batch: schemas.ResultsBatch,
    client=Depends(get_current_client),
    db: Session = Depends(get_db),
):
    """
    Called by the backend engine after each test run.
    Accepts a batch of test results and stores them.
    """
    run_at = datetime.utcnow()

    for r in batch.results:
        record = models.TestResult(
            client_id=client.id,
            test_id=r.test_id,
            test_name=r.name,
            test_type=r.type,
            status=r.status,
            severity=r.severity,
            metrics=r.metrics,
            message=r.message,
            run_at=run_at,
        )
        db.add(record)

    db.commit()
    return {"stored": len(batch.results), "run_at": run_at.isoformat()}


@router.get("", response_model=list[schemas.TestResultOut])
def get_results(
    status: Optional[str] = Query(None, description="Filter by status: PASSED, FAILED, ERROR, SKIPPED"),
    test_type: Optional[str] = Query(None, description="Filter by test type: null_check, duplicate_check, etc."),
    limit: int = Query(100, le=1000, description="Max results to return"),
    client=Depends(get_current_client),
    db: Session = Depends(get_db),
):
    """
    Retrieve test results for the authenticated client.
    Results are ordered newest first.
    """
    q = db.query(models.TestResult).filter(models.TestResult.client_id == client.id)

    if status:
        q = q.filter(models.TestResult.status == status.upper())
    if test_type:
        q = q.filter(models.TestResult.test_type == test_type)

    return q.order_by(models.TestResult.run_at.desc()).limit(limit).all()
