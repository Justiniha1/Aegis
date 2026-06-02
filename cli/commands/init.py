import shutil
from pathlib import Path
import typer

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


_DATABASE_CONNECTION_YAML = """\
# Connection profiles — names here appear in the dashboard's Active Environment selector.
# Secrets must use ${ENV_VAR} references (never hard-code passwords here).
# Run `aegis push` to upload these to the dashboard.
dev:
  type: sqlite
  path: ./data/your_database.db
"""


def init_cmd():
    """Scaffold the aegis/ project directory with starter config files."""
    aegis_dir = Path("aegis")

    if aegis_dir.exists():
        typer.echo("[aegis] aegis/ directory already exists. Nothing to do.")
        raise typer.Exit()

    aegis_dir.mkdir()

    shutil.copy(TEMPLATES_DIR / "config.yaml", aegis_dir / "config.yaml")
    shutil.copy(TEMPLATES_DIR / "test_definitions.yaml", aegis_dir / "test_definitions.yaml")
    (aegis_dir / "database_connection.yaml").write_text(_DATABASE_CONNECTION_YAML)

    env_path = Path(".env")
    if not env_path.exists():
        env_path.write_text("AEGIS_API_KEY=paste-your-api-key-here\n")
        typer.echo("[aegis] Created .env — add your API key (find it in Settings on the dashboard).")

    typer.echo("[aegis] Project initialized. Next steps:")
    typer.echo("  1. Add AEGIS_API_KEY to .env")
    typer.echo("  2. Edit aegis/database_connection.yaml with your connection profiles")
    typer.echo("  3. Edit aegis/test_definitions.yaml with your tests")
    typer.echo("  4. Run 'aegis push' to sync tests and profiles to the dashboard")
