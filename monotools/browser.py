"""Static browser-proof validation which is safe to run before lifecycle mutation."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess

from monotools.lifecycle import LifecycleError
from monotools.management import BrowserSuite


def validate_browser_suite(suite: BrowserSuite, workspace: Path) -> dict[str, object]:
    """Parse, enumerate, and enforce the declared minimum browser proof matrix."""
    validator = workspace / "packages" / "browser-testing" / "src" / "validate.js"
    static = subprocess.run(
        ["node", str(validator), str(suite.path)], cwd=workspace,
        check=False, text=True, capture_output=True,
    )
    if static.returncode:
        raise LifecycleError(static.stderr.strip() or "BROWSER_STATIC_VALIDATION_FAILED")
    try:
        report = json.loads(static.stdout)
    except json.JSONDecodeError as error:
        raise LifecycleError("BROWSER_VALIDATOR_OUTPUT: invalid JSON") from error
    _validate_proof_coverage(suite, report)
    _validate_playwright_inventory(suite, workspace)
    return report


def _validate_proof_coverage(suite: BrowserSuite, report: dict[str, object]) -> None:
    counts = report["counts"]
    assert isinstance(counts, dict)
    missing = sorted(proof for proof in suite.proof_kinds
        if not counts.get(proof))
    if missing:
        raise LifecycleError(f"BROWSER_PROOF_COVERAGE: missing {', '.join(missing)}")


def _validate_playwright_inventory(suite: BrowserSuite, workspace: Path) -> None:
    playwright = workspace / "node_modules" / ".bin" / "playwright"
    listed = subprocess.run(
        [str(playwright), "test", str(suite.path.relative_to(workspace)), "--list"],
        cwd=workspace, check=False, text=True, capture_output=True,
    )
    if listed.returncode:
        raise LifecycleError(f"BROWSER_LIST_FAILED: {listed.stderr.strip() or listed.stdout.strip()}")
    if "Total:" not in listed.stdout:
        raise LifecycleError("BROWSER_LIST_EMPTY: Playwright resolved no tests")
    absent_viewports = sorted(name for name in suite.viewports if name not in listed.stdout)
    if absent_viewports:
        raise LifecycleError(
            f"BROWSER_VIEWPORT_COVERAGE: missing {', '.join(absent_viewports)}"
        )


def run_browser_framework_suite(workspace: Path) -> int:
    """Run Monotools' own trusted-input canaries without an application service."""
    suite = BrowserSuite(
        workspace / "tests" / "browser-framework" / "evidence.spec.js",
        frozenset({"acceptance", "browser-integration"}),
    )
    validate_browser_suite(suite, workspace)
    completed = subprocess.run(
        [str(workspace / "node_modules" / ".bin" / "playwright"), "test",
            str(suite.path.relative_to(workspace))],
        cwd=workspace, check=False,
    )
    return completed.returncode
