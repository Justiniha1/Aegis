import shutil
from pathlib import Path
import typer

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


_DATABASE_CONNECTION_YAML = """\
# Connection profiles — names here appear in the dashboard's Active Environment selector.
# Secrets must use ${ENV_VAR} references (never hard-code passwords here).
# Run `comet push` to upload these to the dashboard.
dev:
  type: sqlite
  path: ./data/your_database.db

# Snowflake example (uncomment + fill in; password MUST be a ${ENV} reference):
# warehouse:
#   type: snowflake
#   account: myorg-myacct        # org-account locator only — no .snowflakecomputing.com
#   username: ${SNOWFLAKE_USER}
#   password: ${SNOWFLAKE_PASSWORD}
#   database: ANALYTICS
#   warehouse: COMPUTE_WH
#   role: TRANSFORMER
"""


def init_cmd():
    """Scaffold the comet/ project directory with starter config files."""
    comet_dir = Path("comet")

    if comet_dir.exists():
        typer.echo("[comet] comet/ directory already exists. Nothing to do.")
        raise typer.Exit()

    comet_dir.mkdir()

    shutil.copy(TEMPLATES_DIR / "test_definitions.yaml", comet_dir / "test_definitions.yaml")
    (comet_dir / "database_connection.yaml").write_text(_DATABASE_CONNECTION_YAML)

    env_path = Path(".env")
    if not env_path.exists():
        env_path.write_text("COMET_API_KEY=paste-your-api-key-here\n")
        typer.echo("[comet] Created .env — add your API key (find it in Settings on the dashboard).")

    typer.echo("[comet] Project initialized. Next steps:")
    typer.echo("  1. Add COMET_API_KEY to .env")
    typer.echo("  2. Edit comet/database_connection.yaml with your connection profiles")
    typer.echo("  3. Edit comet/test_definitions.yaml with your tests")
    typer.echo("  4. Run 'comet push' to sync tests and profiles to the dashboard")
