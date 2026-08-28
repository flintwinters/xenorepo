"""Read-only architecture and structural audits for a Monotools workspace."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import ast
import json
import re
import subprocess

from monotools.apps import AppDefinition


SOURCE_ROOTS = ("apps", "monotools", "packages", "scripts", "tests")
SOURCE_SUFFIXES = frozenset({".py", ".js", ".ts", ".tsx", ".html"})
TEXT_SUFFIXES = SOURCE_SUFFIXES | frozenset({".md", ".json", ".toml", ".yaml", ".yml"})
EXCLUDED_PARTS = frozenset({".git", ".venv", "data", "dist", "historic", "node_modules", "__pycache__"})
MAX_SOURCE_LINES = 600
MAX_CYCLOMATIC_COMPLEXITY = 8
_SCRIPT_IMPORT = re.compile(r"(?:from\s+|import\s*)[\"']([^\"']+)[\"']")
_CUSTOM_ELEMENT = re.compile(r'customElements\.define\(["\'](x-[a-z0-9-]+)["\']')


@dataclass(frozen=True, order=True)
class AuditViolation:
    category: str
    path: str
    detail: str


@dataclass(frozen=True)
class AuditReport:
    architecture: tuple[AuditViolation, ...]
    large_files: tuple[AuditViolation, ...]
    complex_functions: tuple[AuditViolation, ...]


def _source_files(workspace: Path) -> tuple[Path, ...]:
    candidates = [
        path
        for root_name in SOURCE_ROOTS
        if (root := workspace / root_name).is_dir()
        for path in root.rglob("*")
        if path.is_file() and path.suffix in SOURCE_SUFFIXES
        and not EXCLUDED_PARTS.intersection(path.relative_to(workspace).parts)
    ]
    candidates.extend(path for path in workspace.iterdir()
        if path.is_file() and path.suffix in SOURCE_SUFFIXES)
    return tuple(sorted(set(candidates)))


def _central_text_files(workspace: Path) -> tuple[Path, ...]:
    roots = [workspace, workspace / "monotools", workspace / "packages", workspace / "scripts",
        workspace / "tests"]
    candidates: set[Path] = set()
    for root in roots:
        if not root.is_dir():
            continue
        iterator = root.iterdir() if root == workspace else root.rglob("*")
        candidates.update(path for path in iterator if path.is_file() and path.suffix in TEXT_SUFFIXES
            and path.name not in {"package-lock.json", "uv.lock"}
            and not EXCLUDED_PARTS.intersection(path.relative_to(workspace).parts))
    return tuple(sorted(candidates))


def _central_identity_violations(workspace: Path,
    definitions: tuple[AppDefinition, ...]) -> list[AuditViolation]:
    patterns = [(definition.name, re.compile(rf"(?<![A-Za-z0-9_]){re.escape(definition.name)}(?![A-Za-z0-9_])",
        re.IGNORECASE)) for definition in definitions]
    violations: list[AuditViolation] = []
    for path in _central_text_files(workspace):
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for name, pattern in patterns:
                if pattern.search(line):
                    violations.append(AuditViolation("central-app-identity",
                        f"{path.relative_to(workspace)}:{line_number}", name))
    return violations


def _python_app_import_violations(workspace: Path,
    definitions: tuple[AppDefinition, ...]) -> list[AuditViolation]:
    violations: list[AuditViolation] = []
    for definition in definitions:
        for path in sorted(definition.directory.rglob("*.py")):
            if EXCLUDED_PARTS.intersection(path.relative_to(workspace).parts):
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            owned = f"apps.{definition.name}"
            for module, line_number in _imported_modules(tree):
                if module.startswith("apps.") and module != owned and not module.startswith(owned + "."):
                    violations.append(AuditViolation("cross-app-import",
                        f"{path.relative_to(workspace)}:{line_number}", module))
    return violations


def _imported_modules(tree: ast.AST) -> tuple[tuple[str, int], ...]:
    imports: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.append((node.module, node.lineno))
        elif isinstance(node, ast.Import):
            imports.extend((alias.name, node.lineno) for alias in node.names)
    return tuple(imports)


def _frontend_boundary_violations(workspace: Path,
    definitions: tuple[AppDefinition, ...]) -> list[AuditViolation]:
    violations: list[AuditViolation] = []
    for definition in definitions:
        for path in sorted(definition.source_directory.rglob("*")):
            if path.suffix not in {".js", ".ts", ".tsx"}:
                continue
            for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                for specifier in _SCRIPT_IMPORT.findall(line):
                    if not specifier.startswith("."):
                        continue
                    target = (path.parent / specifier).resolve()
                    if not target.is_relative_to(definition.directory.resolve()):
                        violations.append(AuditViolation("frontend-boundary-import",
                            f"{path.relative_to(workspace)}:{line_number}", specifier))
    return violations


def _custom_element_violations(workspace: Path,
    definitions: tuple[AppDefinition, ...]) -> list[AuditViolation]:
    barrel = workspace / "packages" / "lit-ui" / "src" / "index.ts"
    if not barrel.is_file():
        return []
    registered = sorted(set(_CUSTOM_ELEMENT.findall(barrel.read_text(encoding="utf-8"))))
    violations: list[AuditViolation] = []
    for tag in registered:
        consumers = sum(any(f"<{tag}" in path.read_text(encoding="utf-8")
            for path in definition.source_directory.rglob("*") if path.suffix in SOURCE_SUFFIXES)
            for definition in definitions)
        if consumers < 2:
            violations.append(AuditViolation("unproved-custom-element",
                str(barrel.relative_to(workspace)), f"{tag}: {consumers} consumers"))
    return violations


def audit_architecture(workspace: Path,
    definitions: tuple[AppDefinition, ...]) -> tuple[AuditViolation, ...]:
    """Return deterministic dependency and shared-boundary violations."""
    violations = _central_identity_violations(workspace, definitions)
    violations.extend(_python_app_import_violations(workspace, definitions))
    violations.extend(_frontend_boundary_violations(workspace, definitions))
    violations.extend(_custom_element_violations(workspace, definitions))
    return tuple(sorted(violations))


class _PythonComplexity(ast.NodeVisitor):
    def __init__(self) -> None:
        self.value = 1

    def generic_visit(self, node: ast.AST) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            return
        if isinstance(node, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.IfExp, ast.comprehension)):
            self.value += 1
        elif isinstance(node, ast.BoolOp):
            self.value += len(node.values) - 1
        elif isinstance(node, ast.Try):
            self.value += len(node.handlers)
        elif isinstance(node, ast.Match):
            self.value += max(0, len(node.cases) - 1)
        super().generic_visit(node)


def _python_complexity(path: Path, workspace: Path) -> list[AuditViolation]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations: list[AuditViolation] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        visitor = _PythonComplexity()
        for statement in node.body:
            visitor.visit(statement)
        if visitor.value > MAX_CYCLOMATIC_COMPLEXITY:
            violations.append(AuditViolation("complex-function",
                f"{path.relative_to(workspace)}:{node.lineno}",
                f"{node.name}: {visitor.value} (maximum {MAX_CYCLOMATIC_COMPLEXITY})"))
    return violations


def _script_complexity(workspace: Path, paths: tuple[Path, ...]) -> list[AuditViolation]:
    if not paths:
        return []
    command = ["node", str(workspace / "scripts" / "audit-structure.mjs"),
        *(str(path.relative_to(workspace)) for path in paths)]
    completed = subprocess.run(command, cwd=workspace, check=False, text=True, capture_output=True)
    if completed.returncode:
        raise RuntimeError(completed.stderr.strip() or "structural JavaScript audit failed")
    return [AuditViolation("complex-function", item["path"], item["detail"])
        for item in json.loads(completed.stdout)]


def audit_workspace(workspace: Path,
    definitions: tuple[AppDefinition, ...]) -> AuditReport:
    """Collect architecture violations and non-gating structural debt."""
    sources = _source_files(workspace)
    large = [AuditViolation("large-file", str(path.relative_to(workspace)),
        f"{len(path.read_text(encoding='utf-8').splitlines())} lines (maximum {MAX_SOURCE_LINES})")
        for path in sources if len(path.read_text(encoding="utf-8").splitlines()) > MAX_SOURCE_LINES]
    complex_functions = [violation for path in sources if path.suffix == ".py"
        for violation in _python_complexity(path, workspace)]
    scripts = tuple(path for path in sources if path.suffix in {".js", ".ts", ".tsx", ".html"})
    complex_functions.extend(_script_complexity(workspace, scripts))
    return AuditReport(audit_architecture(workspace, definitions),
        tuple(sorted(large)), tuple(sorted(complex_functions)))
