"""Typed discovery for declarative YAML application definitions."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import re

from ruamel.yaml import YAML
from ruamel.yaml.constructor import DuplicateKeyError
from ruamel.yaml.error import YAMLError


ROOT = Path(__file__).resolve().parent.parent
APPS_DIRECTORY = ROOT / "apps"
_ARTIFACT_NAME = re.compile(r"^[a-z][a-z0-9_-]*$")
_ROUTE_PATH = re.compile(r"^/[A-Za-z0-9._~!$&'()*+,;=:@%/-]*$")
_RESERVED_ROUTES = frozenset({"/health"})
_FORMATS = frozenset({"document", "lit"})


class AppDefinitionError(ValueError):
    """Raised when application metadata violates its contract."""


@dataclass(frozen=True)
class FrontendArtifact:
    """One independently-built document declared by an application."""

    name: str
    format: str
    source: Path
    output: Path
    shell: str | None = None


@dataclass(frozen=True)
class AppDefinition:
    name: str
    title: str
    directory: Path
    module: str
    artifacts: tuple[FrontendArtifact, ...]
    routes: tuple[tuple[str, str], ...]
    capabilities: frozenset[str]

    @property
    def source_directory(self) -> Path:
        """Compatibility location for legacy frontend inputs."""
        return self.directory / "frontend"

    @property
    def dist_directory(self) -> Path:
        return self.directory / "dist"

    @property
    def frontend_format(self) -> str:
        """Compatibility view for legacy single-page callers."""
        return self.artifacts[0].format

    @property
    def frontend_shell(self) -> str | None:
        """Compatibility view for legacy single-page callers."""
        return self.artifacts[0].shell

    def artifact(self, name: str) -> FrontendArtifact:
        for artifact in self.artifacts:
            if artifact.name == name:
                return artifact
        raise AppDefinitionError(f"{self.name} has no frontend artifact {name!r}")

    def document_for_route(self, route: str) -> Path:
        for declared_route, artifact_name in self.routes:
            if declared_route == route:
                return self.dist_directory / self.artifact(artifact_name).output
        raise AppDefinitionError(f"{self.name} has no document route {route!r}")


def _metadata_path(directory: Path) -> Path:
    return directory / "app.yaml"


def _display(path: Path) -> str:
    return str(path.relative_to(ROOT))


def _mapping(value: object, path: Path, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise AppDefinitionError(f"{_display(path)} {label} must be a mapping")
    if not all(isinstance(key, str) for key in value):
        raise AppDefinitionError(f"{_display(path)} {label} keys must be strings")
    return value


def _only_keys(value: Mapping[str, object], allowed: frozenset[str], path: Path, label: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise AppDefinitionError(f"{_display(path)} {label} has unknown keys: {', '.join(unknown)}")


def _string(value: object, path: Path, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise AppDefinitionError(f"{_display(path)} {label} must be a non-empty string")
    return value


def _relative_path(value: object, path: Path, label: str) -> Path:
    raw = _string(value, path, label)
    candidate = PurePosixPath(raw)
    if candidate.is_absolute() or ".." in candidate.parts or raw != candidate.as_posix():
        raise AppDefinitionError(f"{_display(path)} {label} must be a normalized relative path")
    if raw == ".":
        raise AppDefinitionError(f"{_display(path)} {label} must name a file")
    return Path(*candidate.parts)


def _load_yaml(path: Path) -> Mapping[str, object]:
    loader = YAML(typ="safe")
    loader.allow_duplicate_keys = False
    try:
        data = loader.load(path)
    except DuplicateKeyError as error:
        raise AppDefinitionError(f"{_display(path)} contains a duplicate key: {error.problem}") from error
    except YAMLError as error:
        raise AppDefinitionError(f"{_display(path)} is malformed YAML: {error.problem or error}") from error
    return _mapping(data, path, "document")


def _artifacts(value: object, path: Path) -> tuple[FrontendArtifact, ...]:
    declared = _mapping(value, path, "frontend.artifacts")
    if not declared:
        raise AppDefinitionError(f"{_display(path)} frontend.artifacts must not be empty")
    result: list[FrontendArtifact] = []
    for name, raw in declared.items():
        if not _ARTIFACT_NAME.fullmatch(name):
            raise AppDefinitionError(f"{_display(path)} invalid frontend artifact name: {name!r}")
        item = _mapping(raw, path, f"frontend.artifacts.{name}")
        _only_keys(item, frozenset({"format", "source", "output", "shell"}), path,
            f"frontend.artifacts.{name}")
        format_name = _string(item.get("format"), path, f"frontend.artifacts.{name}.format")
        if format_name not in _FORMATS:
            raise AppDefinitionError(f"{_display(path)} has unsupported frontend format: {format_name!r}")
        source = _relative_path(item.get("source"), path, f"frontend.artifacts.{name}.source")
        output = _relative_path(item.get("output"), path, f"frontend.artifacts.{name}.output")
        if output.suffix != ".html":
            raise AppDefinitionError(f"{_display(path)} frontend artifact output must end in .html")
        shell = item.get("shell")
        if shell is not None and shell != "console":
            raise AppDefinitionError(f"{_display(path)} has unsupported frontend shell: {shell!r}")
        if format_name == "document" and shell is None:
            raise AppDefinitionError(f"{_display(path)} document frontend must declare a shell")
        if format_name not in {"document", "lit"} and shell is not None:
            raise AppDefinitionError(f"{_display(path)} shell requires document or Lit frontend format")
        result.append(FrontendArtifact(name, format_name, source, output, shell))
    return tuple(result)


def _routes(value: object, artifacts: tuple[FrontendArtifact, ...], path: Path) -> tuple[tuple[str, str], ...]:
    declared = _mapping(value, path, "frontend.routes")
    if not declared:
        raise AppDefinitionError(f"{_display(path)} frontend.routes must not be empty")
    artifact_names = {artifact.name for artifact in artifacts}
    result: list[tuple[str, str]] = []
    for route, artifact_name in declared.items():
        if not _ROUTE_PATH.fullmatch(route) or "//" in route or "?" in route or "#" in route:
            raise AppDefinitionError(f"{_display(path)} has invalid route: {route!r}")
        if route in _RESERVED_ROUTES:
            raise AppDefinitionError(f"{_display(path)} route {route!r} is reserved by the platform")
        if not isinstance(artifact_name, str) or artifact_name not in artifact_names:
            raise AppDefinitionError(
                f"{_display(path)} route {route!r} references unknown frontend artifact {artifact_name!r}"
            )
        result.append((route, artifact_name))
    return tuple(result)


def load_app(directory: Path) -> AppDefinition:
    metadata_path = _metadata_path(directory)
    if not metadata_path.is_file():
        raise AppDefinitionError(f"missing metadata: {_display(metadata_path)}")
    data = _load_yaml(metadata_path)
    _only_keys(data, frozenset({"name", "title", "module", "capabilities", "frontend"}), metadata_path,
        "document")
    name = _string(data.get("name"), metadata_path, "name")
    title = _string(data.get("title"), metadata_path, "title")
    module = _string(data.get("module"), metadata_path, "module")
    if name != directory.name:
        raise AppDefinitionError(f"app name {name!r} must match directory {directory.name!r}")
    frontend = _mapping(data.get("frontend"), metadata_path, "frontend")
    _only_keys(frontend, frozenset({"artifacts", "routes"}), metadata_path, "frontend")
    artifacts = _artifacts(frontend.get("artifacts"), metadata_path)
    routes = _routes(frontend.get("routes"), artifacts, metadata_path)
    declared_capabilities = data.get("capabilities", [])
    if not isinstance(declared_capabilities, list) or not all(isinstance(item, str) for item in declared_capabilities):
        raise AppDefinitionError(f"{_display(metadata_path)} capabilities must be a list of strings")
    capabilities = frozenset(declared_capabilities)
    unsupported = capabilities - {"database", "realtime"}
    if unsupported:
        raise AppDefinitionError(
            f"{_display(metadata_path)} has unsupported capabilities: {', '.join(sorted(unsupported))}"
        )
    return AppDefinition(name, title, directory, module, artifacts, routes, capabilities)


def discover_apps() -> tuple[AppDefinition, ...]:
    if not APPS_DIRECTORY.is_dir():
        return ()
    return tuple(load_app(directory) for directory in sorted(APPS_DIRECTORY.iterdir())
                 if directory.is_dir() and not directory.name.startswith((".", "_")))


def get_app(name: str) -> AppDefinition:
    matches = [definition for definition in discover_apps() if definition.name == name]
    if not matches:
        available = ", ".join(app.name for app in discover_apps()) or "none"
        raise AppDefinitionError(f"unknown app {name!r}; available: {available}")
    return matches[0]
