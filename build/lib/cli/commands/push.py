from pathlib import Path
from urllib.parse import quote_plus
import requests
import yaml
import typer
from cli.config import load_config
from cli.api_client import AegisClient


def _profile_to_url(name: str, profile: dict) -> tuple[str, str] | None:
    """Return (connection_url, db_type) from a profile dict, or None if not buildable."""
    if "connection_url" in profile:
        return profile["connection_url"], profile.get("type", "unknown")

    db_type = profile.get("type", "").lower()

    if db_type == "sqlite":
        path = profile.get("path", "")
        if not Path(path).is_absolute():
            typer.echo(
                f"[aegis] Profile '{name}': SQLite with a relative path cannot be resolved "
                f"for the server — add a 'connection_url' field (e.g. sqlite:////app/data/my.db). Skipping."
            )
            return None
        return f"sqlite:///{path}", "sqlite"

    user = quote_plus(str(profile.get("username", "")))
    password = quote_plus(str(profile.get("password", "")))
    host = profile.get("host", "localhost")
    database = profile.get("database", "")

    if db_type in ("postgresql", "postgres"):
        port = profile.get("port", 5432)
        return f"postgresql://{user}:{password}@{host}:{port}/{database}", "postgresql"

    if db_type == "mysql":
        port = profile.get("port", 3306)
        return f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}", "mysql"

    typer.echo(f"[aegis] Profile '{name}': unsupported type '{db_type}' without connection_url. Skipping.")
    return None


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

    # --- Push connection profiles (optional — skip if file absent) ---
    conn_path = Path("aegis") / "database_connection.yaml"
    if not conn_path.exists():
        return

    try:
        raw = yaml.safe_load(conn_path.read_text(encoding="utf-8")) or {}
    except Exception as e:
        typer.echo(f"[aegis] Could not parse database_connection.yaml: {e}")
        return

    profiles = {k: v for k, v in raw.items() if isinstance(v, dict)}
    if not profiles:
        return

    created = skipped = errors = 0
    for name, profile in profiles.items():
        result = _profile_to_url(name, profile)
        if result is None:
            errors += 1
            continue
        connection_url, db_type = result
        try:
            client.post("/api/v1/profiles", json={"name": name, "connection_url": connection_url, "db_type": db_type})
            created += 1
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 409:
                skipped += 1  # already exists — not an error
            else:
                typer.echo(f"[aegis] Profile '{name}': push failed — {e}")
                errors += 1
        except Exception as e:
            typer.echo(f"[aegis] Profile '{name}': push failed — {e}")
            errors += 1

    typer.echo(f"[aegis] Profiles pushed. created={created} skipped={skipped} (already exists) errors={errors}")
