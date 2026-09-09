#!/usr/bin/env python3
"""Xenorepo-owned lifecycle aggregation and application mounting."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import subprocess

from rich.console import Console
from rich.table import Table
import typer

from monotools.orchestration.apps import (
    AppDefinition, AppDefinitionError, discover_planned_apps, is_planned_app, load_app,
)
from monotools.orchestration.browser import run_browser_framework_suite
from monotools.orchestration.environment import (
    EnvironmentConfigurationError, activated_environment,
)
from monotools.orchestration.lifecycle import (
    LifecycleError,
    build_app,
    collect_app_status,
    run_test_suite,
    validate_app,
    validate_source_lines,
    validate_dist,
)
from monotools.orchestration.management import ApplicationManager, PythonSuite, create_cli
from monotools.orchestration.output import print_error
from monotools.orchestration.ui import run_ui_check
from monotools.orchestration.aesthetics import review_aesthetics
from monotools.orchestration.hygiene import analyze_ui_hygiene
from monotools.provisioning.audit import AuditReport, audit_workspace
from monotools.provisioning.management import attach_repository_commands
from monotools.provisioning.repositories import (
    RepositoryError, delete_app, inspect_app_repository, promote_to_submodule,
    protect_upstream_remote, uninitialized_app_submodules,
)
from monotools.provisioning.scaffolding import ScaffoldError, scaffold_app


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
    _validate_manager(manager, path)
    return manager


def _validate_manager(manager: object, path: Path) -> None:
    """Validate one imported manager without obscuring its exact diagnostic."""
    if not isinstance(manager, ApplicationManager):
        raise ManagerError(f"app manager {path} must export 'manager' as ApplicationManager")
    if manager.definition.directory.resolve() != path.parent.resolve():
        raise ManagerError(f"app manager {path} describes another application")
    if not manager.python_suite.path.is_dir():
        raise ManagerError(f"app manager {path} has no Python suite: {manager.python_suite.path}")
    if manager.browser_suite is not None and not manager.browser_suite.path.is_file():
        raise ManagerError(f"app manager {path} has no browser suite: {manager.browser_suite.path}")


def _load_managed_app(directory: Path) -> tuple[AppDefinition, ApplicationManager]:
    manager_path = directory / "manage.py"
    if not manager_path.is_file():
        raise ManagerError(f"visible app directory has no manage.py: {directory}")
    try:
        definition = load_app(directory)
    except AppDefinitionError as error:
        raise ManagerError(str(error)) from error
    manager = _import_manager(manager_path)
    if manager.definition != definition:
        raise ManagerError(f"app manager {manager_path} definition does not match app.yaml")
    return definition, manager


def _load_startup_app(directory: Path, *, strict: bool
    ) -> tuple[AppDefinition, ApplicationManager] | None:
    """Skip broken remnants only while constructing recovery-capable commands."""
    try:
        return _load_managed_app(directory)
    except ManagerError:
        if strict:
            raise
        return None


def _record_manager(managers: list[tuple[AppDefinition, ApplicationManager]], names: set[str],
    definition: AppDefinition, manager: ApplicationManager) -> None:
    """Append one manager while enforcing inventory identity uniqueness."""
    if definition.name in names:
        raise ManagerError(f"duplicate managed app name: {definition.name}")
    names.add(definition.name)
    managers.append((definition, manager))


def discover_managers(apps_directory: Path = APPS_DIRECTORY, *, strict: bool = True
    ) -> tuple[tuple[AppDefinition, ApplicationManager], ...]:
    """Load every immediate visible Xenorepo app and its explicit manager."""
    managers: list[tuple[AppDefinition, ApplicationManager]] = []
    names: set[str] = set()
    uninitialized = {path.resolve() for path in uninitialized_app_submodules(apps_directory.parent)}
    for directory in _visible_directories(apps_directory):
        if directory.resolve() in uninitialized:
            continue
        if is_planned_app(directory):
            continue
        loaded = _load_startup_app(directory, strict=strict)
        if loaded is None:
            continue
        definition, manager = loaded
        _record_manager(managers, names, definition, manager)
    suite_paths = [manager.python_suite.path for _, manager in managers]
    if len(suite_paths) != len(set(suite_paths)):
        raise ManagerError("application Python suite paths must be unique")
    return tuple(managers)


def _fail(error: Exception | str) -> None:
    print_error(console, error)
    raise typer.Exit(1)


def _run_bootstrap(command: list[str], recovery: str) -> None:
    completed = subprocess.run(command, cwd=ROOT, check=False)
    if completed.returncode:
        raise LifecycleError(f"{' '.join(command)} failed ({completed.returncode}). {recovery}")


def _restore_dependencies(*, initialize_submodules: bool = True) -> None:
    """Initialize repository and language dependencies in their required order."""
    if initialize_submodules and (ROOT / ".gitmodules").is_file():
        _run_bootstrap(["git", "submodule", "update", "--init", "--recursive"],
            "Verify submodule access and URLs, then rerun bootstrap.")
    _run_bootstrap(["uv", "sync", "--locked"],
        "Restore or update uv.lock with uv lock, then rerun bootstrap.")
    _run_bootstrap(["npm", "ci"],
        "Verify package-lock.json and npm registry access, then rerun bootstrap.")
    _run_bootstrap(["node_modules/.bin/playwright", "install", "chromium"],
        "Restore network access for the Playwright browser download, then rerun bootstrap.")


def _collect_audit() -> AuditReport:
    try:
        return audit_workspace(ROOT, tuple(definition for definition, _ in discover_managers()))
    except (OSError, RuntimeError, SyntaxError) as error:
        raise LifecycleError(f"structural audit failed: {error}") from error


def _print_violations(title: str, violations: tuple[object, ...]) -> None:
    table = Table(title, "Path", "Detail")
    for violation in violations:
        table.add_row(violation.category, violation.path, violation.detail)
    console.print(table)


app = create_cli("Manage Xenorepo and its immediate applications.")
monoapp = create_cli("Create and manage Xenorepo monoapps.")
app.add_typer(monoapp, name="monoapp")
MANAGERS = discover_managers(strict=False)
for definition, manager in MANAGERS:
    attach_repository_commands(manager, ROOT)
    app.add_typer(manager.app, name=definition.name)


@monoapp.command("create")
def create_monoapp(name: str = typer.Argument(...),
    title: str = typer.Option(..., "--title", help="Human-readable application title.")) -> None:
    """Create a complete Monotools-owned Preact and FastAPI walking skeleton."""
    try:
        directory = scaffold_app(APPS_DIRECTORY, name, title)
    except (OSError, ScaffoldError) as error:
        _fail(error)
    console.print(f"[bold green]Created monoapp[/] {directory.relative_to(ROOT)}")
    console.print(f"Complete {directory.relative_to(ROOT) / 'SPEC.md'}, then run uv run manage.py verify.")


@monoapp.command("delete")
def delete_monoapp(name: str = typer.Argument(...)) -> None:
    """Delete a monoapp's directory, runtime data, commands, and repository registration."""
    try:
        deleted = delete_app(ROOT, name)
    except (OSError, RepositoryError) as error:
        _fail(error)
    console.print(f"[bold green]Deleted monoapp[/] {deleted.name} ({deleted.mode})")
    console.print(f"Committed as {deleted.revision}; run uv run manage.py verify.")


