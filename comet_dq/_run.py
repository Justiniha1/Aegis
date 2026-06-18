"""comet_dq._run — core run_checks() callable.

This is the only module clients should call directly. Everything else is internal.
"""
from __future__ import annotations

from typing import Any

from comet_dq._client import CometAPIClient


class CometDQChecksFailed(Exception):
    """Raised by run_checks() when one or more data-quality checks fail.

    Airflow treats any raised exception as a task failure, so this exception
    automatically blocks downstream tasks.

    Attributes:
        run_id:  The integer run ID on the Comet server.
        profile: The connection profile that was run.
        reason:  Human-readable failure reason from the server.
    """

    def __init__(self, run_id: int, profile: str, reason: str) -> None:
        self.run_id = run_id
        self.profile = profile
        self.reason = reason
        super().__init__(
            f"Comet DQ checks failed for profile '{profile}' "
            f"(run_id={run_id}): {reason}"
        )


class CometDQRunTimeout(Exception):
    """Raised by run_checks() when the run has not reached a terminal state
    within the max_wait_seconds deadline.

    Attributes:
        profile:          The connection profile that was run.
        run_id:           The integer run ID on the Comet server.
        max_wait_seconds: The deadline that was exceeded, in seconds.
    """

    def __init__(self, profile: str, run_id: int, max_wait_seconds: int) -> None:
        self.profile = profile
        self.run_id = run_id
        self.max_wait_seconds = max_wait_seconds
        super().__init__(
            f"Comet DQ run for profile '{profile}' (run_id={run_id}) "
            f"did not complete within {max_wait_seconds}s"
        )


def run_checks(
    profile: str = "default",
    *,
    type_filter: list[str] | None = None,
    poll_interval: int = 5,
    api_url: str | None = None,
    api_key: str | None = None,
    max_wait_seconds: int | None = None,
) -> dict[str, Any]:
    """Trigger a data-quality run and wait for it to complete.

    The API key is read from the COMET_API_KEY environment variable by default.
    The API URL is fixed (the hosted Comet endpoint, baked into the SDK) and is not
    configurable. Pass ``api_key`` directly to override the env var (useful in tests or
    when the key comes from an Airflow Variable); ``api_url`` is an internal/testing override.

    Args:
        profile:          Connection profile name to run (default: "default").
        type_filter:      Optional list of test types to run (e.g. ["null_check"]).
                          None means all enabled tests.
        poll_interval:    Seconds between status polls (default: 5).
        api_url:          Internal/testing override for the (fixed) hosted API URL.
        api_key:          Override the COMET_API_KEY env var.
        max_wait_seconds: Optional hard deadline in seconds. Raises CometDQRunTimeout
                          if the run has not reached a terminal state within this
                          deadline. None (default) polls indefinitely.

    Returns:
        The final run dict from the Comet API (contains id, status,
        total_tests, completed_tests, error, etc.).

    Raises:
        CometDQChecksFailed: When the run completes with status "FAILED".
        CometDQRunTimeout:   When max_wait_seconds is set and the deadline is exceeded.
        ValueError:          When credentials are missing.
        requests.HTTPError:  When the API returns a 4xx or 5xx response.
    """
    client = CometAPIClient(api_url=api_url, api_key=api_key)
    run_id = client.trigger_run(profile=profile, type_filter=type_filter)

    try:
        run = client.wait_for_run(
            run_id=run_id, poll_interval=poll_interval, max_wait_seconds=max_wait_seconds
        )
    except TimeoutError:
        raise CometDQRunTimeout(
            profile=profile, run_id=run_id, max_wait_seconds=max_wait_seconds
        )

    if run.get("status") == "FAILED":
        error = run.get("error") or {}
        reason = error.get("reason") or "unknown error"
        raise CometDQChecksFailed(run_id=run_id, profile=profile, reason=reason)

    return run
