"""Inspect and promote monoapp Git repository boundaries.

This module changes source ownership without changing the application-platform
contract: promoted apps remain deliberate consumers of their enclosing Xenorepo.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
import re
import shutil
import subprocess

from monotools.apps import AppDefinition


class RepositoryError(RuntimeError):
    """Raised when repository state makes a requested transition unsafe or ambiguous."""


@dataclass(frozen=True)
class AppRepositoryState:
    """One app's current Git ownership and local modification state."""

    mode: str
    clean: bool
    remote: str | None
    revision: str


_GITHUB_COMPONENT = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9_.-]*[A-Za-z0-9])?$")
_VISIBILITIES = frozenset({"private", "public", "internal"})


def _run(command: list[str], cwd: Path) -> str:
    completed = subprocess.run(command, cwd=cwd, check=False, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if completed.returncode:
        detail = completed.stdout.strip() or "no diagnostic output"
        raise RepositoryError(f"{' '.join(command)} failed ({completed.returncode}): {detail}")
    return completed.stdout.strip()


def _git(cwd: Path, *arguments: str) -> str:
    return _run(["git", *arguments], cwd)


def _gh(cwd: Path, *arguments: str) -> str:
    return _run(["gh", *arguments], cwd)


def _relative_app_path(definition: AppDefinition, workspace: Path) -> Path | None:
    try:
        relative = definition.directory.resolve().relative_to(workspace.resolve())
    except ValueError:
        return None
    expected = Path("apps") / definition.name
    return relative if relative == expected else None


def inspect_app_repository(definition: AppDefinition, workspace: Path) -> AppRepositoryState:
    """Report monolithic, submodule, or independent ownership without mutation."""
    relative = _relative_app_path(definition, workspace)
    if relative is None:
        revision = _git(definition.directory, "rev-parse", "--short", "HEAD")
        dirty = bool(_git(definition.directory, "status", "--short"))
        remote = _optional_remote(definition.directory)
        return AppRepositoryState("independent", not dirty, remote, revision)
    staged = _git(workspace, "ls-files", "--stage", "--", str(relative)).splitlines()
    mode = "submodule" if any(line.startswith("160000 ") for line in staged) else "monolith"
    git_root = definition.directory if mode == "submodule" else workspace
    pathspec = [] if mode == "submodule" else ["--", str(relative)]
    dirty = bool(_git(git_root, "status", "--short", *pathspec))
    revision = _git(git_root, "rev-parse", "--short", "HEAD")
    remote = _optional_remote(git_root) if mode == "submodule" else None
    return AppRepositoryState(mode, not dirty, remote, revision)


def _optional_remote(directory: Path) -> str | None:
    completed = subprocess.run(["git", "remote", "get-url", "origin"], cwd=directory,
        check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    return completed.stdout.strip() if completed.returncode == 0 else None


def _validate_github_target(owner: str, repository: str, visibility: str) -> None:
    if not _GITHUB_COMPONENT.fullmatch(owner):
        raise RepositoryError("GitHub owner must be one account or organization name")
    if not _GITHUB_COMPONENT.fullmatch(repository):
        raise RepositoryError("GitHub repository must be one unqualified repository name")
    if visibility not in _VISIBILITIES:
        raise RepositoryError("visibility must be private, public, or internal")


def _preflight(definition: AppDefinition, workspace: Path, owner: str,
    repository: str, visibility: str) -> Path:
    _validate_github_target(owner, repository, visibility)
    if shutil.which("git") is None:
        raise RepositoryError("git is required for monoapp repository management")
    if shutil.which("gh") is None:
        raise RepositoryError("GitHub CLI is required; install gh and run 'gh auth login'")
    relative = _relative_app_path(definition, workspace)
    if relative is None:
        raise RepositoryError("create-repo requires an app mounted at apps/<name> in Xenorepo")
    state = inspect_app_repository(definition, workspace)
    if state.mode != "monolith":
        raise RepositoryError(f"{definition.name} is already managed as {state.mode}")
    if _git(workspace, "status", "--short"):
        raise RepositoryError("Xenorepo worktree must be clean before repository promotion")
    if not (definition.directory / ".gitignore").is_file():
        raise RepositoryError(f"{definition.name} needs an app-owned .gitignore before promotion")
    _gh(workspace, "auth", "status")
    return relative


def promote_to_submodule(definition: AppDefinition, workspace: Path, *, owner: str,
    repository: str, visibility: str, verify: Callable[[], None]) -> str:
    """Create a GitHub repository, preserve app history, and mount it as a submodule."""
    relative = _preflight(definition, workspace, owner, repository, visibility)
    verify()
    split = _git(workspace, "subtree", "split", f"--prefix={relative}", "HEAD").splitlines()[-1]
    target = f"{owner}/{repository}"
    _gh(workspace, "repo", "create", target, f"--{visibility}",
        "--description", f"{definition.title} monoapp", "--disable-wiki")
    remote = _gh(workspace, "repo", "view", target, "--json", "sshUrl", "--jq", ".sshUrl")
    _git(workspace, "push", remote, f"{split}:refs/heads/main")
    _git(workspace, "rm", "-r", "--", str(relative))
    _git(workspace, "clean", "-fdX", "--", str(relative))
    _git(workspace, "submodule", "add", "--name", definition.name, "--branch", "main",
        remote, str(relative))
    mounted = _git(definition.directory, "rev-parse", "HEAD")
    if mounted != split:
        raise RepositoryError(f"mounted revision {mounted} does not match exported revision {split}")
    verify()
    _commit_promotion(definition, workspace, relative, remote, split)
    return remote


def _commit_promotion(definition: AppDefinition, workspace: Path, relative: Path,
    remote: str, revision: str) -> None:
    subject = f"Promote {definition.title} to a monoapp submodule"
    body = (
        f"Move {relative} from Xenorepo-owned files to an independently versioned Git repository "
        f"at {remote}. Preserve the app-only history through revision {revision} and pin the "
        "verified remote main revision through Xenorepo's submodule gitlink.\n\n"
        "The app remains intentionally coupled to the enclosing Xenorepo's current Monotools, "
        "shared frontend packages, lifecycle commands, and complete verification matrix."
    )
    _git(workspace, "commit", "-m", subject, "-m", body)
