"""Shared SlowAPI Limiter instance.

Import this limiter into any router that needs rate limiting.
The key function uses the X-Api-Key header so each client's
quota is tracked independently (not by IP).
"""
import os

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def _api_key_or_ip(request: Request) -> str:
    """Use X-Api-Key header as the rate-limit key; fall back to IP."""
    return (
        request.headers.get("x-api-key")
        or request.headers.get("X-Api-Key")
        or get_remote_address(request)
    )


# Limit and window are configurable via env vars with safe defaults.
# RATE_LIMIT_RUNS: max requests per window (default 10)
# RATE_LIMIT_WINDOW: window size in seconds (default 60)
RATE_LIMIT_RUNS = int(os.getenv("RATE_LIMIT_RUNS", "10"))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))

# Pre-built limit string consumed by @limiter.limit() in routers/runs.py
RUNS_LIMIT_STRING = f"{RATE_LIMIT_RUNS}/{RATE_LIMIT_WINDOW}second"

limiter = Limiter(key_func=_api_key_or_ip)
