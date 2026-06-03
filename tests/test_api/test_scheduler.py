"""Tests for dashboard_api.scheduler.poll_due_schedules.

Verifies dispatch, overlap-skip, skip-missed, disabled-flag, and error-resilience
behavior WITHOUT running the engine (execute_run and run_in_threadpool are patched).

All tests run poll_due_schedules() directly using asyncio.run().
The DB is an in-memory SQLite session seeded with fixture data.
"""
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from dashboard_api.models import Base, Client, Run, Schedule
from dashboard_api.schedule_logic import compute_next_run

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db(tmp_path):
    """Return a bound SessionLocal for an isolated in-memory SQLite DB."""
    engine = create_engine(
        f"sqlite:///{tmp_path}/sched_test.db",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session


def _add_schedule(db, client_id: int, profile: str = "staging",
                  preset: str = "hourly",
                  next_run_at: datetime = None,
                  enabled: bool = True) -> Schedule:
    if next_run_at is None:
        # Past — due now
        next_run_at = datetime.utcnow() - timedelta(minutes=5)
    s = Schedule(
        client_id=client_id,
        profile=profile,
        preset=preset,
        at_hour=6,
        at_minute=0,
        weekday=0,
        enabled=enabled,
        next_run_at=next_run_at,
        cron="0 * * * *",
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def _add_client(db, name="testco") -> Client:
    c = Client(name=name, email=f"{name}@test.com", api_key_hash="x" * 64)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


# ---------------------------------------------------------------------------
# Test 1: poll dispatches a due, enabled schedule with no active run
# ---------------------------------------------------------------------------

def test_poll_dispatches_due(tmp_path):
    """poll_due_schedules creates a QUEUED Run and advances next_run_at for a due schedule."""
    Session = _make_db(tmp_path)
    db = Session()
    client = _add_client(db)
    sched = _add_schedule(db, client_id=client.id)
    db.close()

    # Patch run_in_threadpool to a no-op coroutine; patch execute_run to a MagicMock.
    with patch("dashboard_api.scheduler.SessionLocal", Session), \
         patch("dashboard_api.scheduler.run_in_threadpool", new_callable=AsyncMock) as mock_rtp, \
         patch("dashboard_api.scheduler.execute_run") as mock_exec:
        asyncio.run(__import__("dashboard_api.scheduler", fromlist=["poll_due_schedules"]).poll_due_schedules())

    # A QUEUED run was created
    db = Session()
    runs = db.query(Run).filter(Run.client_id == client.id).all()
    assert len(runs) == 1, f"Expected 1 run, got {len(runs)}"
    assert runs[0].status == "QUEUED"
    assert runs[0].profile == "staging"

    # next_run_at rolled forward
    sched_after = db.query(Schedule).filter(Schedule.id == sched.id).first()
    assert sched_after.next_run_at > datetime.utcnow(), "next_run_at must be in the future"
    assert sched_after.last_run_at is not None, "last_run_at must be set"
    db.close()


# ---------------------------------------------------------------------------
# Test 2: poll skips schedules whose next_run_at is in the future
# ---------------------------------------------------------------------------

def test_poll_skips_not_due(tmp_path):
    """A schedule whose next_run_at is in the future is not dispatched."""
    Session = _make_db(tmp_path)
    db = Session()
    client = _add_client(db)
    _add_schedule(db, client_id=client.id,
                  next_run_at=datetime.utcnow() + timedelta(hours=1))  # future
    db.close()

    with patch("dashboard_api.scheduler.SessionLocal", Session), \
         patch("dashboard_api.scheduler.run_in_threadpool", new_callable=AsyncMock), \
         patch("dashboard_api.scheduler.execute_run"):
        asyncio.run(__import__("dashboard_api.scheduler", fromlist=["poll_due_schedules"]).poll_due_schedules())

    db = Session()
    runs = db.query(Run).filter(Run.client_id == client.id).all()
    assert len(runs) == 0, f"Expected 0 runs for a future schedule, got {len(runs)}"
    db.close()


# ---------------------------------------------------------------------------
# Test 3: poll skips disabled schedules even if next_run_at is past
# ---------------------------------------------------------------------------

def test_poll_skips_disabled(tmp_path):
    """enabled=False schedules are never dispatched even if next_run_at is in the past."""
    Session = _make_db(tmp_path)
    db = Session()
    client = _add_client(db)
    _add_schedule(db, client_id=client.id, enabled=False,
                  next_run_at=datetime.utcnow() - timedelta(hours=1))
    db.close()

    with patch("dashboard_api.scheduler.SessionLocal", Session), \
         patch("dashboard_api.scheduler.run_in_threadpool", new_callable=AsyncMock), \
         patch("dashboard_api.scheduler.execute_run"):
        asyncio.run(__import__("dashboard_api.scheduler", fromlist=["poll_due_schedules"]).poll_due_schedules())

    db = Session()
    runs = db.query(Run).filter(Run.client_id == client.id).all()
    assert len(runs) == 0, f"Expected 0 runs for a disabled schedule, got {len(runs)}"
    db.close()


# ---------------------------------------------------------------------------
# Test 4: D-09 active-run guard — skip dispatch but still advance next_run_at
# ---------------------------------------------------------------------------

def test_poll_respects_active_run_guard(tmp_path):
    """If client already has QUEUED/RUNNING run, poll skips dispatch but still advances next_run_at."""
    Session = _make_db(tmp_path)
    db = Session()
    client = _add_client(db)
    sched = _add_schedule(db, client_id=client.id)
    # Pre-existing active run
    existing_run = Run(
        client_id=client.id,
        profile="staging",
        type_filter=None,
        status="RUNNING",
        total_tests=0,
        completed_tests=0,
    )
    db.add(existing_run)
    db.commit()
    db.close()

    with patch("dashboard_api.scheduler.SessionLocal", Session), \
         patch("dashboard_api.scheduler.run_in_threadpool", new_callable=AsyncMock) as mock_rtp, \
         patch("dashboard_api.scheduler.execute_run"):
        asyncio.run(__import__("dashboard_api.scheduler", fromlist=["poll_due_schedules"]).poll_due_schedules())

    # run_in_threadpool was NOT called (no second run created)
    mock_rtp.assert_not_called()

    db = Session()
    # Only the pre-existing run exists — no new QUEUED run was added
    all_runs = db.query(Run).filter(Run.client_id == client.id).all()
    assert len(all_runs) == 1, f"Expected 1 run (the existing one), got {len(all_runs)}"

    # next_run_at was still rolled forward (no hot-loop)
    sched_after = db.query(Schedule).filter(Schedule.id == sched.id).first()
    assert sched_after.next_run_at > datetime.utcnow(), (
        "next_run_at must be advanced even when dispatch is skipped"
    )
    db.close()


# ---------------------------------------------------------------------------
# Test 5: skip-missed — even if very overdue, exactly one run is dispatched
# ---------------------------------------------------------------------------

def test_poll_skips_missed_no_catchup(tmp_path):
    """A schedule that was missed many intervals ago fires at most once and rolls next_run_at forward."""
    Session = _make_db(tmp_path)
    db = Session()
    client = _add_client(db)
    # next_run_at is 7 days in the past — a very missed schedule
    _add_schedule(db, client_id=client.id,
                  next_run_at=datetime.utcnow() - timedelta(days=7))
    db.close()

    with patch("dashboard_api.scheduler.SessionLocal", Session), \
         patch("dashboard_api.scheduler.run_in_threadpool", new_callable=AsyncMock) as mock_rtp, \
         patch("dashboard_api.scheduler.execute_run"):
        asyncio.run(__import__("dashboard_api.scheduler", fromlist=["poll_due_schedules"]).poll_due_schedules())

    # Exactly one run dispatched (not 168 = 7*24 hourly catch-ups)
    db = Session()
    runs = db.query(Run).filter(Run.client_id == client.id).all()
    assert len(runs) == 1, f"Expected exactly 1 run (no catch-up burst), got {len(runs)}"

    # next_run_at is in the future (single-step roll-forward)
    from dashboard_api.models import Schedule
    sched_after = db.query(Schedule).filter(Schedule.client_id == client.id).first()
    assert sched_after.next_run_at > datetime.utcnow(), "next_run_at must be in the future after roll-forward"
    db.close()


# ---------------------------------------------------------------------------
# Test 6: one bad schedule does not kill the rest of the loop
# ---------------------------------------------------------------------------

def test_one_bad_schedule_does_not_kill_loop(tmp_path):
    """If processing one schedule raises, the exception is caught and the loop continues."""
    Session = _make_db(tmp_path)
    db = Session()
    client = _add_client(db)
    bad_sched = _add_schedule(db, client_id=client.id, profile="bad", preset="hourly")
    good_sched = _add_schedule(db, client_id=client.id, profile="good", preset="hourly")
    db.close()

    call_count = {"n": 0}

    async def selective_rtp(fn, **kwargs):
        """Raise on the first call (bad schedule), succeed on the second (good schedule)."""
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("simulated engine failure")
        # No-op for subsequent calls

    with patch("dashboard_api.scheduler.SessionLocal", Session), \
         patch("dashboard_api.scheduler.run_in_threadpool", side_effect=selective_rtp), \
         patch("dashboard_api.scheduler.execute_run"):
        asyncio.run(__import__("dashboard_api.scheduler", fromlist=["poll_due_schedules"]).poll_due_schedules())

    db = Session()
    # The good schedule should still have produced a Run despite the bad one failing
    good_runs = db.query(Run).filter(
        Run.client_id == client.id,
        Run.profile == "good",
    ).all()
    assert len(good_runs) == 1, (
        f"Expected 1 run for 'good' schedule after bad schedule exception, got {len(good_runs)}"
    )
    db.close()
