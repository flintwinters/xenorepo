"""Watch managed frontend inputs and rebuild changed artifacts.

This polling implementation follows declared entries and their local or shared
imports, producing deterministic rebuilds without app-specific watch scripts.
"""

from collections.abc import Callable
from pathlib import Path
import time

from monotools.orchestration.apps import AppDefinition
from monotools.orchestration.lifecycle import build_app


def frontend_inputs(definition: AppDefinition, workspace: Path) -> tuple[Path, ...]:
    """Return every authoritative input that can affect an app's frontend build."""
    inputs = [definition.directory / artifact.source for artifact in definition.artifacts]
    inputs.extend(_frontend_tooling_inputs(definition, workspace))
    return tuple(sorted(path for path in inputs if path.is_file()))


def _frontend_tooling_inputs(definition: AppDefinition, workspace: Path) -> tuple[Path, ...]:
    inputs = [*(_files_beneath(definition.directory / "frontend")),
        *(_files_beneath(workspace / "packages" / "ui" / "src")),
        *(workspace / name for name in
            ("package.json", "package-lock.json", "tsconfig.preact.json")),
        *(workspace / "monotools" / "node" / name for name in
            ("build-preact.mjs", "check-frontend.mjs")),
        *(_files_beneath(workspace / "types"))]
    return tuple(inputs)


def _files_beneath(directory: Path) -> tuple[Path, ...]:
    return tuple(path for path in directory.rglob("*") if path.is_file())


def _snapshot(paths: tuple[Path, ...]) -> tuple[tuple[Path, int], ...]:
    return tuple((path, path.stat().st_mtime_ns) for path in paths)


def watch_frontend(definition: AppDefinition, workspace: Path, report: Callable[[str], None],
    interval: float = 0.5) -> None:
    """Rebuild an app whenever one of its declared frontend inputs changes."""
    previous = _snapshot(frontend_inputs(definition, workspace))
    while True:
        time.sleep(interval)
        current = _snapshot(frontend_inputs(definition, workspace))
        if current == previous:
            continue
        previous = current
        try:
            build_app(definition, workspace)
        except Exception as error:
            report(f"Frontend rebuild failed: {error}")
        else:
            report(f"Rebuilt {definition.name} frontend")
