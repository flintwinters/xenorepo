"""Inspect and promote monoapp Git repository boundaries for a host repository.

This module changes source ownership without changing the application-platform
contract: promoted apps remain deliberate consumers of their enclosing Xenorepo.
"""

from __future__ import annotations

from configparser import ConfigParser
from configparser import NoSectionError
from dataclasses import dataclass
from pathlib import Path
import shutil
from typing import TYPE_CHECKING

from git import GitCommandError, InvalidGitRepositoryError, NoSuchPathError, Repo

from monotools.orchestration.apps import AppDefinitionError, validate_app_name

if TYPE_CHECKING:
    from monotools.orchestration.apps import AppDefinition


class RepositoryError(RuntimeError):
    """Raised when repository state makes a requested transition unsafe or ambiguous."""


UPSTREAM_PUSH_DISABLED_URL = "disabled://xenorepo-upstream-push-prohibited"


def _repository(directory: Path) -> Repo:
    """Open exactly one repository and normalize library diagnostics."""
    try:
        return Repo(directory, search_parent_directories=False)
    except (InvalidGitRepositoryError, NoSuchPathError) as error:
        raise RepositoryError(f"not a Git repository: {directory}") from error


def _remove_local_submodule_config(workspace: Path, name: str) -> None:
    try:
        with _repository(workspace).config_writer() as writer:
            writer.remove_section(f"submodule.{name}")
    except NoSectionError:
        pass


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
class AppBoundary:
    """One complete versioned apps/* boundary, whether or not its source is loaded."""

    name: str
    path: Path
    mode: str
    populated: bool
    clean: bool


@dataclass(frozen=True)
class WorkspaceFocus:
    """The atomic host-repository change that retained one monoapp boundary."""

    selected: str
    removed: tuple[str, ...]
    revision: str | None


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


def _versioned_app_names(workspace: Path) -> set[str]:
    """Read app identities from HEAD without requiring their working trees."""
    output = _git(workspace, "ls-tree", "-r", "--name-only", "HEAD", "--", "apps")
    names: set[str] = set()
    for line in output.splitlines():
        path = Path(line)
        if path.parts[:1] == ("apps",) and len(path.parts) >= 2:
            names.add(path.parts[1])
    return names


def _validate_boundary_name(name: str) -> None:
    try:
        validate_app_name(name)
    except AppDefinitionError as error:
        raise RepositoryError(f"unmanaged app directory {name!r}: {error}") from error


def _inspect_boundary(workspace: Path, name: str, submodule: bool) -> AppBoundary:
    _validate_boundary_name(name)
    path = workspace / "apps" / name
    tracked = _git(workspace, "ls-files", "--stage", "--", f"apps/{name}")
    if not tracked:
        raise RepositoryError(
            f"unmanaged app directory apps/{name}; commit or remove it before focusing")
    populated = path.is_dir() and (not submodule or (path / ".git").exists())
    if not submodule:
        dirty = bool(_git(workspace, "status", "--short", "--", f"apps/{name}"))
        return AppBoundary(name, path, "monolith", populated, not dirty)
    dirty = path.is_dir() and any(path.iterdir()) if not populated else _submodule_dirty(
        path, tracked)
    return AppBoundary(name, path, "submodule", populated, not dirty)


def _submodule_dirty(path: Path, tracked: str) -> bool:
    pinned = tracked.split()[1] if tracked.split() else ""
    return bool(_git(path, "status", "--short")) or _git(path, "rev-parse", "HEAD") != pinned


def app_boundary_inventory(workspace: Path) -> tuple[AppBoundary, ...]:
    """Inspect every versioned or registered immediate app without loading app code."""
    workspace = workspace.resolve()
    submodules = {path.name: path for path in declared_app_submodules(workspace)}
    names = _versioned_app_names(workspace) | set(submodules)
    apps_directory = workspace / "apps"
    if apps_directory.is_dir():
        for path in apps_directory.iterdir():
            if path.is_dir() and not path.name.startswith((".", "_")):
                names.add(path.name)
    return tuple(_inspect_boundary(workspace, name, name in submodules)
        for name in sorted(names))


