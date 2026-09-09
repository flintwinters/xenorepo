"""Inspect and promote monoapp Git repository boundaries for a host repository.

This module changes source ownership without changing the application-platform
contract: promoted apps remain deliberate consumers of their enclosing Xenorepo.
"""

from __future__ import annotations

from collections.abc import Callable
from configparser import ConfigParser
from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess
from typing import TYPE_CHECKING

from monotools.orchestration.apps import AppDefinitionError, validate_app_name

if TYPE_CHECKING:
    from monotools.orchestration.apps import AppDefinition


class RepositoryError(RuntimeError):
    """Raised when repository state makes a requested transition unsafe or ambiguous."""


@dataclass(frozen=True)
class AppRepositoryState:
    """One app's current Git ownership and local modification state."""

    mode: str
    clean: bool
    remote: str | None
    revision: str


@dataclass(frozen=True)
class AppDeletion:
    """The local repository boundary removed for one monoapp."""

    name: str
    mode: str
    path: Path
    revision: str


@dataclass(frozen=True)
class FocusedWorkspace:
    """A verified Xenorepo derivative detached from its source repository."""

    path: Path
    revision: str


def declared_app_submodules(workspace: Path) -> tuple[Path, ...]:
    """Return normalized apps/* paths declared by the parent Git repository."""
    metadata = workspace / ".gitmodules"
    if not metadata.is_file():
        return ()
    parser = ConfigParser(interpolation=None)
    try:
        parser.read(metadata, encoding="utf-8")
    except Exception as error:
        raise RepositoryError(f"cannot parse {metadata}: {error}") from error
    paths = []
    for section in parser.sections():
        candidate = Path(parser.get(section, "path", fallback=""))
        if candidate.parts[:1] == ("apps",) and len(candidate.parts) == 2:
            paths.append(workspace / candidate)
    return tuple(sorted(paths))


def uninitialized_app_submodules(workspace: Path) -> tuple[Path, ...]:
    """Return declared app submodules whose working trees have not been populated."""
    return tuple(path for path in declared_app_submodules(workspace)
        if not (path / ".git").exists())


def _deletion_target(workspace: Path, name: str) -> tuple[str, Path, Path, bool]:
    try:
        valid_name = validate_app_name(name)
    except AppDefinitionError as error:
        raise RepositoryError(str(error)) from error
    relative = Path("apps") / valid_name
    directory = workspace / relative
    submodule = directory in declared_app_submodules(workspace)
    if not directory.exists() and not submodule:
        available = sorted(path.name for path in (workspace / "apps").iterdir()
            if path.is_dir() and not path.name.startswith((".", "_")))
        raise RepositoryError(
            f"unknown monoapp {valid_name!r}; available: {', '.join(available) or 'none'}"
        )
    return valid_name, relative, directory, submodule


def _remove_submodule(workspace: Path, relative: Path) -> None:
    _git(workspace, "submodule", "deinit", "-f", "--", str(relative))
    _git(workspace, "rm", "-f", "--", str(relative))
    module_metadata = workspace / ".git" / "modules" / relative
    if module_metadata.exists():
        shutil.rmtree(module_metadata)


def _commit_deletion(workspace: Path, name: str, relative: Path, submodule: bool) -> str:
    subject = f"Delete {name} monoapp"
    body = (
        f"Remove the complete local {relative} application boundary, including its source, "
        "specification, tests, management commands, and repository registration."
    )
    pathspecs = [str(relative)]
    if submodule:
        pathspecs.insert(0, ".gitmodules")
    _git(workspace, "commit", "--only", "-m", subject, "-m", body, "--", *pathspecs)
    return _git(workspace, "rev-parse", "--short", "HEAD")


