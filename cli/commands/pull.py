from pathlib import Path
import typer
from ruamel.yaml import YAML
from cli.config import load_config
from cli.api_client import CometClient


def pull_cmd():
    """Download current test definitions from the dashboard into local test_definitions.yaml.

    Only the `tests` list is replaced with the server's definitions; the local file's
    `engine` and `settings` sections (and comments) are preserved. The server stores only
    test definitions, not those sections, so writing the server YAML verbatim would wipe
    local config. If no local file exists yet, the server YAML is written as-is.
    """
    cfg = load_config()
    client = CometClient(api_url=cfg["api_url"], api_key=cfg["api_key"])
    try:
        server_yaml = client.get_text("/api/v1/tests/yaml")
    except Exception as e:
        typer.echo(f"[comet] Pull failed: {e}")
        raise typer.Exit(1)

    yaml_path = Path("comet") / "test_definitions.yaml"
    yaml = YAML()
    yaml.indent(mapping=2, sequence=2, offset=0)
    yaml.preserve_quotes = True

    server_tests = (yaml.load(server_yaml) or {}).get("tests", [])

    if yaml_path.exists():
        with open(yaml_path, "r", encoding="utf-8") as f:
            doc = yaml.load(f) or {}
        # Replace only the tests; keep the local engine/settings sections and comments.
        doc["tests"] = server_tests
    else:
        # No local file to preserve — write what the server returned.
        doc = yaml.load(server_yaml) or {}

    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(doc, f)
    typer.echo(f"[comet] Pulled latest test definitions to {yaml_path}")
