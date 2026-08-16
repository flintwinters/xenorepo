"""Reusable build and validation operations."""

from importlib import import_module
from html import escape
from pathlib import Path
import py_compile
import shutil
import subprocess

from fastapi.routing import APIWebSocketRoute

from tooling.apps import AppDefinition, FrontendArtifact, ROOT
from tooling.frontend import FrontendCompositionError, compose_document


class LifecycleError(RuntimeError):
    """Raised when a lifecycle operation cannot complete."""


def _run(command: list[str], cwd: Path = ROOT) -> None:
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


def _build_lit(definition: AppDefinition, artifact: FrontendArtifact) -> None:
    npm = shutil.which("npm")
    if npm is None:
        raise LifecycleError("npm not found; run python manage.py bootstrap before building Lit pages")
    bundle = definition.dist_directory / f"{artifact.name}.bundle.js"
    source = definition.directory / artifact.source
    _run([npm, "run", "build:lit", "--", str(source.relative_to(ROOT)), str(bundle.relative_to(ROOT))])
    try:
        script = bundle.read_text(encoding="utf-8")
    finally:
        bundle.unlink(missing_ok=True)
    output = definition.dist_directory / artifact.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "<!doctype html>\n<html lang=\"en\">\n<head>\n"
        "<meta charset=\"utf-8\">\n<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        "<meta name=\"tooling-shell\" content=\"console\">\n"
        f"<title>{escape(definition.title)}</title>\n</head>\n<body>\n<main id=\"app\"></main>\n"
        f"<script>{script}</script>\n</body>\n</html>\n",
        encoding="utf-8",
    )


def build_app(definition: AppDefinition) -> None:
    definition.dist_directory.mkdir(exist_ok=True)
    for artifact in definition.artifacts:
        if artifact.format == "document":
            _build_document(definition, artifact)
            continue
        if artifact.format == "lit":
            _build_lit(definition, artifact)
            continue
        source = definition.directory / artifact.source
        compiler = shutil.which("tsc")
        if compiler is None:
            raise LifecycleError("TypeScript compiler not found; install tsc before building")
        _run([compiler, "--project", str(source.parent / "tsconfig.json")])
        output = definition.dist_directory / artifact.output
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source.parent / "index.html", output)
    return


def validate_app(definition: AppDefinition) -> None:
    expected = [
        definition.directory / "app.yaml",
        definition.directory / "server.py",
    ]
    expected.extend(definition.directory / artifact.source for artifact in definition.artifacts)
    if "database" in definition.capabilities:
        expected.extend(
            [definition.directory / "database.py", definition.directory / "data" / "README.md"]
        )
    missing = [path.relative_to(ROOT) for path in expected if not path.is_file()]
    if missing:
        raise LifecycleError(f"{definition.name} missing files: {', '.join(map(str, missing))}")
    py_compile.compile(str(definition.directory / "server.py"), doraise=True)
    module = import_module(definition.module)
    if not hasattr(module, "app"):
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
