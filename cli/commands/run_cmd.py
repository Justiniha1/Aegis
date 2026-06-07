import time
from pathlib import Path
from typing import Optional
import typer
import yaml
from cli.config import load_config
from cli.api_client import AegisClient

POLL_INTERVAL = 3  # seconds between status polls


def _default_profile_from_yaml() -> Optional[str]:
    """Read settings.default_profile from the local aegis/test_definitions.yaml, if set."""
    path = Path("aegis") / "test_definitions.yaml"
    if not path.exists():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return None
    default_profile = (data.get("settings") or {}).get("default_profile")
    return str(default_profile) if default_profile else None


def run_cmd(
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Connection profile to run (defaults to settings.default_profile in aegis/test_definitions.yaml)"),
    suite: Optional[str] = typer.Option(None, "--suite", "-s", help="Named test suite to run"),
    no_wait: bool = typer.Option(False, "--no-wait", help="Trigger run and exit without polling"),
):
    """Trigger a data quality run on the Aegis servers.

    With no --profile, falls back to `settings.default_profile` in the local
    aegis/test_definitions.yaml. If neither is set, the run is not started.
    """
    cfg = load_config()
    selected_profile = profile or _default_profile_from_yaml()
    if not selected_profile:
        typer.echo(
            "[aegis] No profile given and no 'default_profile' set under 'settings' in "
            "aegis/test_definitions.yaml.\n"
            "        Pass --profile <name>, or add:\n"
            "          settings:\n"
            "            default_profile: <name>"
        )
        raise typer.Exit(1)

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
            # COMPLETE means the run finished, not that every test passed — the run
            # dict carries no pass count, so report tests run and point at the dashboard.
            typer.echo(f"\n[aegis] Run #{run_id} complete — {total} tests run. See the dashboard for pass/fail detail.")
            return
        if state == "FAILED":
            typer.echo(f"\n[aegis] Run #{run_id} failed: {status.get('error_reason', 'unknown error')}")
            raise typer.Exit(1)

        time.sleep(POLL_INTERVAL)
