"""Unit tests for dashboard_api.schedule_logic (compute_next_run + preset_to_cron).

All datetimes are naive UTC, matching the utcnow() convention used throughout models.py.
"""
import pytest
from datetime import datetime


# ---------------------------------------------------------------------------
# Model metadata tests — no Schedule imports needed from schedule_logic
# ---------------------------------------------------------------------------

def test_schedule_table_in_metadata():
    """'schedules' must be in Base.metadata.tables with the required columns."""
    from dashboard_api.models import Base

    assert "schedules" in Base.metadata.tables, "schedules table not in metadata"
    t = Base.metadata.tables["schedules"]
    required_columns = {
        "id", "client_id", "profile", "cron", "interval_seconds",
        "enabled", "last_run_at", "next_run_at", "created_at", "updated_at",
    }
    actual_columns = set(t.columns.keys())
    missing = required_columns - actual_columns
    assert not missing, f"Missing columns in schedules table: {missing}"

    # UniqueConstraint(client_id, profile) must exist
    from sqlalchemy import UniqueConstraint
    constraint_names = {c.name for c in t.constraints}
    assert "uq_schedule_client_profile" in constraint_names, (
        f"UniqueConstraint 'uq_schedule_client_profile' not found; constraints: {constraint_names}"
    )


# ---------------------------------------------------------------------------
# compute_next_run tests
# ---------------------------------------------------------------------------

def test_hourly_next_run():
    """hourly preset: next_run_at is top of the next hour."""
    from dashboard_api.schedule_logic import compute_next_run

    now = datetime(2026, 6, 2, 10, 30, 0)  # 10:30 UTC
    result = compute_next_run(preset="hourly", now=now)
    assert result == datetime(2026, 6, 2, 11, 0, 0), f"Expected 11:00, got {result}"


def test_daily_next_run_after_time():
    """daily preset when now is AFTER today's at_hour: returns next day at at_hour:at_minute."""
    from dashboard_api.schedule_logic import compute_next_run

    now = datetime(2026, 6, 2, 10, 30, 0)  # after 06:00
    result = compute_next_run(preset="daily", at_hour=6, at_minute=0, now=now)
    assert result == datetime(2026, 6, 3, 6, 0, 0), f"Expected 2026-06-03T06:00, got {result}"


def test_daily_next_run_before_time():
    """daily preset when now is BEFORE today's at_hour: returns today at at_hour:at_minute."""
    from dashboard_api.schedule_logic import compute_next_run

    now = datetime(2026, 6, 2, 4, 0, 0)  # before 06:00
    result = compute_next_run(preset="daily", at_hour=6, at_minute=0, now=now)
    assert result == datetime(2026, 6, 2, 6, 0, 0), f"Expected 2026-06-02T06:00, got {result}"


def test_weekly_next_run():
    """weekly preset: from a Wednesday, next Monday 06:00 UTC."""
    from dashboard_api.schedule_logic import compute_next_run

    # Wednesday 2026-06-03
    now = datetime(2026, 6, 3, 12, 0, 0)  # weekday() == 2 (Wed)
    result = compute_next_run(preset="weekly", weekday=0, at_hour=6, now=now)
    # Next Monday is 2026-06-08
    assert result == datetime(2026, 6, 8, 6, 0, 0), f"Expected 2026-06-08T06:00, got {result}"


def test_invalid_preset_raises():
    """Unknown preset must raise ValueError mentioning the allowed presets."""
    from dashboard_api.schedule_logic import compute_next_run

    with pytest.raises(ValueError, match="hourly|daily|weekly"):
        compute_next_run(preset="every-5-min")


# ---------------------------------------------------------------------------
# preset_to_cron tests
# ---------------------------------------------------------------------------

def test_to_cron_canonical():
    """preset_to_cron returns canonical UTC cron strings for the three presets."""
    from dashboard_api.schedule_logic import preset_to_cron

    assert preset_to_cron("hourly") == "0 * * * *"
    assert preset_to_cron("daily", at_hour=6, at_minute=0) == "0 6 * * *"
    assert preset_to_cron("weekly", at_hour=6, at_minute=0, weekday=0) == "0 6 * * 1"
