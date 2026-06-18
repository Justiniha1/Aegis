import typer
from cli.config import load_config
from cli.api_client import CometClient


def status_cmd(
    limit: int = typer.Option(5, "--limit", "-n", help="Number of recent runs to show"),
):
    """Print recent run history."""
    cfg = load_config()
    client = CometClient(api_url=cfg["api_url"], api_key=cfg["api_key"])

    try:
        runs = client.get(f"/api/v1/runs?limit={limit}")
    except Exception as e:
        typer.echo(f"[comet] Could not fetch run history: {e}")
        raise typer.Exit(1)

    if not runs:
        typer.echo("[comet] No runs yet. Try 'comet run' to trigger your first run.")
        return

    typer.echo(f"{'ID':>5}  {'STATUS':<10}  {'PROFILE':<15}  {'TESTS':>8}  {'STARTED'}")
    typer.echo("-" * 60)
    for r in runs:
        tests = f"{r['completed_tests']}/{r['total_tests']}"
        started = r.get("started_at", "")[:19].replace("T", " ")
        typer.echo(f"{r['id']:>5}  {r['status']:<10}  {r['profile']:<15}  {tests:>8}  {started}")
