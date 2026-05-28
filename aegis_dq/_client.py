"""Internal HTTP client for aegis_dq public API.

Never import this from user code. Use run_checks() instead.
"""
from __future__ import annotations

import os
import time
import requests


class AegisAPIClient:
    """Thin HTTP wrapper that reads credentials from environment variables.

    Constructor params override env vars when provided (useful for testing).
    """

    DEFAULT_POLL_INTERVAL = 5   # seconds
    DEFAULT_TIMEOUT = 30        # seconds per request

    def __init__(
        self,
        api_url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self._base = (api_url or os.getenv("AEGIS_API_URL", "")).rstrip("/")
        self._key = api_key or os.getenv("AEGIS_API_KEY", "")
        if not self._base:
            raise ValueError(
                "AEGIS_API_URL is required. Set the environment variable or pass api_url=."
            )
        if not self._key:
            raise ValueError(
                "AEGIS_API_KEY is required. Set the environment variable or pass api_key=."
            )
        self._headers = {"X-Api-Key": self._key}

    def trigger_run(self, profile: str, type_filter: list[str] | None = None) -> int:
        """POST /api/v1/runs — returns run_id (int)."""
        payload: dict = {"profile": profile}
        if type_filter is not None:
            payload["type_filter"] = type_filter
        resp = requests.post(
            f"{self._base}/api/v1/runs",
            json=payload,
            headers=self._headers,
            timeout=self.DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()["run_id"]

    def get_run(self, run_id: int) -> dict:
        """GET /api/v1/runs/{run_id} — returns the run dict."""
        resp = requests.get(
            f"{self._base}/api/v1/runs/{run_id}",
            headers=self._headers,
            timeout=self.DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()

    def wait_for_run(
        self,
        run_id: int,
        poll_interval: int = DEFAULT_POLL_INTERVAL,
        max_wait_seconds: int | None = None,
    ) -> dict:
        """Poll GET /api/v1/runs/{run_id} until status is COMPLETE or FAILED.

        Args:
            run_id:           Run ID to poll.
            poll_interval:    Seconds between polls (default: 5).
            max_wait_seconds: Hard deadline in seconds. Raises TimeoutError
                              when elapsed time exceeds this value and the run
                              has not yet reached a terminal state. None = no deadline.

        Returns:
            The final run dict.

        Raises:
            TimeoutError: When max_wait_seconds is set and the deadline is exceeded.
        """
        deadline = (
            time.monotonic() + max_wait_seconds if max_wait_seconds is not None else None
        )
        while True:
            run = self.get_run(run_id)
            status = run.get("status")
            if status in ("COMPLETE", "FAILED"):
                return run
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Run {run_id} did not reach a terminal state within {max_wait_seconds}s"
                )
            time.sleep(poll_interval)
