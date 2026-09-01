"""Build and validate managed application artifacts.

This module compiles declared Preact entries, checks source and artifact contracts,
prepares databases, imports services, and coordinates repeatable app tests.
"""

from importlib import import_module
import ast
from html import escape
from pathlib import Path
import json
import os
import py_compile
import re
import shutil
import subprocess
import sys
import threading
from collections.abc import Callable, Mapping

from fastapi import FastAPI
from fastapi.routing import APIWebSocketRoute

from monotools.orchestration.apps import AppDefinition, FrontendArtifact
from monotools.runtime.application import AGENT_TOOLS_ROUTE, api_openapi_schema
from monotools.runtime.openapi import OpenAPIContractError, validate_api_openapi_schema
from monotools.runtime.monoform import MonoFormContractError, monoform_manifest


class LifecycleError(RuntimeError):
    """Raised when a lifecycle operation cannot complete."""


MAX_SOURCE_LINE_LENGTH = 120
SOURCE_DIRECTORIES = ("apps", "monotools", "packages", "tests")
SOURCE_EXCLUDED_DIRECTORIES = frozenset({".venv", "__pycache__", "data", "dist", "node_modules"})
SOURCE_SUFFIXES = frozenset({".py", ".js", ".ts", ".tsx", ".css"})


def validate_source_lines(workspace: Path) -> None:
    """Reject unreadably wide Python and TypeScript source lines."""
    violations = [violation for path in _source_candidates(workspace)
        for violation in _line_violations(path, workspace)]
    if violations:
        detail = "\n".join(violations)
        raise LifecycleError(f"source line length validation failed:\n{detail}")


def _source_candidates(workspace: Path) -> tuple[Path, ...]:
    candidates = [
        path
        for directory in SOURCE_DIRECTORIES
        if (root := workspace / directory).is_dir()
        for path in root.rglob("*")
        if path.suffix in SOURCE_SUFFIXES
        and not SOURCE_EXCLUDED_DIRECTORIES.intersection(path.parts)
    ]
    candidates.extend(path for path in workspace.glob("*") if path.suffix in SOURCE_SUFFIXES)
    return tuple(sorted(candidates))


def _line_violations(path: Path, workspace: Path) -> tuple[str, ...]:
    relative = path.relative_to(workspace)
    return tuple(
        f"{relative}:{number}: {len(line)} characters (maximum {MAX_SOURCE_LINE_LENGTH})"
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if len(line) > MAX_SOURCE_LINE_LENGTH
    )


def _run(command: list[str], cwd: Path) -> None:
    completed = subprocess.run(command, cwd=cwd, check=False)
    if completed.returncode:
        raise LifecycleError(f"command failed ({completed.returncode}): {' '.join(command)}")


def _validate_frontend(definition: AppDefinition, workspace: Path) -> None:
    entries = [definition.directory / artifact.source for artifact in definition.artifacts
        if artifact.source is not None]
    if not entries:
        return
    from monotools.orchestration.hygiene import analyze_ui_hygiene

    analyze_ui_hygiene(definition, workspace)
    node = shutil.which("node")
    if node is None:
        raise LifecycleError("node not found; run python manage.py bootstrap before checking frontends")
    command = [node, "monotools/node/check-frontend.mjs",
        *(str(entry.relative_to(workspace)) for entry in entries)]
    completed = subprocess.run(command, cwd=workspace, check=False, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if completed.returncode:
        detail = completed.stdout.strip()
        raise LifecycleError(f"{definition.name} frontend type validation failed:\n{detail}")


def _build_frontend(definition: AppDefinition, artifact: FrontendArtifact, workspace: Path) -> None:
    if artifact.format == "monoform":
        _build_monoform(definition, artifact, workspace)
        return
    npm = shutil.which("npm")
    if npm is None:
        raise LifecycleError("npm not found; run python manage.py bootstrap before building Preact pages")
    bundle = definition.dist_directory / f"{artifact.name}.bundle.js"
    stylesheet = definition.dist_directory / f"{artifact.name}.bundle.css"
    source = definition.directory / artifact.source
    _run([npm, "run", "build:preact", "--", str(source.relative_to(workspace)),
        str(bundle.relative_to(workspace)), str(stylesheet.relative_to(workspace))], workspace)
    try:
        script = bundle.read_text(encoding="utf-8")
        styles = stylesheet.read_text(encoding="utf-8")
    finally:
        bundle.unlink(missing_ok=True)
        stylesheet.unlink(missing_ok=True)
    _write_document(definition, artifact, script, styles)


def _build_monoform(definition: AppDefinition, artifact: FrontendArtifact, workspace: Path) -> None:
    node = shutil.which("node")
    if node is None:
        raise LifecycleError("node not found; run python manage.py bootstrap before building MonoForm pages")
    staging = definition.directory / "data" / "monoform-build" / artifact.name
    staging.mkdir(parents=True, exist_ok=True)
    bundle = staging / "bundle.js"
    stylesheet = staging / "bundle.css"
    operations = staging / "operations.json"
    operations.write_text(json.dumps(artifact.operations) + "\n", encoding="utf-8")
    manifest = definition.directory / "data" / "monoform.json"
    _run([node, "monotools/node/build-monoform.mjs", str(manifest.relative_to(workspace)),
        str(operations.relative_to(workspace)), str(bundle.relative_to(workspace)),
        str(stylesheet.relative_to(workspace))], workspace)
    script = bundle.read_text(encoding="utf-8")
    styles = stylesheet.read_text(encoding="utf-8")
    staged_artifact = staging / "artifact.html"
    _write_document(definition, artifact, script, styles, output=staged_artifact)
    output = definition.dist_directory / artifact.output
    output.parent.mkdir(parents=True, exist_ok=True)
    os.replace(staged_artifact, output)


def _write_document(definition: AppDefinition, artifact: FrontendArtifact,
    script: str, styles: str, *, output: Path | None = None) -> None:
    output = output or definition.dist_directory / artifact.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "<!doctype html>\n<html lang=\"en\">\n<head>\n"
        "<meta charset=\"utf-8\">\n<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        "<meta name=\"monotools-shell\" content=\"console\">\n"
        f"<meta name=\"xenorepo-artifact\" content=\"{escape(str(artifact.output))}\">\n"
        f"<title>{escape(definition.title)}</title>\n"
        "<style>html,body,#app{width:100%;height:100%;margin:0}"
        "html,body{overflow:hidden;background:#1d2021;color:#ebdbb2}"
        f"{styles}</style>\n"
        "</head>\n<body>\n<div id=\"app\"></div>\n"
        f"<script>{script}</script>\n</body>\n</html>\n",
        encoding="utf-8",
    )


