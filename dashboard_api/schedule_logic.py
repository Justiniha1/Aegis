"""Pure scheduling logic: preset_to_cron and compute_next_run.

All datetimes are naive UTC, matching the utcnow() convention used throughout models.py.
No APScheduler or croniter dependency — stdlib datetime/timedelta only.
"""
from datetime import datetime, timedelta

_ALLOWED_PRESETS = {"hourly", "daily", "weekly"}


def preset_to_cron(preset: str, at_hour: int = 0, at_minute: int = 0, weekday: int = 0) -> str:
    """Return a canonical UTC cron string for the given preset.

    hourly  -> "0 * * * *"
    daily   -> "0 {at_hour} * * *"         (at_minute always 0 in v1.3)
    weekly  -> "0 {at_hour} * * {weekday+1}"  (cron weekday: 1=Mon..7=Sun, we add 1 to 0-indexed)
    """
    if preset == "hourly":
        return "0 * * * *"
    if preset == "daily":
        return f"{at_minute} {at_hour} * * *"
    if preset == "weekly":
        # cron weekday: 1=Monday, 7=Sunday (some use 0=Sunday but standard is 1=Monday)
        # We follow the standard where 1=Monday to match weekday=0 (Mon) -> cron 1
        cron_weekday = weekday + 1
        return f"{at_minute} {at_hour} * * {cron_weekday}"
    raise ValueError(
        f"Unknown preset '{preset}'. Allowed presets: {sorted(_ALLOWED_PRESETS)}"
    )


def compute_next_run(
    preset: str,
    now: datetime | None = None,
    at_hour: int = 0,
    at_minute: int = 0,
    weekday: int = 0,
) -> datetime:
    """Compute the next UTC run time for a given scheduling preset.

    All returned datetimes are naive UTC (no tzinfo), matching datetime.utcnow() convention.

    Args:
        preset: "hourly", "daily", or "weekly".
        now: reference time (naive UTC); defaults to datetime.utcnow().
        at_hour: hour of day (0-23) for daily/weekly.
        at_minute: minute of hour (0-59) for daily/weekly.
        weekday: day of week for weekly (0=Monday, 6=Sunday), following Python's weekday().

    Returns:
        Naive UTC datetime of the next scheduled run.

    Raises:
        ValueError: if preset is not one of _ALLOWED_PRESETS.
    """
    if preset not in _ALLOWED_PRESETS:
        raise ValueError(
            f"Unknown preset '{preset}'. Allowed presets: {sorted(_ALLOWED_PRESETS)}"
        )

    if now is None:
        now = datetime.utcnow()

    if preset == "hourly":
        # Top of the next hour
        next_run = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        return next_run

    if preset == "daily":
        # Today at at_hour:at_minute — if already past, advance to tomorrow
        candidate = now.replace(hour=at_hour, minute=at_minute, second=0, microsecond=0)
        if candidate <= now:
            candidate += timedelta(days=1)
        return candidate

    if preset == "weekly":
        # Next occurrence of `weekday` at at_hour:at_minute
        # Python weekday(): 0=Mon, 6=Sun
        today_weekday = now.weekday()
        days_ahead = weekday - today_weekday
        if days_ahead < 0:
            days_ahead += 7
        candidate = (now + timedelta(days=days_ahead)).replace(
            hour=at_hour, minute=at_minute, second=0, microsecond=0
        )
        # If today is the target weekday but the time has already passed, advance a week
        if candidate <= now:
            candidate += timedelta(weeks=1)
        return candidate

    # unreachable — caught by preset check above
    raise ValueError(f"Unknown preset '{preset}'")  # pragma: no cover
