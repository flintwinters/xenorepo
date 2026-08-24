"""Reusable build and validation operations."""

from importlib import import_module
from html import escape
from pathlib import Path
import os
import py_compile
import shutil
import subprocess
import sys
import threading
from collections.abc import Callable, Mapping

from fastapi import FastAPI
from fastapi.routing import APIWebSocketRoute

from monotools.apps import AppDefinition, FrontendArtifact
from monotools.frontend import FrontendCompositionError, compose_document


class LifecycleError(RuntimeError):
    """Raised when a lifecycle operation cannot complete."""


def _run(command: list[str], cwd: Path) -> None:
    completed = subprocess.run(command, cwd=cwd, check=False)
    if completed.returncode:
        raise LifecycleError(f"command failed ({completed.returncode}): {' '.join(command)}")


def _build_document(definition: AppDefinition, artifact: FrontendArtifact) -> None:
    source = definition.directory / artifact.source
    try:
        document = compose_document(source, artifact.shell or "")
    except FrontendCompositionError as error:
        raise LifecycleError(str(error)) from error
    output = definition.dist_directory / artifact.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(document, encoding="utf-8")


def _build_lit(definition: AppDefinition, artifact: FrontendArtifact, workspace: Path) -> None:
    npm = shutil.which("npm")
    if npm is None:
        raise LifecycleError("npm not found; run python manage.py bootstrap before building Lit pages")
    bundle = definition.dist_directory / f"{artifact.name}.bundle.js"
    source = definition.directory / artifact.source
    _run([npm, "run", "build:lit", "--", str(source.relative_to(workspace)),
        str(bundle.relative_to(workspace))], workspace)
    try:
        script = bundle.read_text(encoding="utf-8")
    finally:
        bundle.unlink(missing_ok=True)
    output = definition.dist_directory / artifact.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "<!doctype html>\n<html lang=\"en\">\n<head>\n"
        "<meta charset=\"utf-8\">\n<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        "<meta name=\"monotools-shell\" content=\"console\">\n"
        f"<title>{escape(definition.title)}</title>\n"
        "<style>html,body,#app{width:100%;height:100%;margin:0}"
        "html,body{overflow:hidden;background:#1d2021;color:#ebdbb2}</style>\n"
        "</head>\n<body>\n<main id=\"app\"></main>\n"
        f"<script>{script}</script>\n</body>\n</html>\n",
        encoding="utf-8",
    )


def build_app(definition: AppDefinition, workspace: Path) -> None:
    definition.dist_directory.mkdir(exist_ok=True)
    for artifact in definition.artifacts:
        if artifact.format == "document":
            _build_document(definition, artifact)
            continue
        if artifact.format == "lit":
            _build_lit(definition, artifact, workspace)
            continue


def validate_app(definition: AppDefinition, workspace: Path) -> None:
    expected = [
        definition.directory / "app.yaml",
        definition.directory / "server.py",
    ]
    expected.extend(definition.directory / artifact.source for artifact in definition.artifacts)
    if "database" in definition.capabilities:
        expected.extend(
            [definition.directory / "database.py", definition.directory / "data" / "README.md"]
        )
    missing = [path.relative_to(workspace) for path in expected if not path.is_file()]
    if missing:
        raise LifecycleError(f"{definition.name} missing files: {', '.join(map(str, missing))}")
    py_compile.compile(str(definition.directory / "server.py"), doraise=True)
    module = import_module(definition.module)
    if not isinstance(getattr(module, "app", None), FastAPI):
        raise LifecycleError(f"{definition.module} does not expose a FastAPI 'app'")
    if "realtime" in definition.capabilities and not any(
        isinstance(route, APIWebSocketRoute) for route in module.app.routes
    ):
        raise LifecycleError(
            f"{definition.name} declares realtime but exposes no WebSocket route"
        )


def validate_dist(definition: AppDefinition) -> None:
    expected = [artifact.output for artifact in definition.artifacts]
    missing = [str(name) for name in expected if not (definition.dist_directory / name).is_file()]
    if missing:
        raise LifecycleError(f"build did not produce: {', '.join(missing)}")


def collect_app_status(definition: AppDefinition) -> dict[str, bool]:
    """Collect an application's source and artifact health without mutation."""
    return {
        "source": all((definition.directory / artifact.source).is_file()
            for artifact in definition.artifacts),
        "readme": (definition.directory / "README.md").is_file(),
        "data": (definition.directory / "data").is_dir(),
        "dist": all((definition.dist_directory / artifact.output).is_file()
            for artifact in definition.artifacts),
    }


def run_test_suite(directory: Path, suite: Path) -> int:
    """Run one unittest suite and return its process status."""
    completed = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", str(suite), "-v"],
        cwd=directory,
        check=False,
    )
    return completed.returncode


def serve_app(definition: AppDefinition, workspace: Path, *, host: str = "127.0.0.1",
    port: int = 8000, watch: bool = False, environment: Mapping[str, str] | None = None,
    report: Callable[[str], None] = print) -> int:
    """Build and run one FastAPI app, optionally watching its frontend inputs."""
    validate_app(definition, workspace)
    build_app(definition, workspace)
    validate_dist(definition)
    if watch:
        from monotools.watch import watch_frontend

        threading.Thread(
            target=watch_frontend,
            args=(definition, workspace, report),
            daemon=True,
            name=f"{definition.name}-frontend-watch",
        ).start()
    completed = subprocess.run(
        [sys.executable, "-m", "uvicorn", definition.module + ":app", "--host", host,
            "--port", str(port)],
        cwd=workspace,
        env=os.environ | dict(environment or {}),
        check=False,
    )
    return completed.returncode
