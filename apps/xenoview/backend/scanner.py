"""Deterministic, read-only repository projections for the cockpit."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import ast
import os
import re
import statistics
import subprocess

from monotools.apps import AppDefinition, discover_apps
from monotools.audit import EXCLUDED_PARTS, audit_workspace


LANGUAGES = {".css": "CSS", ".html": "HTML", ".js": "JavaScript", ".json": "JSON",
    ".md": "Markdown", ".py": "Python", ".sql": "SQL", ".toml": "TOML",
    ".ts": "TypeScript", ".tsx": "TypeScript", ".yaml": "YAML", ".yml": "YAML"}
COMPILED_PARTS = frozenset({"build", "coverage", "dist", "htmlcov", "site"})
DEPENDENCY_PARTS = frozenset({".mypy_cache", ".pytest_cache", ".ruff_cache", ".uv-cache",
    ".venv", "node_modules", "vendor"})
TREE_EXCLUDED_PARTS = EXCLUDED_PARTS | COMPILED_PARTS | DEPENDENCY_PARTS
_SCRIPT_TEST = re.compile(r"\b(?:test|it)\s*\(")


@dataclass(frozen=True)
class FileFact:
    path: Path
    bytes: int
    lines: int


def _included(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    return not TREE_EXCLUDED_PARTS.intersection(relative.parts) and ".git" not in relative.parts


def _facts(root: Path) -> tuple[FileFact, ...]:
    facts: list[FileFact] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or not _included(path, root):
            continue
        content = path.read_bytes()
        lines = len(content.decode("utf-8", errors="replace").splitlines()) if path.suffix in LANGUAGES else 0
        facts.append(FileFact(path.relative_to(root), len(content), lines))
    return tuple(facts)


def _git(root: Path) -> tuple[str, bool]:
    revision = subprocess.run(["git", "rev-parse", "--short=12", "HEAD"], cwd=root,
        check=False, text=True, capture_output=True).stdout.strip() or "unavailable"
    dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=root,
        check=False, text=True, capture_output=True).stdout.strip())
    return revision, dirty


def _definitions(root: Path) -> tuple[AppDefinition, ...]:
    return discover_apps() if root == Path(__file__).resolve().parents[3] else tuple()


def _python_test_cases(path: Path) -> int:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return sum(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_") for node in ast.walk(tree))


def _test_case_count(path: Path, root: Path) -> int:
    if path.suffix == ".py":
        return _python_test_cases(root / path)
    if path.suffix in {".js", ".ts", ".tsx"}:
        return len(_SCRIPT_TEST.findall((root / path).read_text(encoding="utf-8")))
    return 0


def _test_breakdown(facts: tuple[FileFact, ...], root: Path,
    definitions: tuple[AppDefinition, ...]) -> dict[str, object]:
    test_files = tuple(item.path for item in facts if "tests" in item.path.parts and
        item.path.suffix in {".js", ".py", ".ts", ".tsx"})
    counts = {str(path): _test_case_count(path, root) for path in test_files}
    apps = {definition.name: sum(value for path, value in counts.items()
        if Path(path).is_relative_to(Path("apps") / definition.name / "tests"))
        for definition in definitions}
    monorepo = sum(value for path, value in counts.items() if not Path(path).is_relative_to(Path("apps")))
    return {"total": monorepo + sum(apps.values()), "monorepo": monorepo, "monoapps": apps}


def _language_lines(source: tuple[FileFact, ...]) -> list[dict[str, object]]:
    counts = Counter()
    files = Counter()
    for item in source:
        language = LANGUAGES[item.path.suffix]
        counts[language] += item.lines
        files[language] += 1
    return [{"language": language, "lines": lines, "files": files[language]}
        for language, lines in sorted(counts.items(), key=lambda item: (-item[1], item[0]))]


def _metrics(root: Path, facts: tuple[FileFact, ...], source: tuple[FileFact, ...],
    definitions: tuple[AppDefinition, ...], tests: dict[str, object]) -> dict[str, int]:
    audit = audit_workspace(root, definitions)
    lines = [item.lines for item in source]
    return {
        "source_files": len(source), "source_lines": sum(lines),
        "repository_bytes": sum(item.bytes for item in facts), "monoapps": len(definitions),
        "monotools_modules": len(tuple((root / "monotools").glob("*.py"))),
        "test_files": sum("tests" in item.path.parts for item in source),
        "test_cases": int(tests["total"]),
        "specified_apps": sum(item.specification.is_file() for item in definitions),
        "architecture_violations": len(audit.architecture), "large_files": len(audit.large_files),
        "complex_functions": len(audit.complex_functions),
        "shared_import_edges": sum(len(item.imports) for item in definitions),
        "largest_file_lines": max(lines, default=0),
        "median_file_lines": round(statistics.median(lines)) if lines else 0,
    }


def scan_overview(root: Path) -> dict[str, object]:
    facts, definitions = _facts(root), _definitions(root)
    source = tuple(fact for fact in facts if fact.path.suffix in LANGUAGES)
    tests = _test_breakdown(facts, root, definitions)
    revision, dirty = _git(root)
    metrics = _metrics(root, facts, source, definitions, tests)
    identity = f"{revision}:{int(dirty)}:" + ":".join(f"{key}={value}" for key, value in metrics.items())
    return {"metrics": metrics, "revision": revision, "dirty": dirty,
        "fingerprint": sha256(identity.encode()).hexdigest(),
        "specification": {"covered": metrics["specified_apps"], "total": metrics["monoapps"]},
        "exclusions": sorted(TREE_EXCLUDED_PARTS), "language_lines": _language_lines(source),
        "test_breakdown": tests,
        "largest_files": [{"path": str(item.path), "lines": item.lines, "bytes": item.bytes}
            for item in sorted(source, key=lambda item: (-item.lines, str(item.path)))[:8]]}


def _module_dependencies(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    values = {node.module.split(".", 1)[1].split(".", 1)[0]
        for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module
        and node.module.startswith("monotools.")}
    values.update(alias.name.split(".", 1)[1].split(".", 1)[0]
        for node in ast.walk(tree) if isinstance(node, ast.Import)
        for alias in node.names if alias.name.startswith("monotools."))
    return sorted(values - {path.stem})


def scan_modules(root: Path) -> list[dict[str, object]]:
    definitions = _definitions(root)
    inbound = Counter(item.removeprefix("monotools.").split(".", 1)[0]
        for definition in definitions for item in definition.imports if item.startswith("monotools."))
    modules = []
    for path in sorted((root / "monotools").glob("*.py")):
        content = path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(path))
        documentation = (ast.get_docstring(tree, clean=True) or "").split("\n\n", 1)
        public = sum(isinstance(node, (ast.ClassDef, ast.FunctionDef))
            and not node.name.startswith("_") for node in tree.body)
        modules.append({"name": path.stem, "path": str(path.relative_to(root)),
            "lines": len(content.splitlines()), "bytes": path.stat().st_size,
            "public_definitions": public, "inbound_apps": inbound[path.stem],
            "description": documentation[0], "explanation": documentation[1],
            "dependencies": _module_dependencies(path)})
    return modules


def _tree_child_names(matching: tuple[FileFact, ...], path: Path) -> list[str]:
    return sorted({item.path.parts[len(path.parts)] for item in matching
        if len(item.path.parts) > len(path.parts) + 1})


def _tree_directory(facts: tuple[FileFact, ...], path: Path, depth: int) -> dict[str, object]:
    matching = tuple(filter(lambda item: item.path.is_relative_to(path), facts))
    child_names = _tree_child_names(matching, path)
    children = [_tree_directory(facts, path / name, depth + 1) for name in child_names]
    children.extend({"name": item.path.name, "path": str(item.path), "kind": "file",
        "bytes": item.bytes, "lines": item.lines} for item in matching
        if item.path.parent == path)
    return {"name": path.name or "xenorepo", "path": str(path) or ".", "kind": "directory",
        "bytes": sum(item.bytes for item in matching), "lines": sum(item.lines for item in matching),
        "children": children}


def scan_tree(root: Path) -> dict[str, object]:
    tree = _tree_directory(_facts(root), Path(), 0)
    tree["ls_colors"] = os.environ.get("LS_COLORS", "")
    return tree


def scan_architecture(root: Path) -> dict[str, object]:
    definitions = _definitions(root)
    nodes = [{"id": "repository", "label": "Xenorepo", "kind": "repository"},
        {"id": "monotools", "label": "Monotools", "kind": "platform"},
        {"id": "lit-ui", "label": "Central Lit UI", "kind": "platform"},
        {"id": "runtime", "label": "FastAPI + dist", "kind": "runtime"},
        {"id": "storage", "label": "SQLite / PostgreSQL", "kind": "storage"}]
    nodes.extend({"id": f"app:{item.name}", "label": item.title, "kind": "app"}
        for item in definitions)
    edges = [{"source": "repository", "target": "monotools", "label": "orchestrates"},
        {"source": "monotools", "target": "runtime", "label": "builds + serves"}]
    for item in definitions:
        app_id = f"app:{item.name}"
        edges.append({"source": app_id, "target": "monotools", "label":
            f"{sum(value.startswith('monotools.') for value in item.imports)} declared modules"})
        if "@xenorepo/lit-ui" in item.imports:
            edges.append({"source": app_id, "target": "lit-ui", "label": "composes"})
        edges.append({"source": "runtime", "target": app_id, "label": "hosts"})
        if "database" in item.capabilities:
            edges.append({"source": app_id, "target": "storage", "label": "persists"})
    return {"nodes": nodes, "edges": edges}
