"""Build Typer-native command surfaces for application managers.

This module turns app definitions and suite declarations into consistent leaf
commands while keeping root orchestration generic and discoverable.
"""

from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys

import typer
from rich.console import Console

from monotools.orchestration.apps import AppDefinition, AppDefinitionError, load_app
from monotools.orchestration.lifecycle import (
    LifecycleError,
    build_app,
    run_test_suite,
    serve_app,
    validate_app,
    validate_dist,
)
from monotools.orchestration.repositories import RepositoryError, inspect_app_repository, promote_to_submodule
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
    if definition.specification.is_file() and browser_path is None:
        raise AppDefinitionError(
            f"{definition.name} has a product specification but no app-owned browser suite"
        )
    app = create_cli(f"Build, validate, test, and run {definition.title}.")
    git_app = create_cli("Inspect and change this monoapp's Git repository boundary.")
    app.add_typer(git_app, name="git")

    @git_app.command("status")
    def git_status() -> None:
        """Show whether this app is monolithic, a submodule, or independent."""
        try:
            state = inspect_app_repository(definition, workspace)
        except RepositoryError as error:
            _fail(error)
        console.print(f"[bold]{definition.name}[/] {state.mode} at {state.revision}")
        console.print(f"worktree: {'clean' if state.clean else 'modified'}")
        console.print(f"origin: {state.remote or 'not configured'}")

    @git_app.command("create-repo")
    def create_repository(owner: str = typer.Option(..., "--owner"),
        repository: str = typer.Option(..., "--repository"),
        visibility: str = typer.Option(..., "--visibility")) -> None:
        """Create a GitHub repository and replace this app with its verified submodule."""
        def verify_workspace() -> None:
            completed = subprocess.run(
                [sys.executable, "manage.py", definition.name, "verify"],
                cwd=workspace, check=False,
            )
            if completed.returncode:
                raise RepositoryError(
                    f"workspace verification failed ({completed.returncode}); promotion stopped"
                )

        try:
            remote = promote_to_submodule(definition, workspace, owner=owner,
                repository=repository, visibility=visibility, verify=verify_workspace)
        except RepositoryError as error:
            _fail(error)
        console.print(f"[bold green]Promoted[/] {definition.name} -> {remote}")

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

    @app.command("ui-check")
    def ui_check(evidence: bool = typer.Option(False, "--evidence",
            help="Retain trace, video, and HAR evidence for successful checks.")) -> None:
        """Run universal journeys and any app-owned browser suite."""
        declared = (BrowserSuite(browser_path, proof_kinds, viewports, input_modalities)
            if browser_path is not None else None)
        try:
            artifacts = run_ui_check(definition, workspace, declared, evidence=evidence)
        except LifecycleError as error:
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
        ui_check(evidence=False)

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
