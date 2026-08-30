"""Resolve local dotenv configuration at Monotools lifecycle boundaries.

The resolver keeps local secret loading consistent across imports and child
processes while preserving explicit deployment environment variables.
"""

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
import os
from pathlib import Path

from dotenv import dotenv_values


class EnvironmentConfigurationError(RuntimeError):
    """Raised when a dotenv file cannot produce a valid environment."""


def _dotenv_files(workspace: Path, app_directory: Path | None) -> tuple[Path, ...]:
    if app_directory is None or app_directory.resolve() == workspace.resolve():
        return (workspace / ".env",)
    return (workspace / ".env", app_directory / ".env")


def resolve_dotenv_environment(workspace: Path, app_directory: Path | None = None,
    environ: Mapping[str, str] | None = None) -> dict[str, str]:
    """Resolve environment values with deployment variables retaining authority."""
    resolved: dict[str, str] = {}
    for path in _dotenv_files(workspace, app_directory):
        if not path.is_file():
            continue
        values = dotenv_values(path)
        missing = sorted(key for key, value in values.items() if value is None)
        if missing:
            names = ", ".join(missing)
            raise EnvironmentConfigurationError(f"{path} has variables without values: {names}")
        resolved.update({key: value for key, value in values.items() if value is not None})
    resolved.update(dict(os.environ if environ is None else environ))
    return resolved


@contextmanager
def activated_environment(workspace: Path, app_directory: Path | None = None
    ) -> Iterator[dict[str, str]]:
    """Temporarily activate resolved dotenv values for imports and child processes."""
    original = dict(os.environ)
    resolved = resolve_dotenv_environment(workspace, app_directory, original)
    os.environ.clear()
    os.environ.update(resolved)
    try:
        yield resolved
    finally:
        os.environ.clear()
        os.environ.update(original)
