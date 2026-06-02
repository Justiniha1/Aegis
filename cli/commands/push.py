from pathlib import Path
import yaml
import typer
from cli.config import load_config
from cli.api_client import AegisClient
from cli.profiles_sync import parse_yaml_profile, profile_to_payload


def _reconcile_profiles(client, local: dict, confirm, dry_run: bool = False) -> dict:
    """Mirror local YAML profiles to the dashboard. Upsert each local profile (POST is
    idempotent by name); delete remote profiles absent from local after confirmation."""
    remote = client.get("/api/v1/profiles")
    remote_by_name = {p["name"]: p for p in remote}
    summary = {"created": 0, "updated": 0, "deleted": 0, "unchanged": 0, "errors": 0}

    for name, profile in local.items():
        parsed = parse_yaml_profile(name, profile)
        payload, warning = profile_to_payload(name, parsed)
        if warning:
            typer.echo(f"[aegis] WARN: {warning}")
        existed = name in remote_by_name
        if dry_run:
            typer.echo(f"[aegis]   {'update' if existed else 'create'} {name}")
            summary["updated" if existed else "created"] += 1
            continue
        try:
            client.post("/api/v1/profiles", json=payload)
            summary["updated" if existed else "created"] += 1
        except Exception as e:
            typer.echo(f"[aegis] Profile '{name}': push failed - {e}")
            summary["errors"] += 1

    stale = [p for n, p in remote_by_name.items() if n not in local]
    if stale:
        names = ", ".join(p["name"] for p in stale)
        if confirm(f"Delete {len(stale)} dashboard profile(s) not in local YAML ({names})?"):
            for p in stale:
                if dry_run:
                    typer.echo(f"[aegis]   delete {p['name']}")
                    summary["deleted"] += 1
                    continue
                try:
                    client.delete(f"/api/v1/profiles/{p['id']}")
                    summary["deleted"] += 1
                except Exception as e:
                    typer.echo(f"[aegis] Profile '{p['name']}': delete failed - {e}")
                    summary["errors"] += 1
    return summary


def push_cmd(
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview profile changes without applying them"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip the delete confirmation prompt (for CI)"),
):
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

    # --- Push connection profiles (reconciling mirror) ---
    conn_path = Path("aegis") / "database_connection.yaml"
    if not conn_path.exists():
        return

    try:
        raw = yaml.safe_load(conn_path.read_text(encoding="utf-8")) or {}
    except Exception as e:
        typer.echo(f"[aegis] Could not parse database_connection.yaml: {e}")
        return

    # Only treat mappings with a 'type' as profiles - mirrors pull's heuristic so a
    # non-profile block (e.g. settings:) is never pushed as a junk profile.
    local = {k: v for k, v in raw.items() if isinstance(v, dict) and "type" in v}
    if not local:
        return

    def _confirm(prompt: str) -> bool:
        if yes:
            return True
        return typer.confirm(prompt)

    if dry_run:
        typer.echo("[aegis] --dry-run: showing intended changes only")
    summary = _reconcile_profiles(client, local, confirm=_confirm, dry_run=dry_run)
    typer.echo(
        f"[aegis] Profiles pushed. created={summary['created']} updated={summary['updated']} "
        f"deleted={summary['deleted']} errors={summary['errors']}"
    )
