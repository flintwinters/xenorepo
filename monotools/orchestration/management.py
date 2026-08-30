"""Build Typer-native command surfaces for application managers.

This module turns app definitions and suite declarations into consistent leaf
commands while keeping root orchestration generic and discoverable.
"""

from dataclasses import dataclass
from pathlib import Path

import typer
from rich.console import Console

from monotools.orchestration.apps import AppDefinition, AppDefinitionError, load_app
from monotools.orchestration.environment import (
    EnvironmentConfigurationError, activated_environment,
)
from monotools.orchestration.lifecycle import (
    LifecycleError,
    build_app,
    run_test_suite,
    serve_app,
    validate_app,
    validate_dist,
)
from monotools.orchestration.output import print_error
from monotools.orchestration.ui import run_ui_check


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
    print_error(console, error)
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
    if definition.specification.is_file() and browser_path is None:
        raise AppDefinitionError(
            f"{definition.name} has a product specification but no app-owned browser suite"
        )
    app = create_cli(f"Build, validate, test, and run {definition.title}.")

    @app.command()
    def build() -> None:
        """Compile the frontend into the local dist directory."""
        try:
            with activated_environment(workspace, definition.directory):
                build_app(definition, workspace)
                validate_dist(definition)
        except (EnvironmentConfigurationError, LifecycleError) as error:
            _fail(error)
        console.print(f"[green]Built[/] {definition.name} -> {definition.dist_directory}")

    @app.command()
    def check() -> None:
        """Validate metadata, sources, imports, and the production build."""
        try:
            with activated_environment(workspace, definition.directory):
                validate_app(definition, workspace)
                build_app(definition, workspace)
                validate_dist(definition)
        except (EnvironmentConfigurationError, LifecycleError) as error:
            _fail(error)
        console.print(f"[bold green]Checks passed[/] {definition.name}")

    @app.command()
    def test() -> None:
        """Run this application's curated Python suite."""
        try:
            with activated_environment(workspace, definition.directory):
                result = run_test_suite(workspace, test_suite)
        except EnvironmentConfigurationError as error:
            _fail(error)
        if result:
            raise typer.Exit(result)
        console.print(f"[bold green]Tests passed[/] {definition.name}")

    @app.command("ui-check")
    def ui_check(evidence: bool = typer.Option(False, "--evidence",
            help="Retain trace, video, and HAR evidence for successful checks."),
        update_snapshots: bool = typer.Option(False, "--update-snapshots",
            help="Replace app-owned visual baselines with verified current output.")) -> None:
        """Run universal journeys and any app-owned browser suite."""
        declared = (BrowserSuite(browser_path, proof_kinds, viewports, input_modalities)
            if browser_path is not None else None)
        try:
            with activated_environment(workspace, definition.directory):
                artifacts = run_ui_check(definition, workspace, declared, evidence=evidence,
                    update_snapshots=update_snapshots)
        except (EnvironmentConfigurationError, LifecycleError) as error:
            _fail(error)
        matrix = "wide/narrow route smoke"
        if declared:
            matrix += "; app-owned " + "/".join(sorted(declared.proof_kinds))
        if declared and declared.input_modalities:
            matrix += "; trusted " + "/".join(sorted(declared.input_modalities))
        console.print(f"[bold green]{matrix}[/] {definition.name} ({artifacts})")

    @app.command()
    def verify() -> None:
        """Run this app's checks, Python suite, and complete browser proof matrix."""
        check()
        test()
        ui_check(evidence=False, update_snapshots=False)

    if include_serve:
        @app.command()
        def serve(host: str = typer.Option("127.0.0.1"),
            port: int = typer.Option(8000, min=1, max=65535),
            watch: bool = typer.Option(False, "--watch",
                help="Rebuild frontend artifacts when their inputs change.")) -> None:
            """Build and serve this application through FastAPI."""
            try:
                with activated_environment(workspace, definition.directory):
                    result = serve_app(definition, workspace, host=host, port=port,
                        watch=watch, report=console.print)
            except (AppDefinitionError, EnvironmentConfigurationError, LifecycleError) as error:
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
