from pathlib import Path
import typer
from cli.config import load_config
from cli.api_client import AegisClient


def push_cmd():
    """Upload local test_definitions.yaml and database_connection.yaml to the dashboard."""
    cfg = load_config()
    client = AegisClient(api_url=cfg["api_url"], api_key=cfg["api_key"])

    # --- Push test definitions ---
    yaml_path = Path("aegis") / "test_definitions.yaml"
    if not yaml_path.exists():
        typer.echo("[aegis] aegis/test_definitions.yaml not found. Run 'aegis init' first.")
        raise typer.Exit(1)
    try:
        result = client.post("/api/v1/tests/sync", json={"yaml_content": yaml_path.read_text(encoding="utf-8")})
        typer.echo(
            f"[aegis] Tests pushed.   created={result.get('created', 0)} "
            f"updated={result.get('updated', 0)} "
            f"deleted={result.get('deleted', 0)} "
            f"unchanged={result.get('unchanged', 0)}"
        )
    except Exception as e:
        typer.echo(f"[aegis] Push failed (tests): {e}")
        raise typer.Exit(1)

    # --- Push connection profiles (upload the whole YAML; skip if absent) ---
    conn_path = Path("aegis") / "database_connection.yaml"
    if conn_path.exists():
        try:
            res = client.post("/api/v1/profiles/sync", json={"yaml_content": conn_path.read_text(encoding="utf-8")})
            names = res.get("profiles", []) if isinstance(res, dict) else []
            typer.echo(f"[aegis] Profiles synced. {len(names)} profile(s): {', '.join(names)}")
        except Exception as e:
            typer.echo(f"[aegis] Could not sync profiles: {e}")
