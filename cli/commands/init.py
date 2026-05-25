import shutil
from pathlib import Path
import typer

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"


def init_cmd():
    """Scaffold the aegis/ project directory with starter config files."""
    aegis_dir = Path("aegis")
    profiles_dir = aegis_dir / "profiles"

    if aegis_dir.exists():
        typer.echo("[aegis] aegis/ directory already exists. Nothing to do.")
        raise typer.Exit()

    aegis_dir.mkdir()
    profiles_dir.mkdir()

    shutil.copy(TEMPLATES_DIR / "config.yaml", aegis_dir / "config.yaml")
    shutil.copy(TEMPLATES_DIR / "test_definitions.yaml", aegis_dir / "test_definitions.yaml")

    (profiles_dir / "dev.yaml").write_text("# Dev profile label — add connection in dashboard Settings\nname: dev\n")
    (profiles_dir / "production.yaml").write_text("# Production profile label — add connection in dashboard Settings\nname: production\n")

    env_path = Path(".env")
    if not env_path.exists():
        env_path.write_text("AEGIS_API_KEY=paste-your-api-key-here\n")
        typer.echo("[aegis] Created .env — add your API key (find it in Settings on the dashboard).")

    typer.echo("[aegis] Project initialized. Next steps:")
    typer.echo("  1. Add AEGIS_API_KEY to .env")
    typer.echo("  2. Add your DB connection in the dashboard under Settings -> Connection Profiles")
    typer.echo("  3. Edit aegis/test_definitions.yaml")
    typer.echo("  4. Run 'aegis push' to sync your tests to the dashboard")