def initialize_app_submodules(workspace: Path, names: tuple[str, ...] | None = None) -> None:
    """Populate only explicitly declared monoapp source boundaries."""
    declared = {path.name: path for path in declared_app_submodules(workspace)}
    requested = tuple(sorted(declared)) if names is None else names
    unknown = sorted(set(requested) - set(declared))
    if unknown:
        raise RepositoryError(
            f"unknown declared monoapp submodule(s): {', '.join(unknown)}")
    if not requested:
        return
    _git(workspace, "submodule", "update", "--init", "--recursive", "--",
        *(str(declared[name].relative_to(workspace)) for name in requested))


def _remove_gitmodule_sections(metadata: Path, names: tuple[str, ...]) -> None:
    parser = ConfigParser(interpolation=None)
    parser.read(metadata, encoding="utf-8")
    for section in tuple(parser.sections()):
        path = Path(parser.get(section, "path", fallback=""))
        if path.parts[:1] == ("apps",) and len(path.parts) == 2 and path.name in names:
            parser.remove_section(section)
    if parser.sections():
        with metadata.open("w", encoding="utf-8") as stream:
            parser.write(stream, space_around_delimiters=False)
    else:
        metadata.unlink(missing_ok=True)


def _restore_focus_index(workspace: Path, paths: tuple[str, ...], metadata: Path,
    original_metadata: bytes | None) -> None:
    _git(workspace, "reset", "HEAD", "--", *paths)
    if original_metadata is None:
        metadata.unlink(missing_ok=True)
        return
    metadata.write_bytes(original_metadata)
    _git(workspace, "reset", "HEAD", "--", ".gitmodules")


def _commit_focus(workspace: Path, selected: str, names: tuple[str, ...],
    paths: tuple[str, ...], metadata: Path, original_metadata: bytes | None) -> None:
    _git(workspace, "rm", "-r", "-f", "--cached", "--", *paths)
    if original_metadata is not None:
        _remove_gitmodule_sections(metadata, names)
        _git(workspace, "add", "-A", "--", ".gitmodules")
    body = (
        f"Retain apps/{selected} as the sole monoapp boundary and remove {len(names)} "
        f"other versioned app boundaries in one reversible repository transaction.\n\n"
        f"Removed: {', '.join(names)}. Source checkouts were not fetched or initialized; "
        "reverting this commit restores their host-repository registrations."
    )
    _git(workspace, "commit", "-m", f"Focus Xenorepo workspace on {selected}", "-m", body)


def _discard_focused_boundaries(workspace: Path, candidates: tuple[AppBoundary, ...]) -> None:
    for item in candidates:
        if item.path.exists():
            shutil.rmtree(item.path)
        module_metadata = workspace / ".git" / "modules" / item.name
        if module_metadata.exists():
            shutil.rmtree(module_metadata)
        _remove_local_submodule_config(workspace, item.name)


def _focus_candidates(workspace: Path, selected: str, discard: bool
    ) -> tuple[AppBoundary, ...]:
    if _git(workspace, "diff", "--cached", "--name-only"):
        raise RepositoryError(
            "Xenorepo index contains staged changes; commit or unstage them before focusing")
    inventory = app_boundary_inventory(workspace)
    if selected not in {item.name for item in inventory}:
        raise RepositoryError(f"unknown versioned monoapp {selected!r}")
    candidates = tuple(item for item in inventory if item.name != selected)
    dirty = tuple(item.name for item in candidates if not item.clean)
    if dirty and not discard:
        raise RepositoryError(
            "cannot remove monoapps with uncommitted or unpinned work: " + ", ".join(dirty))
    return candidates


