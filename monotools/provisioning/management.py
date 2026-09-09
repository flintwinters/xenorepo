"""Attach Xenorepo-owned controls to generic application managers.

Monoapps declare only their reusable Monotools lifecycle. The enclosing
Xenorepo adds repository inspection and promotion when it mounts each manager.
"""

from pathlib import Path

from rich.console import Console
import typer

from monotools.orchestration.management import ApplicationManager, create_cli
from monotools.orchestration.output import print_error
from monotools.provisioning.repositories import (
    RepositoryError, inspect_app_repository,
)


console = Console()


def _fail(error: Exception) -> None:
    print_error(console, error)
    raise typer.Exit(1)


def attach_repository_commands(manager: ApplicationManager, workspace: Path) -> None:
    """Mount Xenorepo repository controls onto one generic monoapp manager."""
    definition = manager.definition
    git_app = create_cli("Inspect and change this monoapp's Git repository boundary.")
    manager.app.add_typer(git_app, name="git")

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