def _promote_monoapp(definition: AppDefinition, *, repository_directory: Path) -> None:
    """Move one managed app into a local Git repository without product validation."""
    repository = promote_to_submodule(
        definition, ROOT, repository_directory=repository_directory)
    console.print(f"[bold green]Promoted[/] {definition.name} -> {repository}")
    console.print("External remote: not configured; add one manually when ready.")


@monoapp.command("promote")
def promote_monoapp(name: str = typer.Argument(...),
    repository_directory: Path | None = typer.Option(None, "--repository-directory",
        help="Local repository path; defaults to data/repositories/<app>.")) -> None:
    """Create a local Git repository and replace a monoapp with its verified submodule."""
    selected = next((definition for definition, _ in MANAGERS if definition.name == name), None)
    if selected is None:
        _fail(f"unknown managed monoapp {name!r}")
    try:
        _promote_monoapp(selected,
            repository_directory=repository_directory or ROOT / "data" / "repositories" / name)
    except RepositoryError as error:
        _fail(error)


def _confirm_workspace_promotion(definition: AppDefinition) -> bool:
    """Confirm whether the current monolithic app should become its own repository."""
    try:
        state = inspect_app_repository(definition, ROOT)
    except RepositoryError as error:
        _fail(error)
    if state.mode != "monolith":
        return False
    if not typer.confirm(
        f"{definition.name} is not promoted. Promote it for direct work in apps/{definition.name}?",
        default=True,
    ):
        _fail(f"{definition.name} must be promoted before using its app-owned working tree")
    return True


