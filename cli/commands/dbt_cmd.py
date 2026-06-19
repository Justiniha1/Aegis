from datetime import datetime, timezone
from typing import Optional

import typer

from cli.api_client import CometClient
from cli.config import load_config
from cli.dbt.artifacts import DbtArtifactsError, load_artifacts, resolve_target_dir
from cli.dbt.translator import translate

dbt_app = typer.Typer(
    name="dbt",
    help="Publish dbt test results to your Comet dashboard.",
    no_args_is_help=True,
)


@dbt_app.command("publish")
def publish_cmd(
    target_dir: Optional[str] = typer.Option(
        None, "--target-dir", help="Path to the dbt target/ directory (default: ./target)."
    ),
    project_dir: Optional[str] = typer.Option(
        None, "--project-dir", help="dbt project root; artifacts read from <project-dir>/target."
    ),
):
    """Read dbt artifacts and publish test outcomes to Comet under the 'dbt' profile."""
    cfg = load_config()

    target = resolve_target_dir(target_dir, project_dir)
    try:
        run_results, manifest = load_artifacts(target)
    except DbtArtifactsError as e:
        typer.echo(f"[comet] {e}")
        raise typer.Exit(1)

    results = translate(run_results, manifest)
    if not results:
        typer.echo(f"[comet] No dbt test results found in {target}. Nothing to publish.")
        raise typer.Exit(0)

    client = CometClient(api_url=cfg["api_url"], api_key=cfg["api_key"])
    payload = {
        "results": results,
        "run_profile": "dbt",
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
    }
    try:
        resp = client.post("/api/v1/results", json=payload)
    except Exception as e:
        typer.echo(f"[comet] Failed to publish results: {e}")
        raise typer.Exit(1)

    stored = resp.get("stored", len(results))
    typer.echo(
        f"[comet] Published {stored} dbt test result(s) to your dashboard (profile: dbt)."
    )
