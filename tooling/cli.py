"""Typer command model for the centralized tooling framework."""

from pathlib import Path
import subprocess
import sys

import typer
from rich.console import Console
from rich.table import Table

from tooling.apps import AppDefinition, AppDefinitionError, ROOT, discover_apps, get_app
from tooling.lifecycle import LifecycleError, build_app, validate_app, validate_dist


app = typer.Typer(no_args_is_help=True, help="Build, validate, test, and run repository apps.")
console = Console()


def _fail(error: Exception) -> None:
    console.print(f"[bold red]Error:[/] {error}")
    raise typer.Exit(1)


def _select_app(name: str | None) -> AppDefinition:
    """Resolve an app name or give the operator the available choices."""
    try:
        definitions = discover_apps()
    except AppDefinitionError as error:
        _fail(error)
    if name is None:
        choices = ", ".join(definition.name for definition in definitions) or "none"
        console.print(f"[bold red]Error:[/] choose an application: {choices}")
        console.print("Example: manage.py serve " + definitions[0].name if definitions
            else "Run manage.py list after adding an application.")
        raise typer.Exit(2)
    return get_app(name)


@app.command("list")
def list_apps() -> None:
    """List applications discovered from declarative metadata."""
    table = Table("Name", "Title", "Module")
    try:
        for definition in discover_apps():
            table.add_row(definition.name, definition.title, definition.module)
    except AppDefinitionError as error:
        _fail(error)
    console.print(table)


@app.command()
def build(name: str = typer.Argument(..., help="Application name.")) -> None:
    """Compile an application's frontend into its dist directory."""
    try:
        definition = _select_app(name)
        build_app(definition)
        validate_dist(definition)
    except (AppDefinitionError, LifecycleError) as error:
        _fail(error)
    console.print(f"[green]Built[/] {name} -> {definition.dist_directory.relative_to(ROOT)}")


@app.command()
def check() -> None:
    """Validate metadata, sources, imports, and production builds."""
    try:
        definitions = discover_apps()
        for definition in definitions:
            validate_app(definition)
            build_app(definition)
            validate_dist(definition)
    except (AppDefinitionError, LifecycleError) as error:
        _fail(error)
    console.print(f"[bold green]All checks passed[/] ({len(definitions)} app(s))")


@app.command()
def test() -> None:
    """Run the repository's curated automated test suite."""
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=ROOT,
        check=False,
    )
    if result.returncode:
        raise typer.Exit(result.returncode)
    console.print("[bold green]Tests passed[/]")


@app.command()
def serve(
    name: str | None = typer.Argument(None, help="Application name."),
    host: str = typer.Option("127.0.0.1"),
    port: int = typer.Option(8000, min=1, max=65535),
) -> None:
    """Build and serve an application through its FastAPI service."""
    try:
        definition = _select_app(name)
        build_app(definition)
        validate_dist(definition)
    except (AppDefinitionError, LifecycleError) as error:
        _fail(error)
    subprocess.run(
        [sys.executable, "-m", "uvicorn", definition.module + ":app", "--host", host, "--port", str(port)],
        cwd=ROOT,
        check=False,
    )
