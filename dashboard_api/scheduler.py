"""In-process APScheduler runtime for periodic schedule polling.

Architecture notes (locked in 09-CONTEXT.md):
- Single in-process AsyncIOScheduler: the Dockerfile CMD is already single-process and
  single-replica. COMET_SCHEDULER_ENABLED is the seam to graduate to a dedicated worker
  later; for now it gates whether THIS process runs the poller (prevents double-fire on
  multi-replica deploys if the env var is set to 1 only on one instance).
- Table-as-source-of-truth: no APScheduler job store. The Schedule table is the only
  durable store; the poller re-reads next_run_at on every tick so schedules survive
  Railway redeploys without any extra state in APScheduler.
- Threadpool dispatch: execute_run is synchronous (pandas/sync SQLAlchemy). It MUST be
  dispatched via run_in_threadpool so it never blocks the event loop (Pitfall 2).
- Overlap guard: max_instances=1 + coalesce=True at the APScheduler job level prevents
  two poll_due_schedules coroutines from running concurrently. The D-09 active-run guard
  replicated here prevents two *engine* runs from being dispatched for the same client.
- Skip-missed: next_run_at is always rolled forward by exactly one interval (compute_next_run)
  regardless of how far in the past it was, so a long downtime never causes a catch-up burst.
"""
import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool

from dashboard_api.database import SessionLocal
from dashboard_api import models
from dashboard_api.run_executor import execute_run
from dashboard_api.queries import active_run
from dashboard_api.schedule_logic import compute_next_run

logger = logging.getLogger(__name__)

_scheduler = AsyncIOScheduler(timezone="UTC")

_POLL_INTERVAL_SECONDS = 60


async def poll_due_schedules() -> None:
    """Scan the Schedule table for due rows and dispatch each via execute_run.

    Pitfall mitigations applied here:
    - D-09 active-run guard: if the client already has a QUEUED/RUNNING run, we skip
      creating a second one but still advance next_run_at to prevent a hot-loop.
    - Skip-missed: next_run_at is rolled forward exactly once per due row, so a restarted
      service after downtime does not fire a burst of catch-up runs.
    - Error isolation: each schedule row gets its own fresh session so an exception and
      rollback on one row cannot corrupt state for the next row.
    """
    now = datetime.utcnow()

    # Fetch the due schedule IDs using a short-lived scan session.
    # We re-open per row so that a rollback on one row never affects another.
    scan_db = SessionLocal()
    try:
        due_ids: list[int] = [
            row.id
            for row in scan_db.query(models.Schedule.id)
            .filter(
                models.Schedule.enabled == True,  # noqa: E712
                models.Schedule.next_run_at <= now,
            )
            .all()
        ]
    finally:
        scan_db.close()

    for sched_id in due_ids:
        db = SessionLocal()
        try:
            sched = db.query(models.Schedule).filter(models.Schedule.id == sched_id).first()
            if sched is None:
                # Deleted between the scan and now — skip.
                continue

            # D-09 active-run guard: shared with runs.py via queries.active_run. The
            # partial unique index is the real backstop — if a manual trigger raced and
            # created the active run between our check and insert, the commit raises
            # IntegrityError; treat that as "already active" and just roll next_run_at forward.
            dispatched = False
            if active_run(db, sched.client_id) is None:
                run = models.Run(
                    client_id=sched.client_id,
                    profile=sched.profile,
                    type_filter=None,
                    status="QUEUED",
                    total_tests=0,
                    completed_tests=0,
                )
                db.add(run)
                raced = False
                try:
                    db.commit()
                except IntegrityError:
                    # A manual trigger created the active run first; skip and roll forward.
                    db.rollback()
                    raced = True

                if not raced:
                    db.refresh(run)
                    dispatched = True
                    try:
                        # Dispatch to the threadpool — execute_run is synchronous.
                        await run_in_threadpool(
                            execute_run,
                            run_id=run.id,
                            client_id=sched.client_id,
                            profile=sched.profile,
                            type_filter=None,
                            alert=True,  # scheduled run — notify the client on failure
                        )
                    except Exception as dispatch_err:
                        # execute_run is contracted never to raise, but if it does the Run
                        # row is already committed as QUEUED. Leaving it QUEUED would make the
                        # active-run guard above suppress every future scheduled run for this
                        # client forever (silent deadlock). Mark it FAILED so the client is not
                        # permanently blocked.
                        db.rollback()
                        stuck = db.query(models.Run).filter(models.Run.id == run.id).first()
                        if stuck is not None and stuck.status in ("QUEUED", "RUNNING"):
                            stuck.status = "FAILED"
                            stuck.error_reason = f"scheduler dispatch failed: {dispatch_err}"
                            stuck.completed_at = datetime.utcnow()
                            db.commit()

            # Always roll next_run_at forward — skip-missed, no catch-up burst.
            # Apply even when we skipped due to an active run, so we do not hot-loop.
            # last_run_at is stamped only when a run was actually dispatched, so it never
            # records a run that the active-run guard suppressed.
            if dispatched:
                sched.last_run_at = now
            sched.next_run_at = compute_next_run(
                sched.preset,
                now=now,
                at_hour=sched.at_hour or 0,
                at_minute=sched.at_minute or 0,
                weekday=sched.weekday or 0,
            )
            sched.updated_at = now
            db.commit()

        except Exception as e:
            logger.warning("schedule id=%s failed: %s", sched_id, e)
            try:
                db.rollback()
            except Exception:
                pass
        finally:
            db.close()


def start_scheduler() -> None:
    """Register the polling job and start the scheduler (idempotent)."""
    if not _scheduler.running:
        _scheduler.add_job(
            poll_due_schedules,
            "interval",
            seconds=_POLL_INTERVAL_SECONDS,
            id="poll_due_schedules",
            max_instances=1,
            coalesce=True,
            replace_existing=True,
        )
        _scheduler.start()


def stop_scheduler() -> None:
    """Shut down the scheduler gracefully (idempotent)."""
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
