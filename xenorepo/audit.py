"""Measure architecture and structural invariants without mutation.

The audit inventories dependency-boundary violations, oversized sources, and
complex functions so root checks can reject drift through stable categories.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import ast
import json
import re
import subprocess

from monotools.orchestration.apps import AppDefinition


SOURCE_ROOTS = ("apps", "monotools", "packages", "tests", "xenorepo")
SOURCE_SUFFIXES = frozenset({".py", ".js", ".ts", ".tsx", ".css", ".html"})
TEXT_SUFFIXES = SOURCE_SUFFIXES | frozenset({".md", ".json", ".toml", ".yaml", ".yml"})
EXCLUDED_PARTS = frozenset({
    ".git", ".state", ".venv", "data", "dist", "historic", "node_modules", "__pycache__",
})
MAX_SOURCE_LINES = 600
MAX_CYCLOMATIC_COMPLEXITY = 8
_SCRIPT_IMPORT = re.compile(r"(?:from\s+|import\s*)[\"']([^\"']+)[\"']")
_TABLE_CELL = re.compile(r"<td\b[^>]*>(.*?)</td>", re.DOTALL | re.IGNORECASE)
_STACKED_CELL_CONTENT = re.compile(r"<(?:article|br|div|footer|header|p|section|small)\b", re.IGNORECASE)


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
    roots = [workspace, workspace / "monotools", workspace / "packages", workspace / "tests",
        workspace / "xenorepo"]
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


def _monotools_dependency_violations(workspace: Path) -> list[AuditViolation]:
    """Reject dependencies from reusable Monotools into Xenorepo policy."""
    directory = workspace / "monotools"
    if not directory.is_dir():
        return []
    violations = []
    for path in sorted(directory.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for module, line_number in _imported_modules(tree):
            if module == "xenorepo" or module.startswith("xenorepo."):
                violations.append(AuditViolation("monotools-xenorepo-import",
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


def _app_source_html_violations(workspace: Path) -> list[AuditViolation]:
    """Reject authored HTML while permitting generated deployment artifacts."""
    apps_directory = workspace / "apps"
    if not apps_directory.is_dir():
        return []
    return [AuditViolation("app-source-html", str(path.relative_to(workspace)),
        "HTML is a compiled artifact; application source must be JavaScript or TypeScript")
        for path in sorted(apps_directory.rglob("*.html"))
        if not EXCLUDED_PARTS.intersection(path.relative_to(workspace).parts)]


def _legacy_frontend_source_violations(workspace: Path) -> list[AuditViolation]:
    """Reject JavaScript source in production frontend trees after the TSX migration."""
    apps_directory = workspace / "apps"
    if not apps_directory.is_dir():
        return []
    return [AuditViolation("legacy-frontend-javascript", str(path.relative_to(workspace)),
        "production frontend source must be typed TypeScript or TSX")
        for path in sorted(apps_directory.glob("*/frontend/**/*.js"))
        if not EXCLUDED_PARTS.intersection(path.relative_to(workspace).parts)]


def _monotools_documentation_violations(workspace: Path) -> list[AuditViolation]:
    """Require a summary and explanatory paragraph in every platform module."""
    directory = workspace / "monotools"
    if not directory.is_dir():
        return []
    violations = []
    for path in sorted(directory.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        sections = (ast.get_docstring(tree, clean=True) or "").split("\n\n", 1)
        if len(sections) < 2 or not all(section.strip() for section in sections):
            violations.append(AuditViolation("monotools-module-documentation",
                str(path.relative_to(workspace)),
                "module docstring must contain a summary and explanatory paragraph"))
    return violations


def _stacked_table_cell_violations(workspace: Path,
    definitions: tuple[AppDefinition, ...]) -> list[AuditViolation]:
    """Reject markup that deliberately stacks multiple text regions in one cell."""
    violations = []
    for definition in definitions:
        for path in sorted(definition.source_directory.rglob("*")):
            if path.suffix not in {".js", ".ts", ".tsx"}:
                continue
            content = path.read_text(encoding="utf-8")
            for match in _TABLE_CELL.finditer(content):
                if _STACKED_CELL_CONTENT.search(match.group(1)):
                    line = content.count("\n", 0, match.start()) + 1
                    violations.append(AuditViolation("stacked-table-cell",
                        f"{path.relative_to(workspace)}:{line}",
                        "table cells must contain one logical value without stacked markup"))
    return violations


def audit_architecture(workspace: Path,
    definitions: tuple[AppDefinition, ...]) -> tuple[AuditViolation, ...]:
    """Return deterministic dependency and shared-boundary violations."""
    violations = _central_identity_violations(workspace, definitions)
    violations.extend(_python_app_import_violations(workspace, definitions))
    violations.extend(_monotools_dependency_violations(workspace))
    violations.extend(_frontend_boundary_violations(workspace, definitions))
    violations.extend(_app_source_html_violations(workspace))
    violations.extend(_legacy_frontend_source_violations(workspace))
    violations.extend(_monotools_documentation_violations(workspace))
    violations.extend(_stacked_table_cell_violations(workspace, definitions))
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
    command = ["node", str(workspace / "monotools" / "node" / "audit-structure.mjs"),
        *(str(path.relative_to(workspace)) for path in paths)]
    completed = subprocess.run(command, cwd=workspace, check=False, text=True, capture_output=True)
    if completed.returncode:
        raise RuntimeError(completed.stderr.strip() or "structural JavaScript audit failed")
    return [AuditViolation("complex-function", item["path"], item["detail"])
        for item in json.loads(completed.stdout)]


def audit_workspace(workspace: Path,
    definitions: tuple[AppDefinition, ...]) -> AuditReport:
    """Collect architecture, file-size, and function-complexity violations."""
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
