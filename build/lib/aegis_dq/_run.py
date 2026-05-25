"""aegis_dq._run — core run_checks() callable.

This is the only module clients should call directly. Everything else is internal.
"""
from __future__ import annotations

from typing import Any

from aegis_dq._client import AegisAPIClient


class AegisDQChecksFailed(Exception):
    """Raised by run_checks() when one or more data-quality checks fail.

    Airflow treats any raised exception as a task failure, so this exception
    automatically blocks downstream tasks.

    Attributes:
        run_id:  The integer run ID on the Aegis server.
        profile: The connection profile that was run.
        reason:  Human-readable failure reason from the server.
    """

    def __init__(self, run_id: int, profile: str, reason: str) -> None:
        self.run_id = run_id
        self.profile = profile
        self.reason = reason
        super().__init__(
            f"Aegis DQ checks failed for profile '{profile}' "
            f"(run_id={run_id}): {reason}"
        )


def run_checks(
    profile: str = "default",
    *,
    type_filter: list[str] | None = None,
    poll_interval: int = 5,
    api_url: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Trigger a data-quality run and wait for it to complete.

    Credentials are read from environment variables by default:
      - AEGIS_API_URL  — base URL of the Aegis dashboard API
      - AEGIS_API_KEY  — API key issued to your client account

    Override credentials by passing ``api_url`` and ``api_key`` directly
    (useful in tests or when credentials come from Airflow Variables).

    Args:
        profile:       Connection profile name to run (default: "default").
        type_filter:   Optional list of test types to run (e.g. ["null_check"]).
                       None means all enabled tests.
        poll_interval: Seconds between status polls (default: 5).
        api_url:       Override AEGIS_API_URL env var.
        api_key:       Override AEGIS_API_KEY env var.

    Returns:
        The final run dict from the Aegis API (contains id, status,
        total_tests, completed_tests, error, etc.).

    Raises:
        AegisDQChecksFailed: When the run completes with status "FAILED".
        ValueError:          When credentials are missing.
        requests.HTTPError:  When the API returns a 4xx or 5xx response.
    """
    client = AegisAPIClient(api_url=api_url, api_key=api_key)
    run_id = client.trigger_run(profile=profile, type_filter=type_filter)
    run = client.wait_for_run(run_id=run_id, poll_interval=poll_interval)

    if run.get("status") == "FAILED":
        error = run.get("error") or {}
        reason = error.get("reason") or "unknown error"
        raise AegisDQChecksFailed(run_id=run_id, profile=profile, reason=reason)

    return run
