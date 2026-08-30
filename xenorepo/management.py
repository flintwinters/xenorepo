"""Attach Xenorepo-owned controls to generic application managers.

Monoapps declare only their reusable Monotools lifecycle. The enclosing
Xenorepo adds repository inspection and promotion when it mounts each manager.
"""

from pathlib import Path
import subprocess
import sys

from rich.console import Console
import typer

from monotools.orchestration.management import ApplicationManager, create_cli
from monotools.orchestration.output import print_error
from xenorepo.repositories import RepositoryError, inspect_app_repository, promote_to_submodule


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
