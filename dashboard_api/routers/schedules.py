"""Tenant-scoped schedules CRUD router.

Security invariants:
- Every query is scoped by client_id (T-09C-01: IDOR prevention).
- create/update re-derives is_website_schedulable server-side (T-09C-02: API-side guardrail).
- ScheduleOut exposes only schedule metadata, never connection secrets (T-09C-03).
- Profile name is validated against the requesting client's own YAML (T-09C-04).
- One schedule per (client, profile) enforced by pre-check + UniqueConstraint (T-09C-05).
- Cross-client access returns 404 not 403 (mirrors runs.py tenant-404 pattern).
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from dashboard_api import connection_source, models, schemas
from dashboard_api.auth import get_client_any_auth
from dashboard_api.database import get_db
from dashboard_api.schedule_logic import compute_next_run, preset_to_cron

router = APIRouter(prefix="/api/v1/schedules", tags=["schedules"])


def _get_schedule_or_404(schedule_id: int, client: models.Client, db: Session) -> models.Schedule:
    """Fetch a schedule owned by this client; return 404 for missing or cross-client access."""
    s = (
        db.query(models.Schedule)
        .filter(
            models.Schedule.id == schedule_id,
            models.Schedule.client_id == client.id,
        )
        .first()
    )
    if s is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return s


@router.post("", response_model=schemas.ScheduleOut, status_code=201)
def create_schedule(
    body: schemas.ScheduleCreate,
    client: models.Client = Depends(get_client_any_auth),
    db: Session = Depends(get_db),
):
    """Create a new recurring schedule for a profile owned by the authenticated client.

    Failure paths:
    - Unknown profile -> 400 "profile '{p}' not found"
    - Non-schedulable profile (sqlite/local) -> 400 with cannot-be-scheduled message
    - Duplicate (client, profile) -> 409 "This profile already has a schedule."
    """
    yaml_text = connection_source.get_yaml_text(db, client.id)

    # Validate profile exists in this client's YAML (T-09C-04)
    names, _ = connection_source.profile_names(yaml_text)
    if body.profile not in names:
        raise HTTPException(
            status_code=400,
            detail=f"Profile '{body.profile}' not found in connection config",
        )

    # Capability guard — re-derive server-side (T-09C-02, defense in depth behind UI)
    types = connection_source.profile_types(yaml_text)
    db_type = types.get(body.profile, "")
    if not connection_source.is_website_schedulable(db_type):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Profile '{body.profile}' cannot be scheduled from the dashboard"
                " — schedule it from the client lane instead."
            ),
        )

    # One-per-(client, profile) pre-check (T-09C-05)
    existing = (
        db.query(models.Schedule)
        .filter(
            models.Schedule.client_id == client.id,
            models.Schedule.profile == body.profile,
        )
        .first()
    )
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail="This profile already has a schedule.",
        )

    cron = preset_to_cron(body.preset, at_hour=body.at_hour, at_minute=body.at_minute, weekday=body.weekday)
    next_run = compute_next_run(
        preset=body.preset, at_hour=body.at_hour, at_minute=body.at_minute, weekday=body.weekday
    )

    schedule = models.Schedule(
        client_id=client.id,
        profile=body.profile,
        preset=body.preset,
        at_hour=body.at_hour,
        at_minute=body.at_minute,
        weekday=body.weekday,
        cron=cron,
        enabled=body.enabled,
        next_run_at=next_run,
    )
    db.add(schedule)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="This profile already has a schedule.",
        )
    db.refresh(schedule)
    return schedule


@router.get("", response_model=list[schemas.ScheduleOut])
def list_schedules(
    client: models.Client = Depends(get_client_any_auth),
    db: Session = Depends(get_db),
):
    """List all schedules for the authenticated client, ordered by creation time."""
    return (
        db.query(models.Schedule)
        .filter(models.Schedule.client_id == client.id)
        .order_by(models.Schedule.created_at.asc())
        .all()
    )


@router.get("/{schedule_id}", response_model=schemas.ScheduleOut)
def get_schedule(
    schedule_id: int,
    client: models.Client = Depends(get_client_any_auth),
    db: Session = Depends(get_db),
):
    """Return a single schedule. 404 on cross-client access (never 403)."""
    return _get_schedule_or_404(schedule_id, client, db)


@router.patch("/{schedule_id}", response_model=schemas.ScheduleOut)
def update_schedule(
    schedule_id: int,
    body: schemas.ScheduleUpdate,
    client: models.Client = Depends(get_client_any_auth),
    db: Session = Depends(get_db),
):
    """Enable/pause a schedule or update its preset. 404 on cross-client access."""
    s = _get_schedule_or_404(schedule_id, client, db)

    if body.enabled is not None:
        s.enabled = body.enabled

    # Recompute cron + next_run_at when preset or time fields change
    preset_changed = body.preset is not None
    time_changed = body.at_hour is not None or body.at_minute is not None or body.weekday is not None

    if preset_changed:
        s.preset = body.preset
    if body.at_hour is not None:
        s.at_hour = body.at_hour
    if body.at_minute is not None:
        s.at_minute = body.at_minute
    if body.weekday is not None:
        s.weekday = body.weekday

    if preset_changed or time_changed:
        effective_preset = s.preset or "hourly"
        effective_at_hour = s.at_hour or 0
        effective_at_minute = s.at_minute or 0
        effective_weekday = s.weekday or 0
        s.cron = preset_to_cron(
            effective_preset,
            at_hour=effective_at_hour,
            at_minute=effective_at_minute,
            weekday=effective_weekday,
        )
        s.next_run_at = compute_next_run(
            preset=effective_preset,
            at_hour=effective_at_hour,
            at_minute=effective_at_minute,
            weekday=effective_weekday,
        )

    s.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(s)
    return s


@router.delete("/{schedule_id}", status_code=204)
def delete_schedule(
    schedule_id: int,
    client: models.Client = Depends(get_client_any_auth),
    db: Session = Depends(get_db),
):
    """Delete a schedule. 404 on cross-client access (never 403)."""
    s = _get_schedule_or_404(schedule_id, client, db)
    db.delete(s)
    db.commit()
