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
_FORMATS = frozenset({"lit"})


class AppDefinitionError(ValueError):
    """Raised when application metadata violates its contract."""


def specification_path(directory: Path) -> Path:
    """Return the canonical product specification path for any app state."""
    return directory / "SPEC.md"


@dataclass(frozen=True)
class PlannedApp:
    """A deliberately non-runnable app represented only by its specification."""

    name: str
    directory: Path

    @property
    def specification(self) -> Path:
        return specification_path(self.directory)


@dataclass(frozen=True)
class FrontendArtifact:
    """One independently-built document declared by an application."""

    name: str
    format: str
    source: Path
    output: Path


@dataclass(frozen=True)
class AppDefinition:
    name: str
    title: str
    directory: Path
    module: str
    artifacts: tuple[FrontendArtifact, ...]
    routes: tuple[tuple[str, str], ...]
    capabilities: frozenset[str]
    imports: tuple[str, ...] = ()

    @property
    def specification(self) -> Path:
        return specification_path(self.directory)

    @property
    def source_directory(self) -> Path:
        """Application-owned frontend source directory."""
        return self.directory / "frontend"

    @property
    def backend_directory(self) -> Path:
        """Application-owned Python implementation package."""
        return self.directory / "backend"

    @property
    def dist_directory(self) -> Path:
        return self.directory / "dist"

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


def _imports(value: object, path: Path) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise AppDefinitionError(f"{_display(path)} imports must be a list of non-empty strings")
    if value != sorted(set(value)):
        raise AppDefinitionError(f"{_display(path)} imports must be unique and sorted")
    unsupported = [item for item in value if not _is_shared_import(item)]
    if unsupported:
        raise AppDefinitionError(
            f"{_display(path)} imports must name shared Monotools or Xenorepo modules: "
            f"{', '.join(unsupported)}"
        )
    return tuple(value)


def _is_shared_import(name: str) -> bool:
    return name.startswith("monotools.") or name.startswith("@xenorepo/")


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


def _artifact(name: str, raw: object, path: Path) -> FrontendArtifact:
    if not _ARTIFACT_NAME.fullmatch(name):
        raise AppDefinitionError(f"{_display(path)} invalid frontend artifact name: {name!r}")
    label = f"frontend.artifacts.{name}"
    item = _mapping(raw, path, label)
    _only_keys(item, frozenset({"format", "source", "output"}), path, label)
    format_name = _string(item.get("format"), path, f"{label}.format")
    if format_name not in _FORMATS:
        raise AppDefinitionError(f"{_display(path)} has unsupported frontend format: {format_name!r}")
    source = _relative_path(item.get("source"), path, f"{label}.source")
    if source.suffix not in {".js", ".ts"}:
        raise AppDefinitionError(
            f"{_display(path)} frontend artifact source must be compilable JavaScript or TypeScript"
        )
    output = _relative_path(item.get("output"), path, f"{label}.output")
    if output.suffix != ".html":
        raise AppDefinitionError(f"{_display(path)} frontend artifact output must end in .html")
    return FrontendArtifact(name, format_name, source, output)


def _artifacts(value: object, path: Path) -> tuple[FrontendArtifact, ...]:
    declared = _mapping(value, path, "frontend.artifacts")
    if not declared:
        raise AppDefinitionError(f"{_display(path)} frontend.artifacts must not be empty")
    return tuple(_artifact(name, raw, path) for name, raw in declared.items())


def _routes(value: object, artifacts: tuple[FrontendArtifact, ...], path: Path) -> tuple[tuple[str, str], ...]:
    declared = _mapping(value, path, "frontend.routes")
    if not declared:
        raise AppDefinitionError(f"{_display(path)} frontend.routes must not be empty")
    artifact_names = {artifact.name for artifact in artifacts}
    return tuple(_route(route, artifact_name, artifact_names, path)
        for route, artifact_name in declared.items())


