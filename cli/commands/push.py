from pathlib import Path
import typer
from cli.config import load_config
from cli.api_client import AegisClient


def push_cmd():
    """Upload local test_definitions.yaml to the dashboard."""
    cfg = load_config()
    yaml_path = Path("aegis") / "test_definitions.yaml"
    if not yaml_path.exists():
        typer.echo("[aegis] aegis/test_definitions.yaml not found. Run 'aegis init' first.")
        raise typer.Exit(1)

    yaml_content = yaml_path.read_text(encoding="utf-8")
    client = AegisClient(api_url=cfg["api_url"], api_key=cfg["api_key"])

    try:
        result = client.post("/api/v1/tests/sync", json={"yaml_content": yaml_content})
        typer.echo(f"[aegis] Pushed. Synced {result.get('synced', '?')} test(s) to dashboard.")
    except Exception as e:
        typer.echo(f"[aegis] Push failed: {e}")
        raise typer.Exit(1)
