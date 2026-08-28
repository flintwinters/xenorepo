"""Reusable build and validation operations."""

from importlib import import_module
import ast
from html import escape
from pathlib import Path
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

from monotools.apps import AppDefinition, FrontendArtifact


class LifecycleError(RuntimeError):
    """Raised when a lifecycle operation cannot complete."""


MAX_SOURCE_LINE_LENGTH = 120
SOURCE_DIRECTORIES = ("apps", "monotools", "packages", "scripts", "tests")
SOURCE_EXCLUDED_DIRECTORIES = frozenset({".venv", "__pycache__", "data", "dist", "node_modules"})
SOURCE_SUFFIXES = frozenset({".py", ".js", ".ts", ".tsx"})


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


def _validate_lit(definition: AppDefinition, workspace: Path) -> None:
    entries = [definition.directory / artifact.source for artifact in definition.artifacts
        if artifact.format == "lit"]
    if not entries:
        return
    node = shutil.which("node")
    if node is None:
        raise LifecycleError("node not found; run python manage.py bootstrap before checking Lit pages")
    command = [node, "scripts/check-lit.mjs",
        *(str(entry.relative_to(workspace)) for entry in entries)]
    completed = subprocess.run(command, cwd=workspace, check=False, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if completed.returncode:
        detail = completed.stdout.strip()
        raise LifecycleError(f"{definition.name} frontend type validation failed:\n{detail}")


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
        f"<meta name=\"xenorepo-artifact\" content=\"{escape(str(artifact.output))}\">\n"
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
        _build_lit(definition, artifact, workspace)


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
        if source.suffix in {".ts", ".js"}:
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
    _validate_lit(definition, workspace)
    py_compile.compile(str(definition.backend_directory / "server.py"), doraise=True)
    module = import_module(definition.module)
    _validate_runtime_contract(definition, module)


def _required_sources(definition: AppDefinition) -> tuple[Path, ...]:
    expected = [
        definition.directory / "app.yaml",
        definition.backend_directory / "server.py",
    ]
    expected.extend(definition.directory / artifact.source for artifact in definition.artifacts)
    if "database" in definition.capabilities:
        expected.extend(
            [definition.backend_directory / "database.py",
                definition.directory / "data" / "README.md"]
        )
    return tuple(expected)


def _validate_runtime_contract(definition: AppDefinition, module: object) -> None:
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