def _route(route: str, artifact_name: object, artifact_names: set[str],
    path: Path) -> tuple[str, str]:
    if not _ROUTE_PATH.fullmatch(route) or any(marker in route for marker in ("//", "?", "#")):
        raise AppDefinitionError(f"{_display(path)} has invalid route: {route!r}")
    if route in _RESERVED_ROUTES:
        raise AppDefinitionError(f"{_display(path)} route {route!r} is reserved by the platform")
    if not isinstance(artifact_name, str) or artifact_name not in artifact_names:
        raise AppDefinitionError(
            f"{_display(path)} route {route!r} references unknown frontend artifact {artifact_name!r}"
        )
    return route, artifact_name


def _validate_structure(directory: Path, name: str, module: str,
    artifacts: tuple[FrontendArtifact, ...]) -> None:
    """Reject monoapps that blur their administrative and implementation roots."""
    missing = [child for child in ("frontend", "backend")
        if not (directory / child).is_dir()]
    if missing:
        raise AppDefinitionError(
            f"{_display(directory)} missing required directories: {', '.join(missing)}"
        )
    _validate_administrative_root(directory)
    expected_module = f"apps.{name}.backend.server"
    if module != expected_module:
        raise AppDefinitionError(f"{_display(directory)} module must be {expected_module!r}")
    outside_frontend = sorted(str(artifact.source) for artifact in artifacts
        if not artifact.source.parts or artifact.source.parts[0] != "frontend")
    if outside_frontend:
        raise AppDefinitionError(
            f"{_display(directory)} frontend sources must be beneath frontend/: "
            f"{', '.join(outside_frontend)}"
        )


def _validate_administrative_root(directory: Path) -> None:
    root_python = sorted(path.name for path in directory.glob("*.py"))
    if root_python != ["manage.py"]:
        found = ", ".join(root_python) or "none"
        raise AppDefinitionError(
            f"{_display(directory)} root Python files must be exactly manage.py; found: {found}"
        )


def load_app(directory: Path) -> AppDefinition:
    metadata_path = _metadata_path(directory)
    if not metadata_path.is_file():
        raise AppDefinitionError(f"missing metadata: {_display(metadata_path)}")
    data = _load_yaml(metadata_path)
    _only_keys(data, frozenset({"name", "title", "module", "capabilities", "imports", "frontend"}), metadata_path,
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
    _validate_structure(directory, name, module, artifacts)
    declared_capabilities = data.get("capabilities", [])
    if not isinstance(declared_capabilities, list) or not all(isinstance(item, str) for item in declared_capabilities):
        raise AppDefinitionError(f"{_display(metadata_path)} capabilities must be a list of strings")
    capabilities = frozenset(declared_capabilities)
    unsupported = capabilities - {"database", "realtime"}
    if unsupported:
        raise AppDefinitionError(
            f"{_display(metadata_path)} has unsupported capabilities: {', '.join(sorted(unsupported))}"
        )
    imports = _imports(data.get("imports", []), metadata_path)
    return AppDefinition(name, title, directory, module, artifacts, routes, capabilities, imports)


def discover_apps() -> tuple[AppDefinition, ...]:
    if not APPS_DIRECTORY.is_dir():
        return ()
    return tuple(load_app(directory) for directory in sorted(APPS_DIRECTORY.iterdir())
                 if directory.is_dir() and not directory.name.startswith((".", "_"))
                 and not is_planned_app(directory))


def is_planned_app(directory: Path) -> bool:
    """Return whether a visible directory is intentionally specification-only."""
    return (directory / "SPEC.md").is_file() and set(path.name for path in directory.iterdir()) == {"SPEC.md"}


def discover_planned_apps(apps_directory: Path = APPS_DIRECTORY) -> tuple[PlannedApp, ...]:
    """Discover plans without admitting incomplete apps to the runnable catalog."""
    if not apps_directory.is_dir():
        return ()
    return tuple(PlannedApp(directory.name, directory) for directory in sorted(apps_directory.iterdir())
        if directory.is_dir() and not directory.name.startswith((".", "_")) and is_planned_app(directory))


def get_app(name: str) -> AppDefinition:
    matches = [definition for definition in discover_apps() if definition.name == name]
    if not matches:
        available = ", ".join(app.name for app in discover_apps()) or "none"
        raise AppDefinitionError(f"unknown app {name!r}; available: {available}")
    return matches[0]
