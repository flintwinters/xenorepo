#!/usr/bin/env python3
"""Xenorepo-owned lifecycle aggregation and application mounting."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import subprocess

from rich.console import Console
from rich.table import Table
import typer

from monotools.apps import AppDefinition, AppDefinitionError, load_app
from monotools.browser import run_browser_framework_suite
from monotools.lifecycle import (
    LifecycleError,
    build_app,
    collect_app_status,
    run_test_suite,
    validate_app,
    validate_dist,
)
from monotools.management import ApplicationManager, PythonSuite, create_cli


ROOT = Path(__file__).resolve().parent
APPS_DIRECTORY = ROOT / "apps"
console = Console()


class ManagerError(RuntimeError):
    """Raised when Xenorepo's immediate app-manager inventory is invalid."""


def _visible_directories(apps_directory: Path) -> tuple[Path, ...]:
    if not apps_directory.is_dir():
        return ()
    return tuple(directory for directory in sorted(apps_directory.iterdir())
        if directory.is_dir() and not directory.name.startswith((".", "_")))


def _import_manager(path: Path) -> ApplicationManager:
    module_name = f"xenorepo_app_manager_{path.parent.name}"
    spec = spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ManagerError(f"cannot import app manager: {path}")
    module = module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as error:
        raise ManagerError(f"failed to import app manager {path}: {error}") from error
    manager = getattr(module, "manager", None)
    if not isinstance(manager, ApplicationManager):
        raise ManagerError(f"app manager {path} must export 'manager' as ApplicationManager")
    if manager.definition.directory.resolve() != path.parent.resolve():
        raise ManagerError(f"app manager {path} describes another application")
    if not manager.python_suite.path.is_dir():
        raise ManagerError(f"app manager {path} has no Python suite: {manager.python_suite.path}")
    if manager.browser_suite is not None and not manager.browser_suite.path.is_file():
        raise ManagerError(f"app manager {path} has no browser suite: {manager.browser_suite.path}")
    return manager


def discover_managers(apps_directory: Path = APPS_DIRECTORY
    ) -> tuple[tuple[AppDefinition, ApplicationManager], ...]:
    """Load every immediate visible Xenorepo app and its explicit manager."""
    managers: list[tuple[AppDefinition, ApplicationManager]] = []
    names: set[str] = set()
    for directory in _visible_directories(apps_directory):
        manager_path = directory / "manage.py"
        if not manager_path.is_file():
            raise ManagerError(f"visible app directory has no manage.py: {directory}")
        try:
            definition = load_app(directory)
        except AppDefinitionError as error:
            raise ManagerError(str(error)) from error
        if definition.name in names:
            raise ManagerError(f"duplicate managed app name: {definition.name}")
        names.add(definition.name)
        manager = _import_manager(manager_path)
        if manager.definition != definition:
            raise ManagerError(f"app manager {manager_path} definition does not match app.yaml")
        managers.append((definition, manager))
    suite_paths = [manager.python_suite.path for _, manager in managers]
    if len(suite_paths) != len(set(suite_paths)):
        raise ManagerError("application Python suite paths must be unique")
    return tuple(managers)


def _fail(error: Exception | str) -> None:
    console.print(f"[bold red]Error:[/] {error}")
    raise typer.Exit(1)


def _run_bootstrap(command: list[str], recovery: str) -> None:
    completed = subprocess.run(command, cwd=ROOT, check=False)
    if completed.returncode:
        raise LifecycleError(f"{' '.join(command)} failed ({completed.returncode}). {recovery}")


app = create_cli("Manage Xenorepo and its immediate applications.")
MANAGERS = discover_managers()
for definition, manager in MANAGERS:
    app.add_typer(manager.app, name=definition.name)


@app.command()
def bootstrap() -> None:
    """Verify Node 22 and restore the locked Python, npm, and browser environments."""
    try:
        version = subprocess.run(
            ["node", "--version"], cwd=ROOT, check=False, text=True, capture_output=True
        )
    except FileNotFoundError:
        _fail("Node 22 is required; install Node 22, then run python manage.py bootstrap.")
    if version.returncode or not version.stdout.startswith("v22."):
        actual = version.stdout.strip() or version.stderr.strip() or "not available"
        _fail(f"Node 22 is required (found {actual}); install Node 22, then rerun bootstrap.")
    try:
        _run_bootstrap(["uv", "sync", "--locked"],
            "Restore or update uv.lock with uv lock, then rerun bootstrap.")
        _run_bootstrap(["npm", "ci"],
            "Verify package-lock.json and npm registry access, then rerun bootstrap.")
        _run_bootstrap(["node_modules/.bin/playwright", "install", "chromium"],
            "Restore network access for the Playwright browser download, then rerun bootstrap.")
    except (FileNotFoundError, LifecycleError) as error:
        _fail(error)
    console.print(f"[bold green]Bootstrap complete[/] (Node {version.stdout.strip()})")


@app.command("list")
def list_apps() -> None:
    """List applications explicitly managed by Xenorepo."""
    table = Table("Name", "Title", "Module")
    for definition, _ in MANAGERS:
        table.add_row(definition.name, definition.title, definition.module)
    console.print(table)


@app.command()
def status() -> None:
    """Show source and artifact health for every managed application."""
    table = Table("App", "Title", "Source", "README", "Data", "Dist")
    for definition, _ in MANAGERS:
        health = collect_app_status(definition)
        table.add_row(
            definition.name,
            definition.title,
            "[green]ok[/]" if health["source"] else "[red]missing[/]",
            "[green]ok[/]" if health["readme"] else "[red]missing[/]",
            "[green]ok[/]" if health["data"] else "—",
            "[green]built[/]" if health["dist"] else "[yellow]pending[/]",
        )
    console.print(table)
    console.print(f"{len(MANAGERS)} managed app(s); run [bold]manage.py check[/] for validation.")


@app.command()
def check() -> None:
    """Validate Xenorepo's manager inventory and every application build."""
    try:
        current = discover_managers()
        for definition, _ in current:
            validate_app(definition, ROOT)
            build_app(definition, ROOT)
            validate_dist(definition)
    except (ManagerError, LifecycleError) as error:
        _fail(error)
    console.print(f"[bold green]All checks passed[/] ({len(current)} app(s))")


@app.command()
def test() -> None:
    """Run the curated platform and application regression suite exactly once."""
    suites = (PythonSuite(ROOT / "tests"), *(manager.python_suite for _, manager in MANAGERS))
    for suite in suites:
        result = run_test_suite(ROOT, suite.path)
        if result:
            raise typer.Exit(result)
    browser_result = run_browser_framework_suite(ROOT)
    if browser_result:
        raise typer.Exit(browser_result)
    console.print("[bold green]Tests passed[/]")


if __name__ == "__main__":
    app()