def focus_app_workspace(workspace: Path, selected: str, *, discard: bool = False
    ) -> WorkspaceFocus:
    """Atomically remove every non-selected versioned app boundary without fetching source."""
    workspace = workspace.resolve()
    candidates = _focus_candidates(workspace, selected, discard)
    if not candidates:
        return WorkspaceFocus(selected, (), None)
    names = tuple(item.name for item in candidates)
    paths = tuple(f"apps/{name}" for name in names)
    metadata = workspace / ".gitmodules"
    original_metadata = metadata.read_bytes() if metadata.is_file() else None
    try:
        _commit_focus(workspace, selected, names, paths, metadata, original_metadata)
    except Exception as error:
        _restore_focus_index(workspace, paths, metadata, original_metadata)
        raise RepositoryError(f"workspace focus rolled back after failure: {error}") from error
    _discard_focused_boundaries(workspace, candidates)
    revision = _git(workspace, "rev-parse", "--short", "HEAD")
    return WorkspaceFocus(selected, names, revision)


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


def _remove_submodule(workspace: Path, name: str, relative: Path) -> None:
    _git(workspace, "submodule", "deinit", "-f", "--", str(relative))
    _git(workspace, "rm", "-f", "--", str(relative))
    module_metadata = workspace / ".git" / "modules" / name
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
    tracked = "" if submodule else _git(
        workspace, "ls-tree", "-r", "--name-only", "HEAD", "--", str(relative))
    if not submodule and not tracked:
        raise RepositoryError(
            f"{valid_name} is not versioned; commit it before deletion so the deletion can be reverted"
        )
    if submodule:
        _remove_submodule(workspace, valid_name, relative)
        mode = "submodule"
    else:
        _git(workspace, "reset", "HEAD", "--", str(relative))
        _git(workspace, "rm", "-r", "-f", "--", str(relative))
        mode = "monolith"
    if directory.exists():
        shutil.rmtree(directory)
    revision = _commit_deletion(workspace, valid_name, relative, submodule)
    return AppDeletion(valid_name, mode, relative, revision)


def _git(cwd: Path, *arguments: str) -> str:
    """Run Git plumbing through the project's sole GitPython boundary."""
    try:
        if arguments[:1] == ("init",):
            initial_branch = next((item.split("=", 1)[1] for item in arguments
                if item.startswith("--initial-branch=")), None)
            Repo.init(cwd, initial_branch=initial_branch)
            return ""
        repository = _repository(cwd)
        return repository.git.execute(["git", *arguments]).strip()
    except GitCommandError as error:
        detail = (error.stderr or error.stdout or "no diagnostic output").strip()
        raise RepositoryError(
            f"git {' '.join(arguments)} failed ({error.status}): {detail}") from error


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


def _optional_remote(directory: Path, name: str = "origin") -> str | None:
    repository = _repository(directory)
    try:
        return next(remote.url for remote in repository.remotes if remote.name == name)
    except StopIteration:
        return None


def protect_upstream_remote(workspace: Path) -> str | None:
    """Retain the source remote for fetching while making accidental pushes impossible."""
    origin = _optional_remote(workspace)
    upstream = _optional_remote(workspace, "upstream")
    if origin and upstream and origin == upstream:
        _git(workspace, "remote", "remove", "origin")
    elif origin and not upstream:
        _git(workspace, "remote", "rename", "origin", "upstream")
        upstream = origin
    if upstream:
        _git(workspace, "remote", "set-url", "--push", "upstream",
            UPSTREAM_PUSH_DISABLED_URL)
    return upstream


def _validate_local_repository_target(workspace: Path, repository_directory: Path) -> None:
    """Require a new target outside maintained source directories."""
    if repository_directory.is_relative_to(workspace) and not repository_directory.is_relative_to(
        workspace / "data"):
        raise RepositoryError("internal repository targets must be beneath Xenorepo data/")
    if repository_directory.exists():
        raise RepositoryError(f"refusing to overwrite existing repository: {repository_directory}")


