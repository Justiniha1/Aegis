import time
from typing import Optional
import typer
from cli.config import load_config
from cli.api_client import AegisClient

POLL_INTERVAL = 3  # seconds between status polls


def run_cmd(
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Connection profile to run"),
    suite: Optional[str] = typer.Option(None, "--suite", "-s", help="Named test suite to run"),
    no_wait: bool = typer.Option(False, "--no-wait", help="Trigger run and exit without polling"),
):
    """Trigger a data quality run on the Aegis servers."""
    cfg = load_config()
    selected_profile = profile or cfg.get("default_profile", "dev")

    payload = {"profile": selected_profile}
    if suite:
        payload["suite"] = suite

    client = AegisClient(api_url=cfg["api_url"], api_key=cfg["api_key"])

    try:
        resp = client.post("/api/v1/runs", json=payload)
    except Exception as e:
        typer.echo(f"[aegis] Failed to trigger run: {e}")
        raise typer.Exit(1)

    run_id = resp["run_id"]
    typer.echo(f"[aegis] Run #{run_id} triggered (profile: {selected_profile})")

    if no_wait:
        typer.echo(f"[aegis] Track it at: {cfg['api_url'].replace('api.', 'app.')}/dashboard/history")
        return

    typer.echo("[aegis] Waiting for run to complete...")
    while True:
        try:
            status = client.get(f"/api/v1/runs/{run_id}")
        except Exception as e:
            typer.echo(f"[aegis] Status poll failed: {e}")
            raise typer.Exit(1)

        state = status["status"]
        done = status["completed_tests"]
        total = status["total_tests"]
        typer.echo(f"  {state} — {done}/{total} tests", nl=False)
        typer.echo("\r", nl=False)

        if state == "COMPLETE":
            typer.echo(f"\n[aegis] Run #{run_id} complete — {total}/{total} tests passed.")
            return
        if state == "FAILED":
            typer.echo(f"\n[aegis] Run #{run_id} failed: {status.get('error_reason', 'unknown error')}")
            raise typer.Exit(1)

        time.sleep(POLL_INTERVAL)
