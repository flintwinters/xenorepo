"""Watch managed frontend inputs and rebuild changed artifacts.

This polling implementation follows declared entries and their local or shared
imports, producing deterministic rebuilds without app-specific watch scripts.
"""

from collections.abc import Callable
from pathlib import Path
import time

from monotools.orchestration.apps import AppDefinition
from monotools.orchestration.lifecycle import build_app, frontend_inputs


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