def _clean_removal_candidates(others: tuple[AppDefinition, ...]) -> tuple[AppDefinition, ...]:
    """Preflight every app before allowing any workspace-focused deletion."""
    states = []
    for definition in others:
        try:
            states.append((definition, inspect_app_repository(definition, ROOT)))
        except RepositoryError as error:
            _fail(f"cannot safely focus the workspace: {error}")
    dirty = [definition.name for definition, state in states if not state.clean]
    if dirty:
        _fail("cannot remove monoapps with uncommitted work: " + ", ".join(dirty))
    return tuple(definition for definition, _ in states)


def _remove_other_apps(others: tuple[AppDefinition, ...]) -> None:
    """Remove a preflighted set of apps through the canonical deletion routine."""
    for definition in others:
        try:
            delete_app(ROOT, definition.name)
        except RepositoryError as error:
            _fail(f"workspace focus stopped while removing {definition.name}: {error}")


def _offer_workspace_focus(selected: AppDefinition) -> None:
    """Offer to remove every other clean monoapp from the current Xenorepo."""
    others = tuple(definition for definition, _ in MANAGERS
        if definition.name != selected.name)
    if not others or not typer.confirm(
        f"Remove the other {len(others)} monoapp(s) from this Xenorepo before promotion?",
        default=False,
    ):
        return
    candidates = _clean_removal_candidates(others)
    _remove_other_apps(candidates)
    console.print(f"[bold green]Removed[/] {len(candidates)} other monoapp(s)")


@monoapp.command("fork-workspace")
def fork_monoapp_workspace(name: str = typer.Argument(...)) -> None:
    """Focus this Xenorepo on one app and prepare its in-place Git workspace."""
    selected = next((definition for definition, _ in MANAGERS if definition.name == name), None)
    if selected is None:
        _fail(f"unknown managed monoapp {name!r}")
    promote = _confirm_workspace_promotion(selected)
    try:
        upstream = protect_upstream_remote(ROOT)
    except RepositoryError as error:
        _fail(error)
    _offer_workspace_focus(selected)
    if promote:
        try:
            _promote_monoapp(selected,
                repository_directory=ROOT / "data" / "repositories" / selected.name)
        except RepositoryError as error:
            _fail(error)
    console.print("[bold green]App workspace ready[/]")
    console.print(f"Working tree: {selected.directory}")
    if upstream:
        console.print(f"Source remote: upstream -> {upstream} (push disabled)")


