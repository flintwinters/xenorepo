"""Worminal lifecycle manager with its terminal-user serving policy."""

import typer
from rich.console import Console

from monotools.lifecycle import LifecycleError, serve_app
from monotools.management import create_app_cli, resolve_local_app


app = create_app_cli(
    __file__,
    tests="../../tests",
    ui_suite="../../tests/ui/worminal.spec.js",
    include_serve=False,
)
console = Console()
definition = resolve_local_app(__file__)
workspace = definition.directory.parent.parent


@app.command()
def serve(host: str = typer.Option("127.0.0.1"),
    port: int = typer.Option(8000, min=1, max=65535),
    user: str | None = typer.Option(None, "--user",
        help="Unix user for Worminal terminal processes."),
    watch: bool = typer.Option(False, "--watch",
        help="Rebuild frontend artifacts when their inputs change.")) -> None:
    """Build and serve Worminal with an optional terminal process user."""
    try:
        result = serve_app(
            definition,
            workspace,
            host=host,
            port=port,
            watch=watch,
            environment={"WORMINAL_SHELL_USER": user} if user else None,
            report=console.print,
        )
    except LifecycleError as error:
        console.print(f"[bold red]Error:[/] {error}")
        raise typer.Exit(1) from error
    if result:
        raise typer.Exit(result)


if __name__ == "__main__":
    app()