def _preflight(definition: AppDefinition, workspace: Path,
    repository_directory: Path) -> Path:
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
    """Capture the current app snapshot without staging unrelated workspace changes."""
    if not _git(workspace, "status", "--short", "--", str(relative)):
        return
    try:
        readme = relative / "README.md"
        if (workspace / readme).is_file():
            _git(workspace, "add", "-f", "--", str(readme))
        _git(workspace, "add", "-A", "--", str(relative))
        _git(workspace, "commit", "-m", f"Prepare {definition.title} for promotion", "-m",
            f"Record the complete current {relative} application state before extracting its "
            "history into an independently versioned monoapp repository.")
    except Exception:
        _git(workspace, "reset", "HEAD", "--", str(relative))
        raise


def _create_local_repository(repository_directory: Path, workspace: Path, split: str) -> None:
    """Materialize app-only history without leaving a partial target on failure."""
    try:
        repository_directory.mkdir(parents=True)
        _git(repository_directory, "init", "--initial-branch=main")
        _git(repository_directory, "fetch", str(workspace), split)
        _git(repository_directory, "checkout", "-B", "main", "FETCH_HEAD")
    except Exception:
        shutil.rmtree(repository_directory, ignore_errors=True)
        raise


def _restore_monolith(definition: AppDefinition, workspace: Path, relative: Path,
    repository_directory: Path, gitmodules: bytes | None) -> None:
    """Roll an interrupted local-submodule transition back to committed source."""
    if definition.directory.exists():
        shutil.rmtree(definition.directory)
    module_metadata = workspace / ".git" / "modules" / definition.name
    if module_metadata.exists():
        shutil.rmtree(module_metadata)
    _remove_local_submodule_config(workspace, definition.name)
    _git(workspace, "reset", "HEAD", "--", str(relative))
    metadata = workspace / ".gitmodules"
    if gitmodules is not None or metadata.exists():
        _git(workspace, "reset", "HEAD", "--", ".gitmodules")
    _git(workspace, "restore", "--source=HEAD", "--worktree", "--", str(relative))
    if gitmodules is None:
        metadata.unlink(missing_ok=True)
    else:
        metadata.write_bytes(gitmodules)
    shutil.rmtree(repository_directory, ignore_errors=True)


def _mount_local_repository(definition: AppDefinition, workspace: Path, relative: Path,
    repository_directory: Path) -> None:
    """Replace committed monolith files with an exact local submodule mount."""
    _git(workspace, "rm", "-r", "--", str(relative))
    if definition.directory.exists():
        shutil.rmtree(definition.directory)
    _git(workspace, "-c", "protocol.file.allow=always", "submodule", "add", "--name",
        definition.name, "--branch", "main", str(repository_directory), str(relative))


def promote_to_submodule(definition: AppDefinition, workspace: Path, *,
    repository_directory: Path) -> Path:
    """Create a local app repository, preserve history, and mount it as a submodule."""
    workspace, repository_directory = workspace.resolve(), repository_directory.resolve()
    relative = _preflight(definition, workspace, repository_directory)
    _commit_pending_app_changes(definition, workspace, relative)
    split = _git(workspace, "subtree", "split", f"--prefix={relative}", "HEAD").splitlines()[-1]
    _create_local_repository(repository_directory, workspace, split)
    metadata = workspace / ".gitmodules"
    gitmodules = metadata.read_bytes() if metadata.is_file() else None
    try:
        _mount_local_repository(definition, workspace, relative, repository_directory)
        mounted = _git(definition.directory, "rev-parse", "HEAD")
        if mounted != split:
            raise RepositoryError(
                f"mounted revision {mounted} does not match exported revision {split}")
        _commit_promotion(definition, workspace, relative, repository_directory, split)
    except Exception as error:
        try:
            _restore_monolith(
                definition, workspace, relative, repository_directory, gitmodules)
        except Exception as recovery_error:
            raise RepositoryError(
                f"promotion failed: {error}; automatic rollback also failed: {recovery_error}"
            ) from error
        raise RepositoryError(f"promotion rolled back after failure: {error}") from error
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