@app.command()
def restore(initialize_submodules: bool = typer.Option(True,
    "--submodules/--no-submodules",
    help="Initialize every declared app submodule before restoring language dependencies.")) -> None:
    """Restore locked repository dependencies without imposing a runtime version policy."""
    try:
        _restore_dependencies(initialize_submodules=initialize_submodules)
        discover_managers()
    except (FileNotFoundError, LifecycleError, ManagerError) as error:
        _fail(error)
    console.print("[bold green]Dependencies restored[/]")


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
        _restore_dependencies()
    except (FileNotFoundError, LifecycleError) as error:
        _fail(error)
    try:
        discover_managers()
    except ManagerError as error:
        _fail(error)
    console.print(f"[bold green]Bootstrap complete[/] (Node {version.stdout.strip()})")


@app.command("list")
def list_apps() -> None:
    """List applications explicitly managed by Xenorepo."""
    table = Table("Name", "Title", "State", "Module")
    for definition, _ in MANAGERS:
        table.add_row(definition.name, definition.title, "active", definition.module)
    for planned in discover_planned_apps(APPS_DIRECTORY):
        table.add_row(planned.name, "—", "planned", "—")
    for directory in uninitialized_app_submodules(ROOT):
        table.add_row(directory.name, "—", "uninitialized submodule", "—")
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
    planned = discover_planned_apps(APPS_DIRECTORY)
    for item in planned:
        table.add_row(item.name, "—", "[cyan]planned[/]", "—", "—", "—")
    missing = uninitialized_app_submodules(ROOT)
    for directory in missing:
        table.add_row(directory.name, "—", "[yellow]uninitialized[/]", "—", "—", "—")
    console.print(table)
    console.print(
        f"{len(MANAGERS)} managed app(s), {len(planned)} planned, "
        f"{len(missing)} uninitialized; "
        "run [bold]manage.py check[/] for validation."
    )


@app.command()
def audit() -> None:
    """Report architecture violations and measured structural debt without mutation."""
    try:
        report = _collect_audit()
    except LifecycleError as error:
        _fail(error)
    _print_violations("Architecture", report.architecture)
    _print_violations("Large source files", report.large_files)
    _print_violations("Complex functions", report.complex_functions)
    console.print(
        f"[bold green]Architecture violations: {len(report.architecture)}[/]; "
        f"structural debt: {len(report.large_files)} large file(s), "
        f"{len(report.complex_functions)} complex function(s)"
    )
    if report.architecture:
        raise typer.Exit(1)


@app.command()
def check() -> None:
    """Validate Xenorepo's manager inventory and every application build."""
    try:
        missing = uninitialized_app_submodules(ROOT)
        if missing:
            names = ", ".join(path.name for path in missing)
            raise LifecycleError(
                f"uninitialized app submodules: {names}; run uv run manage.py bootstrap"
            )
        validate_source_lines(ROOT)
        report = _collect_audit()
        violations = report.architecture + report.large_files + report.complex_functions
        if violations:
            details = "; ".join(
                f"{item.category} {item.path}: {item.detail}" for item in violations
            )
            raise LifecycleError(f"structural audit failed: {details}")
        current = discover_managers()
        for definition, _ in current:
            with activated_environment(ROOT, definition.directory):
                validate_app(definition, ROOT)
                build_app(definition, ROOT)
                validate_dist(definition)
    except (EnvironmentConfigurationError, ManagerError, LifecycleError) as error:
        _fail(error)
    console.print(
        f"[bold green]All checks passed[/] ({len(current)} app(s); structural audit clean)"
    )


@app.command()
def test(pattern: str | None = typer.Option(None, "--pattern",
    help="Run matching platform test files only, for focused diagnostics.")) -> None:
    """Run the fast Python platform and application regression suites exactly once."""
    if isinstance(pattern, str):
        result = run_test_suite(ROOT, ROOT / "tests", pattern=pattern)
        if result:
            raise typer.Exit(result)
        return
    suites = ((PythonSuite(ROOT / "tests"), None),
        *((manager.python_suite, definition.directory) for definition, manager in MANAGERS))
    for suite, app_directory in suites:
        try:
            with activated_environment(ROOT, app_directory):
                result = run_test_suite(ROOT, suite.path, allow_empty=app_directory is not None)
        except EnvironmentConfigurationError as error:
            _fail(error)
        if result:
            raise typer.Exit(result)
    console.print("[bold green]Tests passed[/]")


