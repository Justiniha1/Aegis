"""Failure alerting for scheduled runs.

Notifies a client when one of their SCHEDULED runs needs attention: the run FAILED to
execute, or it COMPLETEd but found failing/error tests. Manual (UI-triggered) runs are
not alerted — the operator is watching those live.

Channels: webhook (Slack-compatible / generic, shipping now). Email via Resend is a
planned addition; send_webhook is the only delivery path wired today. All delivery is
fail-safe: a broken channel logs a warning and never affects run execution.
"""

import logging
from typing import Optional

import requests

from dashboard_api import models
from dashboard_api.database import SessionLocal

logger = logging.getLogger(__name__)

_WEBHOOK_TIMEOUT = 10  # seconds


def build_alert_message(client_name: str, run, failed_count: int, error_count: int) -> Optional[str]:
    """Return an alert message if this terminal run warrants one, else None.

    Alerts on a FAILED run, or a COMPLETE run with any failing/error tests. A clean
    COMPLETE (all passed/skipped) and any non-terminal status produce no alert.
    """
    if run.status == "FAILED":
        return (
            f"Comet: scheduled run #{run.id} for '{client_name}' FAILED to run "
            f"(profile '{run.profile}'): {run.error_reason or 'unknown error'}"
        )
    if run.status == "COMPLETE" and (failed_count or error_count):
        return (
            f"Comet: scheduled run #{run.id} for '{client_name}' (profile '{run.profile}') "
            f"found data quality issues — {failed_count} failed, {error_count} error(s) "
            f"across {run.total_tests} tests."
        )
    return None


def send_webhook(url: str, message: str, run) -> bool:
    """POST the alert to a webhook URL. Slack-compatible ('text') plus structured fields
    for generic consumers. Fail-safe: returns False on any error, never raises."""
    payload = {
        "text": message,
        "run_id": run.id,
        "status": run.status,
        "profile": run.profile,
    }
    try:
        resp = requests.post(url, json=payload, timeout=_WEBHOOK_TIMEOUT)
        resp.raise_for_status()
        return True
    except Exception as e:
        logger.warning("alert webhook for run_id=%s failed: %s", run.id, e)
        return False


def maybe_send_run_alert(run_id: int, client_id: int) -> None:
    """Evaluate a terminal scheduled run and deliver a failure alert to the client's
    configured channel(s). Opens its own session; never raises."""
    db = SessionLocal()
    try:
        run = db.query(models.Run).filter(models.Run.id == run_id).first()
        client = db.query(models.Client).filter(models.Client.id == client_id).first()
        if run is None or client is None:
            return

        failed = (
            db.query(models.TestResult)
            .filter(models.TestResult.run_id == run_id, models.TestResult.status == "FAILED")
            .count()
        )
        errored = (
            db.query(models.TestResult)
            .filter(models.TestResult.run_id == run_id, models.TestResult.status == "ERROR")
            .count()
        )

        message = build_alert_message(client.name, run, failed, errored)
        if not message:
            return

        webhook = getattr(client, "alert_webhook_url", None)
        if webhook:
            send_webhook(webhook, message, run)
        # Email via Resend will be added here once RESEND_API_KEY is configured.
    except Exception as e:  # pragma: no cover - alerting must never break the run
        logger.warning("maybe_send_run_alert failed for run_id=%s: %s", run_id, e)
    finally:
        db.close()