def build_app(definition: AppDefinition, workspace: Path) -> None:
    definition.dist_directory.mkdir(exist_ok=True)
    for artifact in definition.artifacts:
        _build_frontend(definition, artifact, workspace)


_SHARED_PACKAGE_IMPORT = re.compile(
    r"(?:from\s+|import\s*(?:\([^)]*?from\s+)?)[\"'](@xenorepo/[^/\"']+)[\"']"
)


def _declared_source_imports(definition: AppDefinition) -> tuple[str, ...]:
    """Discover cross-boundary production imports owned by one monoapp."""
    discovered: set[str] = set()
    python_sources = (definition.directory / "manage.py", *definition.backend_directory.rglob("*.py"))
    for source in python_sources:
        discovered.update(_python_shared_imports(source))
    for source in definition.source_directory.rglob("*"):
        if source.suffix in {".ts", ".tsx", ".js"}:
            discovered.update(_SHARED_PACKAGE_IMPORT.findall(source.read_text(encoding="utf-8")))
    return tuple(sorted(discovered))


def _python_shared_imports(source: Path) -> tuple[str, ...]:
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
        elif isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
    return tuple(name for name in names if name.startswith("monotools."))


def _validate_declared_imports(definition: AppDefinition) -> None:
    discovered = _declared_source_imports(definition)
    if definition.imports != discovered:
        missing = sorted(set(discovered) - set(definition.imports))
        unused = sorted(set(definition.imports) - set(discovered))
        details = []
        if missing:
            details.append(f"undeclared: {', '.join(missing)}")
        if unused:
            details.append(f"not imported: {', '.join(unused)}")
        raise LifecycleError(f"{definition.name} app.yaml imports do not match source ({'; '.join(details)})")


def validate_app(definition: AppDefinition, workspace: Path) -> None:
    missing = [path.relative_to(workspace) for path in _required_sources(definition)
        if not path.is_file()]
    if missing:
        raise LifecycleError(f"{definition.name} missing files: {', '.join(map(str, missing))}")
    _validate_declared_imports(definition)
    py_compile.compile(str(definition.backend_directory / "server.py"), doraise=True)
    module = import_module(definition.module)
    _validate_runtime_contract(definition, module)
    _generate_openapi_types(definition, module.app, workspace)
    _validate_frontend(definition, workspace)


def _generate_openapi_types(definition: AppDefinition, application: FastAPI,
    workspace: Path) -> None:
    """Generate deterministic app-owned declarations for HTTP API routes only."""
    schema = api_openapi_schema(application)
    try:
        validate_api_openapi_schema(schema)
    except OpenAPIContractError as error:
        raise LifecycleError(f"{definition.name} {error}") from error
    data_directory = definition.directory / "data"
    data_directory.mkdir(exist_ok=True)
    try:
        manifest = monoform_manifest(schema, app=definition.name, title=definition.title)
    except MonoFormContractError as error:
        raise LifecycleError(f"{definition.name} MonoForm contract failed: {error}") from error
    manifest_path = data_directory / "monoform.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    schema_path = data_directory / "openapi.json"
    declaration = data_directory / "openapi.d.ts"
    schema_path.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    generator = workspace / "node_modules" / ".bin" / "openapi-typescript"
    if not generator.is_file():
        raise LifecycleError("openapi-typescript not found; run python manage.py bootstrap")
    _run([str(generator), str(schema_path), "--output", str(declaration)], workspace)


def _required_sources(definition: AppDefinition) -> tuple[Path, ...]:
    expected = [
        definition.directory / "app.yaml",
        definition.backend_directory / "server.py",
    ]
    expected.extend(definition.directory / artifact.source for artifact in definition.artifacts
        if artifact.source is not None)
    if "database" in definition.capabilities:
        expected.extend(
            [definition.backend_directory / "database.py",
                definition.directory / "data" / "README.md"]
        )
    return tuple(expected)


def _validate_runtime_contract(definition: AppDefinition, module: object) -> None:
    if not isinstance(getattr(module, "app", None), FastAPI):
        raise LifecycleError(f"{definition.module} does not expose a FastAPI 'app'")
    if not any(getattr(route, "path", None) == AGENT_TOOLS_ROUTE
        for route in module.app.routes):
        raise LifecycleError(
            f"{definition.name} does not expose the platform {AGENT_TOOLS_ROUTE} registry"
        )
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
        "source": all(artifact.source is None or (definition.directory / artifact.source).is_file()
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
        from monotools.orchestration.watch import watch_frontend

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