@app.command("test-browser")
def test_browser() -> None:
    """Run the slower browser-framework integration suite."""
    with activated_environment(ROOT):
        result = run_browser_framework_suite(ROOT)
    if result:
        raise typer.Exit(result)
    console.print("[bold green]Browser framework tests passed[/]")


@app.command()
def security() -> None:
    """Fail closed when the root JavaScript graph has high or critical vulnerabilities."""
    try:
        completed = subprocess.run(
            ["npm", "audit", "--audit-level=high"], cwd=ROOT, check=False,
        )
    except FileNotFoundError:
        _fail("npm is required for the dependency security gate")
    if completed.returncode:
        _fail("dependency security audit failed or was unavailable")
    console.print("[bold green]Dependency security gate passed[/]")


@app.command("ui-check")
def ui_check(app_name: str | None = typer.Argument(None),
    evidence: bool = typer.Option(False, "--evidence",
        help="Retain trace, video, and HAR evidence for successful checks.")) -> None:
    """Run the deterministic universal and app-owned browser inventory."""
    selected = [(definition, manager) for definition, manager in MANAGERS
        if app_name is None or definition.name == app_name]
    if not selected:
        _fail(f"unknown app '{app_name}'; available: {', '.join(d.name for d, _ in MANAGERS)}")
    try:
        for definition, manager in selected:
            with activated_environment(ROOT, definition.directory):
                run_ui_check(definition, ROOT, manager.browser_suite, evidence=evidence)
    except (EnvironmentConfigurationError, LifecycleError) as error:
        _fail(error)
    console.print(f"[bold green]browser proofs passed[/] ({len(selected)} app(s))")


@app.command("ui-hygiene")
def ui_hygiene(app_name: str | None = typer.Argument(None)) -> None:
    """Measure UI vocabulary and enforce toolkit and CSS boundaries."""
    selected = [definition for definition, _ in MANAGERS
        if app_name is None or definition.name == app_name]
    if not selected:
        _fail(f"unknown app '{app_name}'; available: {', '.join(d.name for d, _ in MANAGERS)}")
    try:
        for definition in selected:
            report = analyze_ui_hygiene(definition, ROOT)
            metrics = report["metrics"]
            console.print(f"[green]UI hygiene passed[/] {definition.name} "
                f"({metrics['commandButtons']} commands; {metrics['domainControls']} domain controls)")
    except LifecycleError as error:
        _fail(error)


@app.command("aesthetic-check")
def aesthetic_check(app_name: str | None = typer.Argument(None)) -> None:
    """Capture every review resolution and have a multimodal AI judge the result."""
    selected = [(definition, manager) for definition, manager in MANAGERS
        if app_name is None or definition.name == app_name]
    if not selected:
        _fail(f"unknown app '{app_name}'; available: {', '.join(d.name for d, _ in MANAGERS)}")
    try:
        for definition, manager in selected:
            with activated_environment(ROOT, definition.directory):
                artifacts = run_ui_check(definition, ROOT, manager.browser_suite)
                review_aesthetics(definition, artifacts / "aesthetic-screenshots",
                    artifacts / "aesthetic-review.json")
    except (EnvironmentConfigurationError, LifecycleError) as error:
        _fail(error)
    console.print(f"[bold green]AI aesthetic reviews passed[/] ({len(selected)} app(s))")


@app.command()
def verify() -> None:
    """Run the fast, deterministic inner-loop checks and Python tests."""
    check()
    test()


@app.command()
def release() -> None:
    """Run the slow, fail-closed mainline release gate."""
    verify()
    security()
    test_browser()
    ui_check(app_name=None, evidence=False)


if __name__ == "__main__":
    app()
