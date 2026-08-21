"""Typer command model for the centralized Monotools framework."""

from pathlib import Path
import os
import subprocess
import sys
import threading

import typer
from rich.console import Console
from rich.table import Table

from monotools.apps import AppDefinition, AppDefinitionError, ROOT, discover_apps, get_app
from monotools.lifecycle import LifecycleError, build_app, validate_app, validate_dist
from monotools.ui import run_ui_check
from monotools.watch import watch_frontend


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


def _run_bootstrap(command: list[str], recovery: str) -> None:
    """Run one locked dependency operation with an actionable recovery path."""
    completed = subprocess.run(command, cwd=ROOT, check=False)
    if completed.returncode:
        raise LifecycleError(
            f"{' '.join(command)} failed ({completed.returncode}). {recovery}"
        )


@app.command()
def bootstrap() -> None:
    """Verify Node 22 and restore the locked Python and npm environments."""
    try:
        version = subprocess.run(
            ["node", "--version"], cwd=ROOT, check=False, text=True, capture_output=True
        )
    except FileNotFoundError:
        _fail("Node 22 is required; install Node 22, then run python manage.py bootstrap.")
        return
    if version.returncode or not version.stdout.startswith("v22."):
        actual = version.stdout.strip() or version.stderr.strip() or "not available"
        _fail(f"Node 22 is required (found {actual}); install Node 22, then rerun bootstrap.")
        return
    try:
        _run_bootstrap(
            ["uv", "sync", "--locked"],
            "Restore or update uv.lock with uv lock, then rerun bootstrap.",
        )
        _run_bootstrap(
            ["npm", "ci"],
            "Verify package-lock.json and npm registry access, then rerun bootstrap.",
        )
        _run_bootstrap(
            ["node_modules/.bin/playwright", "install", "chromium"],
            "Install Chromium with node_modules/.bin/playwright install chromium, then rerun bootstrap. "
            "If the download is blocked, restore network access for the Playwright browser download.",
        )
    except (FileNotFoundError, LifecycleError) as error:
        _fail(error)
    console.print(f"[bold green]Bootstrap complete[/] (Node {version.stdout.strip()})")


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
def status() -> None:
    """Show the organization and artifact health of every discovered app."""
    table = Table("App", "Title", "Source", "README", "Data", "Dist")
    try:
        definitions = discover_apps()
    except AppDefinitionError as error:
        _fail(error)
    for definition in definitions:
        source = all(
            (definition.directory / artifact.source).is_file()
            for artifact in definition.artifacts
        )
        readme = (definition.directory / "README.md").is_file()
        data = (definition.directory / "data").is_dir()
        dist = all(
            (definition.dist_directory / artifact.output).is_file()
            for artifact in definition.artifacts
        )
        table.add_row(
            definition.name,
            definition.title,
            "[green]ok[/]" if source else "[red]missing[/]",
            "[green]ok[/]" if readme else "[red]missing[/]",
            "[green]ok[/]" if data else "—",
            "[green]built[/]" if dist else "[yellow]pending[/]",
        )
    console.print(table)
    console.print(f"{len(definitions)} managed app(s); run [bold]manage.py check[/] for deep validation.")


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


@app.command("ui-check")
def ui_check(name: str = typer.Argument(..., help="Application name.")) -> None:
    """Build, serve, and run browser verification for one application."""
    try:
        definition = _select_app(name)
        artifacts = run_ui_check(definition)
    except (AppDefinitionError, LifecycleError) as error:
        _fail(error)
    console.print(
        f"[bold green]UI checks passed[/] {name} "
        f"(artifacts: {artifacts.relative_to(ROOT)})"
    )


@app.command()
def serve(
    name: str | None = typer.Argument(None, help="Application name."),
    host: str = typer.Option("127.0.0.1"),
    port: int = typer.Option(8000, min=1, max=65535),
    user: str | None = typer.Option(None, "--user", help="Unix user for Worminal terminal processes."),
    watch: bool = typer.Option(False, "--watch", help="Rebuild frontend artifacts when their inputs change."),
) -> None:
    """Build and serve an application through its FastAPI service."""
    try:
        definition = _select_app(name)
        if user is not None and definition.name != "worminal":
            raise LifecycleError("--user is available only when serving worminal.")
        build_app(definition)
        validate_dist(definition)
    except (AppDefinitionError, LifecycleError) as error:
        _fail(error)
    if watch:
        threading.Thread(target=watch_frontend, args=(definition, console.print),
            daemon=True, name=f"{definition.name}-frontend-watch").start()
    subprocess.run(
        [sys.executable, "-m", "uvicorn", definition.module + ":app", "--host", host, "--port", str(port)],
        cwd=ROOT, env=os.environ | ({"WORMINAL_SHELL_USER": user} if user else {}),
        check=False,
    )
