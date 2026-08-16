"""Typed discovery for declarative application definitions."""

from dataclasses import dataclass
from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parent.parent
APPS_DIRECTORY = ROOT / "apps"


class AppDefinitionError(ValueError):
    """Raised when application metadata violates its contract."""


@dataclass(frozen=True)
class AppDefinition:
    name: str
    title: str
    directory: Path
    module: str
    frontend_format: str
    capabilities: frozenset[str]

    @property
    def source_directory(self) -> Path:
        return self.directory / "frontend"

    @property
    def dist_directory(self) -> Path:
        return self.directory / "dist"


def load_app(directory: Path) -> AppDefinition:
    metadata_path = directory / "app.toml"
    if not metadata_path.is_file():
        raise AppDefinitionError(f"missing metadata: {metadata_path.relative_to(ROOT)}")
    data = tomllib.loads(metadata_path.read_text(encoding="utf-8"))
    required = ("name", "title", "module")
    missing = [field for field in required if not data.get(field)]
    if missing:
        raise AppDefinitionError(
            f"{metadata_path.relative_to(ROOT)} missing: {', '.join(missing)}"
        )
    if data["name"] != directory.name:
        raise AppDefinitionError(
            f"app name {data['name']!r} must match directory {directory.name!r}"
        )
    frontend_format = data.get("frontend", {}).get("format", "typescript")
    if frontend_format not in {"typescript", "document"}:
        raise AppDefinitionError(
            f"{metadata_path.relative_to(ROOT)} has unsupported frontend format: "
            f"{frontend_format!r}"
        )
    declared_capabilities = data.get("capabilities", [])
    if not isinstance(declared_capabilities, list) or not all(
        isinstance(capability, str) for capability in declared_capabilities
    ):
        raise AppDefinitionError(
            f"{metadata_path.relative_to(ROOT)} capabilities must be a list of strings"
        )
    capabilities = frozenset(declared_capabilities)
    unsupported = capabilities - {"database", "realtime"}
    if unsupported:
        raise AppDefinitionError(
            f"{metadata_path.relative_to(ROOT)} has unsupported capabilities: "
            f"{', '.join(sorted(unsupported))}"
        )
    return AppDefinition(
        name=data["name"],
        title=data["title"],
        directory=directory,
        module=data["module"],
        frontend_format=frontend_format,
        capabilities=capabilities,
    )


def discover_apps() -> tuple[AppDefinition, ...]:
    if not APPS_DIRECTORY.is_dir():
        return ()
    return tuple(
        load_app(directory)
        for directory in sorted(APPS_DIRECTORY.iterdir())
        if directory.is_dir() and not directory.name.startswith((".", "_"))
    )


def get_app(name: str) -> AppDefinition:
    matches = [definition for definition in discover_apps() if definition.name == name]
    if not matches:
        available = ", ".join(app.name for app in discover_apps()) or "none"
        raise AppDefinitionError(f"unknown app {name!r}; available: {available}")
    return matches[0]
