"""Small polling watcher for rebuilding managed frontend artifacts."""

from collections.abc import Callable
from pathlib import Path
import time

from monotools.apps import AppDefinition
from monotools.lifecycle import build_app


def frontend_inputs(definition: AppDefinition, workspace: Path) -> tuple[Path, ...]:
    """Return every authoritative input that can affect an app's frontend build."""
    inputs = [definition.directory / artifact.source for artifact in definition.artifacts]
    if any(artifact.format == "lit" for artifact in definition.artifacts):
        inputs.extend((workspace / "packages" / "lit-ui" / "src").glob("*.ts"))
        inputs.extend((workspace / name) for name in ("package.json", "package-lock.json"))
        inputs.append(workspace / "scripts" / "build-lit.mjs")
    return tuple(sorted(path for path in inputs if path.is_file()))


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
