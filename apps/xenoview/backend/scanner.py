"""Deterministic, read-only repository projections for the cockpit."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import ast
import statistics
import subprocess

from monotools.apps import AppDefinition, discover_apps
from monotools.audit import EXCLUDED_PARTS, SOURCE_SUFFIXES, audit_workspace


TRACKED_SUFFIXES = SOURCE_SUFFIXES | frozenset({".md", ".json", ".toml", ".yaml", ".yml", ".css"})
ROOT_FILES = frozenset({"AGENTS.md", "LIBRARIES.md", "README.md", "STABILIZATION.md",
    "UI.md", "manage.py", "package.json", "pyproject.toml"})
TREE_DEPTH = 4


@dataclass(frozen=True)
class FileFact:
    path: Path
    bytes: int
    lines: int


def _included(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    if EXCLUDED_PARTS.intersection(relative.parts) or any(part.startswith(".") for part in relative.parts):
        return False
    return path.suffix in TRACKED_SUFFIXES or (len(relative.parts) == 1 and path.name in ROOT_FILES)


def _facts(root: Path) -> tuple[FileFact, ...]:
    facts: list[FileFact] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or not _included(path, root):
            continue
        content = path.read_bytes()
        lines = len(content.decode("utf-8", errors="replace").splitlines())
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


def _test_cases(facts: tuple[FileFact, ...], root: Path) -> int:
    python = (fact for fact in facts if fact.path.suffix == ".py" and
        (fact.path.name.startswith("test_") or "tests" in fact.path.parts))
    scripts = (fact for fact in facts if fact.path.suffix == ".ts" and "tests" in fact.path.parts)
    return sum(_python_test_cases(root / fact.path) for fact in python) + sum(
        (root / fact.path).read_text(encoding="utf-8").count("test(") for fact in scripts)


def _metrics(root: Path, facts: tuple[FileFact, ...], source: tuple[FileFact, ...],
    definitions: tuple[AppDefinition, ...]) -> dict[str, int]:
    audit = audit_workspace(root, definitions)
    lines = [item.lines for item in source]
    return {
        "source_files": len(source), "source_lines": sum(lines),
        "repository_bytes": sum(item.bytes for item in facts), "monoapps": len(definitions),
        "monotools_modules": len(tuple((root / "monotools").glob("*.py"))),
        "test_files": sum("tests" in item.path.parts for item in source),
        "test_cases": _test_cases(facts, root),
        "specified_apps": sum(item.specification.is_file() for item in definitions),
        "architecture_violations": len(audit.architecture), "large_files": len(audit.large_files),
        "complex_functions": len(audit.complex_functions),
        "shared_import_edges": sum(len(item.imports) for item in definitions),
        "largest_file_lines": max(lines, default=0),
        "median_file_lines": round(statistics.median(lines)) if lines else 0,
    }


def scan_overview(root: Path) -> dict[str, object]:
    facts, definitions = _facts(root), _definitions(root)
    source = tuple(fact for fact in facts if fact.path.suffix in SOURCE_SUFFIXES)
    revision, dirty = _git(root)
    metrics = _metrics(root, facts, source, definitions)
    identity = f"{revision}:{int(dirty)}:" + ":".join(f"{key}={value}" for key, value in metrics.items())
    return {"metrics": metrics, "revision": revision, "dirty": dirty,
        "fingerprint": sha256(identity.encode()).hexdigest(),
        "specification": {"covered": metrics["specified_apps"], "total": metrics["monoapps"]},
        "exclusions": sorted(EXCLUDED_PARTS),
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
        public = sum(isinstance(node, (ast.ClassDef, ast.FunctionDef))
            and not node.name.startswith("_") for node in tree.body)
        modules.append({"name": path.stem, "path": str(path.relative_to(root)),
            "lines": len(content.splitlines()), "bytes": path.stat().st_size,
            "public_definitions": public, "inbound_apps": inbound[path.stem],
            "dependencies": _module_dependencies(path)})
    return modules


def _tree_child_names(matching: tuple[FileFact, ...], path: Path, depth: int) -> list[str]:
    if depth >= TREE_DEPTH:
        return []
    return sorted({item.path.parts[len(path.parts)] for item in matching
        if len(item.path.parts) > len(path.parts)})


def _tree_directory(facts: tuple[FileFact, ...], path: Path, depth: int) -> dict[str, object]:
    matching = tuple(filter(lambda item: item.path.is_relative_to(path), facts))
    child_names = _tree_child_names(matching, path, depth)
    children = [_tree_directory(facts, path / name, depth + 1) for name in child_names]
    children.extend({"name": item.path.name, "path": str(item.path), "kind": "file",
        "bytes": item.bytes, "lines": item.lines} for item in matching
        if item.path.parent == path)
    return {"name": path.name or "xenorepo", "path": str(path) or ".", "kind": "directory",
        "bytes": sum(item.bytes for item in matching), "lines": sum(item.lines for item in matching),
        "children": children}


def scan_tree(root: Path) -> dict[str, object]:
    return _tree_directory(_facts(root), Path(), 0)


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