def delete_app(workspace: Path, name: str) -> AppDeletion:
    """Remove one local monoapp and every host-repository registration it owns."""
    workspace = workspace.resolve()
    valid_name, relative, directory, submodule = _deletion_target(workspace, name)
    tracked = "" if submodule else _git(workspace, "ls-files", "--", str(relative))
    if not submodule and not tracked:
        raise RepositoryError(
            f"{valid_name} is not versioned; commit it before deletion so the deletion can be reverted"
        )
    if submodule:
        _remove_submodule(workspace, relative)
        mode = "submodule"
    else:
        _git(workspace, "rm", "-r", "-f", "--", str(relative))
        mode = "monolith"
    if directory.exists():
        shutil.rmtree(directory)
    revision = _commit_deletion(workspace, valid_name, relative, submodule)
    return AppDeletion(valid_name, mode, relative, revision)


def _run(command: list[str], cwd: Path) -> str:
    completed = subprocess.run(command, cwd=cwd, check=False, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if completed.returncode:
        detail = completed.stdout.strip() or "no diagnostic output"
        raise RepositoryError(f"{' '.join(command)} failed ({completed.returncode}): {detail}")
    return completed.stdout.strip()


def _git(cwd: Path, *arguments: str) -> str:
    return _run(["git", *arguments], cwd)


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


def _require_git() -> None:
    if shutil.which("git") is None:
        raise RepositoryError("git is required for focused workspace creation")


def _require_promoted_app(definition: AppDefinition, workspace: Path) -> Path:
    relative = _relative_app_path(definition, workspace)
    if relative is None:
        raise RepositoryError("fork-workspace requires an app mounted at apps/<name> in Xenorepo")
    state = inspect_app_repository(definition, workspace)
    if state.mode != "submodule":
        raise RepositoryError(f"{definition.name} must be promoted before forking a workspace")
    if not state.clean:
        _git(definition.directory, "clean", "-fd", "--",
            "data/monoform.json", "data/monoform-build")
        state = inspect_app_repository(definition, workspace)
    if not state.clean:
        raise RepositoryError(f"{definition.name} submodule must be clean before forking a workspace")
    return relative


def _focused_preflight(definition: AppDefinition, workspace: Path,
    destination: Path) -> tuple[Path, str]:
    _require_git()
    if destination == workspace or destination.is_relative_to(workspace):
        raise RepositoryError("focused workspace destination must be outside the source Xenorepo")
    relative = _require_promoted_app(definition, workspace)
    if destination.exists():
        raise RepositoryError(f"refusing to overwrite existing destination: {destination}")
    branch = _git(workspace, "symbolic-ref", "--quiet", "--short", "HEAD")
    return relative, branch


def _tracked_app_names(workspace: Path) -> tuple[str, ...]:
    output = _git(workspace, "ls-tree", "-d", "--name-only", "HEAD:apps")
    names = tuple(line.strip() for line in output.splitlines() if line.strip())
    for name in names:
        try:
            validate_app_name(name)
        except AppDefinitionError as error:
            raise RepositoryError(f"tracked apps entry is not a monoapp name: {name}") from error
    return names


def fork_focused_workspace(definition: AppDefinition, workspace: Path, *, destination: Path,
    verify: Callable[[Path], None]) -> FocusedWorkspace:
    """Create and verify a focused workspace with no remote Xenorepo dependency."""
    workspace, destination = workspace.resolve(), destination.resolve()
    relative, branch = _focused_preflight(definition, workspace, destination)
    _git(workspace, "clone", "--no-recurse-submodules", "--branch", branch,
        str(workspace), str(destination))
    _git(destination, "-c", "protocol.file.allow=always", "submodule", "update", "--init",
        "--", str(relative))
    for name in _tracked_app_names(destination):
        if name != definition.name:
            _git(destination, "rm", "-r", "-f", "--", str(Path("apps") / name))
    _git(destination, "commit", "-m", f"Create focused {definition.title} workspace",
        "-m", "Retain the shared Xenorepo platform and the selected promoted monoapp while "
        "removing unrelated application sources and submodule registrations.")
    _git(destination, "remote", "remove", "origin")
    verify(destination)
    revision = _git(destination, "rev-parse", "--short", "HEAD")
    return FocusedWorkspace(destination, revision)


def _validate_local_repository_target(workspace: Path, repository_directory: Path) -> None:
    """Require a new local repository target outside the source Xenorepo."""
    if repository_directory == workspace or repository_directory.is_relative_to(workspace):
        raise RepositoryError("promoted monoapp repository must be outside Xenorepo")
    if repository_directory.exists():
        raise RepositoryError(f"refusing to overwrite existing repository: {repository_directory}")


def _preflight(definition: AppDefinition, workspace: Path,
    repository_directory: Path) -> Path:
    if shutil.which("git") is None:
        raise RepositoryError("git is required for monoapp repository management")
    _validate_local_repository_target(workspace, repository_directory)
    relative = _relative_app_path(definition, workspace)
    if relative is None:
        raise RepositoryError("promote requires an app mounted at apps/<name> in Xenorepo")
    state = inspect_app_repository(definition, workspace)
    if state.mode != "monolith":
        raise RepositoryError(f"{definition.name} is already managed as {state.mode}")
    staged = _git(workspace, "diff", "--cached", "--name-only")
    if staged:
        raise RepositoryError(
            "Xenorepo index contains staged changes; commit or unstage them before promotion"
        )
    if not (definition.directory / ".gitignore").is_file():
        raise RepositoryError(f"{definition.name} needs an app-owned .gitignore before promotion")
    return relative


def _commit_pending_app_changes(definition: AppDefinition, workspace: Path,
    relative: Path) -> None:
    """Capture a verified app snapshot without staging unrelated workspace changes."""
    if not _git(workspace, "status", "--short", "--", str(relative)):
        return
    _git(workspace, "add", "-A", "--", str(relative))
    _git(workspace, "commit", "-m", f"Prepare {definition.title} for promotion", "-m",
        f"Record the complete verified {relative} application state before extracting its "
        "history into an independently versioned monoapp repository.")


def promote_to_submodule(definition: AppDefinition, workspace: Path, *,
    repository_directory: Path, verify: Callable[[], None]) -> Path:
    """Create a local app repository, preserve history, and mount it as a submodule."""
    workspace, repository_directory = workspace.resolve(), repository_directory.resolve()
    relative = _preflight(definition, workspace, repository_directory)
    verify()
    _commit_pending_app_changes(definition, workspace, relative)
    split = _git(workspace, "subtree", "split", f"--prefix={relative}", "HEAD").splitlines()[-1]
    repository_directory.mkdir(parents=True)
    _git(repository_directory, "init", "--initial-branch=main")
    _git(repository_directory, "fetch", str(workspace), split)
    _git(repository_directory, "checkout", "-B", "main", "FETCH_HEAD")
    _git(workspace, "rm", "-r", "--", str(relative))
    _git(workspace, "clean", "-fdX", "--", str(relative))
    _git(workspace, "-c", "protocol.file.allow=always", "submodule", "add", "--name",
        definition.name, "--branch", "main", str(repository_directory), str(relative))
    mounted = _git(definition.directory, "rev-parse", "HEAD")
    if mounted != split:
        raise RepositoryError(f"mounted revision {mounted} does not match exported revision {split}")
    verify()
    _commit_promotion(definition, workspace, relative, repository_directory, split)
    return repository_directory


def _commit_promotion(definition: AppDefinition, workspace: Path, relative: Path,
    repository_directory: Path, revision: str) -> None:
    subject = f"Promote {definition.title} to a monoapp submodule"
    body = (
        f"Move {relative} from Xenorepo-owned files to an independently versioned Git repository "
        f"at {repository_directory}. Preserve app-only history through revision {revision} and pin the "
        "verified local main revision through Xenorepo's submodule gitlink.\n\n"
        "No hosted remote is configured; add one manually when repository ownership and hosting "
        "are decided. The app remains coupled to Xenorepo's Monotools and shared packages."
    )
    _git(workspace, "commit", "-m", subject, "-m", body)
