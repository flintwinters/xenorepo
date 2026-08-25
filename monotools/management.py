"""Typer-native building blocks for application managers."""

from dataclasses import dataclass
from pathlib import Path

import typer
from rich.console import Console

from monotools.apps import AppDefinition, AppDefinitionError, load_app
from monotools.lifecycle import (
    LifecycleError,
    build_app,
    run_test_suite,
    serve_app,
    validate_app,
    validate_dist,
)
from monotools.ui import run_ui_check


console = Console()


@dataclass(frozen=True)
class PythonSuite:
    """One app-owned unittest discovery root."""

    path: Path


@dataclass(frozen=True)
class BrowserSuite:
    """One app-owned browser suite and the minimum facts it must prove."""

    path: Path
    proof_kinds: frozenset[str] = frozenset({"acceptance"})
    viewports: frozenset[str] = frozenset({"wide-viewport-chromium", "narrow-viewport-chromium"})
    input_modalities: frozenset[str] = frozenset()


@dataclass(frozen=True)
class ApplicationManager:
    """Typed public contract exported by every application manager."""

    app: typer.Typer
    definition: AppDefinition
    python_suite: PythonSuite
    browser_suite: BrowserSuite | None = None


def _owned_path(definition: AppDefinition, declared: str | Path, *, kind: str) -> Path:
    raw = Path(declared)
    if raw.is_absolute() or ".." in raw.parts:
        raise AppDefinitionError(f"{definition.name} {kind} path must be app-owned and relative: {raw}")
    resolved = (definition.directory / raw).resolve()
    tests_root = (definition.directory / "tests").resolve()
    if not resolved.is_relative_to(tests_root):
        raise AppDefinitionError(f"{definition.name} {kind} path must be beneath tests/: {raw}")
    return resolved


def create_cli(help: str) -> typer.Typer:
    """Create an unopinionated manager without repository discovery or lifecycle policy."""
    return typer.Typer(no_args_is_help=True, help=help)


def resolve_local_app(manage_file: str | Path) -> AppDefinition:
    """Load the application declared beside a manager file."""
    return load_app(Path(manage_file).resolve().parent)


def _workspace_for(definition: AppDefinition) -> Path:
    """Resolve the nearest Python project containing an application."""
    for directory in (definition.directory, *definition.directory.parents):
        if (directory / "pyproject.toml").is_file():
            return directory
    raise AppDefinitionError(
        f"{definition.directory} is not contained by a project with pyproject.toml"
    )


def _fail(error: Exception) -> None:
    console.print(f"[bold red]Error:[/] {error}")
    raise typer.Exit(1)


def create_app_manager(manage_file: str | Path, tests: str | Path,
    ui_suite: str | Path | None = None, include_serve: bool = True,
    *, proof_kinds: frozenset[str] = frozenset({"acceptance"}),
    viewports: frozenset[str] = frozenset({"wide-viewport-chromium", "narrow-viewport-chromium"}),
    input_modalities: frozenset[str] = frozenset()) -> ApplicationManager:
    """Create the standard lifecycle CLI for one metadata-declared application."""
    definition = resolve_local_app(manage_file)
    workspace = _workspace_for(definition)
    test_suite = _owned_path(definition, tests, kind="Python suite")
    browser_path = (_owned_path(definition, ui_suite, kind="browser suite")
        if ui_suite is not None else None)
    app = create_cli(f"Build, validate, test, and run {definition.title}.")

    @app.command()
    def build() -> None:
        """Compile the frontend into the local dist directory."""
        try:
            build_app(definition, workspace)
            validate_dist(definition)
        except LifecycleError as error:
            _fail(error)
        console.print(f"[green]Built[/] {definition.name} -> {definition.dist_directory}")

    @app.command()
    def check() -> None:
        """Validate metadata, sources, imports, and the production build."""
        try:
            validate_app(definition, workspace)
            build_app(definition, workspace)
            validate_dist(definition)
        except LifecycleError as error:
            _fail(error)
        console.print(f"[bold green]Checks passed[/] {definition.name}")

    @app.command()
    def test() -> None:
        """Run this application's curated Python suite."""
        result = run_test_suite(workspace, test_suite)
        if result:
            raise typer.Exit(result)
        console.print(f"[bold green]Tests passed[/] {definition.name}")

    if browser_path is not None:
        @app.command("ui-check")
        def ui_check() -> None:
            """Build, serve, and run this application's browser suite."""
            try:
                artifacts = run_ui_check(definition, workspace, browser_path)
            except LifecycleError as error:
                _fail(error)
            console.print(f"[bold green]UI checks passed[/] {definition.name} ({artifacts})")

    if include_serve:
        @app.command()
        def serve(host: str = typer.Option("127.0.0.1"),
            port: int = typer.Option(8000, min=1, max=65535),
            watch: bool = typer.Option(False, "--watch",
                help="Rebuild frontend artifacts when their inputs change.")) -> None:
            """Build and serve this application through FastAPI."""
            try:
                result = serve_app(definition, workspace, host=host, port=port,
                    watch=watch, report=console.print)
            except (AppDefinitionError, LifecycleError) as error:
                _fail(error)
            if result:
                raise typer.Exit(result)

    return ApplicationManager(
        app=app,
        definition=definition,
        python_suite=PythonSuite(test_suite),
        browser_suite=(BrowserSuite(browser_path, proof_kinds, viewports, input_modalities)
            if browser_path is not None else None),
    )


def create_app_cli(manage_file: str | Path, tests: str | Path,
    ui_suite: str | Path | None = None, include_serve: bool = True) -> typer.Typer:
    """Compatibility wrapper; new managers export ``manager`` explicitly."""
    return create_app_manager(manage_file, tests, ui_suite, include_serve).app
