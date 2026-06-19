import typer

app = typer.Typer(
    name="comet",
    help="Comet DQ — data quality from the command line.",
    no_args_is_help=True,
)

from cli.commands.init import init_cmd
from cli.commands.push import push_cmd
from cli.commands.pull import pull_cmd
from cli.commands.run_cmd import run_cmd
from cli.commands.status import status_cmd
from cli.commands.dbt_cmd import dbt_app

app.command("init")(init_cmd)
app.command("push")(push_cmd)
app.command("pull")(pull_cmd)
app.command("run")(run_cmd)
app.command("status")(status_cmd)
app.add_typer(dbt_app, name="dbt")

if __name__ == "__main__":
    app()
