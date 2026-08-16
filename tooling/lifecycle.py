"""Reusable build and validation operations."""

from importlib import import_module
from pathlib import Path
import py_compile
import shutil
import subprocess

from tooling.apps import AppDefinition, ROOT


class LifecycleError(RuntimeError):
    """Raised when a lifecycle operation cannot complete."""


def _run(command: list[str], cwd: Path = ROOT) -> None:
    completed = subprocess.run(command, cwd=cwd, check=False)
    if completed.returncode:
        raise LifecycleError(f"command failed ({completed.returncode}): {' '.join(command)}")


def build_app(definition: AppDefinition) -> None:
    compiler = shutil.which("tsc")
    if compiler is None:
        raise LifecycleError("TypeScript compiler not found; install tsc before building")
    source = definition.source_directory
    definition.dist_directory.mkdir(exist_ok=True)
    _run([compiler, "--project", str(source / "tsconfig.json")])
    for asset in ("index.html", "styles.css"):
        shutil.copy2(source / asset, definition.dist_directory / asset)


def validate_app(definition: AppDefinition) -> None:
    expected = (
        definition.directory / "app.toml",
        definition.directory / "server.py",
        definition.source_directory / "index.html",
        definition.source_directory / "styles.css",
        definition.source_directory / "calculator.ts",
        definition.source_directory / "tsconfig.json",
    )
    missing = [path.relative_to(ROOT) for path in expected if not path.is_file()]
    if missing:
        raise LifecycleError(f"{definition.name} missing files: {', '.join(map(str, missing))}")
    py_compile.compile(str(definition.directory / "server.py"), doraise=True)
    module = import_module(definition.module)
    if not hasattr(module, "app"):
        raise LifecycleError(f"{definition.module} does not expose a FastAPI 'app'")


def validate_dist(definition: AppDefinition) -> None:
    expected = ("index.html", "styles.css", "calculator.js")
    missing = [name for name in expected if not (definition.dist_directory / name).is_file()]
    if missing:
        raise LifecycleError(f"build did not produce: {', '.join(missing)}")
