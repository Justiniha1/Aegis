import os
from pathlib import Path
import typer
from ruamel.yaml import YAML
from cli.config import load_config
from cli.api_client import AegisClient

_yaml = YAML()
_yaml.preserve_quotes = True


def _profiles_to_yaml_dict(remote: list[dict]) -> dict:
    """Build {profile_name: {fields...}} from API rows. Secrets become ${secret_env} refs."""
    out = {}
    for p in remote:
        if (p.get("db_type") or "").lower() == "sqlite":
            out[p["name"]] = {"type": "sqlite", "path": p.get("sqlite_path")}
            continue
        entry = {"type": p["db_type"]}
        for f in ("host", "port", "database", "username"):
            if p.get(f) is not None:
                entry[f] = p[f]
        if p.get("secret_env"):
            entry["password"] = "${" + p["secret_env"] + "}"
        out[p["name"]] = entry
    return out


def _readiness_lines(remote: list[dict]) -> list[str]:
    lines = []
    for p in remote:
        env = p.get("secret_env")
        if not env:
            lines.append(f"  {p['name']:<12} {p.get('db_type',''):<10} OK  no secret needed")
        else:
            state = "SET" if os.environ.get(env) else "NOT SET"
            lines.append(f"  {p['name']:<12} {p.get('db_type',''):<10} needs ${env}   [{state}]")
    return lines


def _merge_profiles_into_file(path: Path, desired: dict) -> None:
    """Update profile mappings in place, preserving comments. Adds new, removes absent."""
    if path.exists():
        doc = _yaml.load(path.read_text(encoding="utf-8")) or {}
    else:
        doc = {}
    # remove profiles no longer present (top-level mapping keys that look like profiles)
    for key in list(doc.keys()):
        if isinstance(doc.get(key), dict) and "type" in doc[key] and key not in desired:
            del doc[key]
    # upsert desired
    for name, fields in desired.items():
        if name in doc and isinstance(doc[name], dict):
            doc[name].clear()
            doc[name].update(fields)
        else:
            doc[name] = fields
    with path.open("w", encoding="utf-8") as f:
        _yaml.dump(doc, f)


def pull_cmd(
    yes: bool = typer.Option(False, "--yes", "-y", help="Write without the confirmation prompt"),
):
    """Download test definitions AND connection profiles from the dashboard to local YAML."""
    cfg = load_config()
    client = AegisClient(api_url=cfg["api_url"], api_key=cfg["api_key"])

    # --- Pull test definitions (unchanged behavior) ---
    try:
        yaml_content = client.get_text("/api/v1/tests/yaml")
    except Exception as e:
        typer.echo(f"[aegis] Pull failed: {e}")
        raise typer.Exit(1)
    tests_path = Path("aegis") / "test_definitions.yaml"
    tests_path.write_text(yaml_content, encoding="utf-8")
    typer.echo(f"[aegis] Pulled latest test definitions to {tests_path}")

    # --- Pull connection profiles ---
    try:
        remote = client.get("/api/v1/profiles")
    except Exception as e:
        typer.echo(f"[aegis] Could not pull profiles: {e}")
        return

    desired = _profiles_to_yaml_dict(remote)
    conn_path = Path("aegis") / "database_connection.yaml"
    if not yes:
        typer.echo(f"[aegis] About to update {len(desired)} profile(s) in {conn_path} (comments preserved).")
        if not typer.confirm("Proceed?"):
            typer.echo("[aegis] Skipped profile write.")
            return
    _merge_profiles_into_file(conn_path, desired)
    typer.echo(f"[aegis] Pulled {len(desired)} connection profile(s) to {conn_path}")
    typer.echo("[aegis] Local readiness (set these env vars before running):")
    for line in _readiness_lines(remote):
        typer.echo(line)
