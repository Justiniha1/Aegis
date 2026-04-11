import json
import os

import requests


def _sanitize(data):
    """Convert numpy/pandas scalar types to native Python before JSON serialization.
    Numpy scalars expose a .item() method that returns the equivalent Python type."""
    return json.loads(json.dumps(data, default=lambda x: x.item() if hasattr(x, "item") else str(x)))

# Set these environment variables to enable dashboard reporting:
#   DQF_API_URL=http://localhost:8000
#   DQF_API_KEY=<key returned when you registered your client>
_API_URL = os.getenv("DQF_API_URL", "").rstrip("/")
_API_KEY = os.getenv("DQF_API_KEY", "")


def send_to_dashboard(results: list[dict], run_timestamp: str) -> bool:
    """
    POST test results to the Dashboard API.
    Returns True on success, False if unconfigured or on any error.
    Falls back silently — a missing/unreachable API never breaks the engine.
    """
    if not _API_URL or not _API_KEY:
        return False

    try:
        resp = requests.post(
            f"{_API_URL}/api/v1/results",
            json=_sanitize({"results": results, "run_timestamp": run_timestamp}),
            headers={"X-API-Key": _API_KEY},
            timeout=10,
        )
        resp.raise_for_status()
        stored = resp.json().get("stored", "?")
        print(f"\nDashboard API: {stored} results sent to {_API_URL}")
        return True
    except requests.exceptions.ConnectionError:
        print(f"\n[warn] Dashboard API unreachable at {_API_URL} — results saved locally only")
    except requests.exceptions.HTTPError as e:
        print(f"\n[warn] Dashboard API returned {e.response.status_code}: {e.response.text}")
    except Exception as e:
        print(f"\n[warn] Could not send results to Dashboard API: {e}")

    return False
