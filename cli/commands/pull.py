from pathlib import Path
import typer
from cli.config import load_config
from cli.api_client import AegisClient


def pull_cmd():
    """Download current test definitions from the dashboard to local test_definitions.yaml."""
    cfg = load_config()
    client = AegisClient(api_url=cfg["api_url"], api_key=cfg["api_key"])
    try:
        yaml_content = client.get_text("/api/v1/tests/yaml")
    except Exception as e:
        typer.echo(f"[aegis] Pull failed: {e}")
        raise typer.Exit(1)
    yaml_path = Path("aegis") / "test_definitions.yaml"
    yaml_path.write_text(yaml_content, encoding="utf-8")
    typer.echo(f"[aegis] Pulled latest test definitions to {yaml_path}")
