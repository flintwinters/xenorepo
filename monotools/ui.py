"""Browser-check lifecycle operations for managed applications."""

from __future__ import annotations

import os
import json
from pathlib import Path
import socket
import subprocess
import signal
import sys
import time

from monotools.apps import AppDefinition
from monotools.lifecycle import LifecycleError, build_app, validate_app, validate_dist


HEALTH_TIMEOUT_SECONDS = 15
POLL_INTERVAL_SECONDS = 0.1


def ui_artifact_directory(definition: AppDefinition) -> Path:
    """Return the visible, app-owned home for browser diagnostics."""
    return definition.directory / "data" / "ui-check"


def available_local_port() -> int:
    """Reserve a local ephemeral port long enough to learn its number."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _health_url(port: int) -> str:
    return f"http://127.0.0.1:{port}/health"


def wait_for_health(port: int, process: subprocess.Popen[bytes]) -> None:
    """Prove that the managed service is alive before running a browser."""
    import urllib.error
    import urllib.request

    deadline = time.monotonic() + HEALTH_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise LifecycleError(f"FastAPI service exited early ({process.returncode})")
        try:
            with urllib.request.urlopen(_health_url(port), timeout=1) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError):
            time.sleep(POLL_INTERVAL_SECONDS)
    raise LifecycleError(f"FastAPI service did not become healthy within {HEALTH_TIMEOUT_SECONDS} seconds")


def _terminate(process: subprocess.Popen[bytes]) -> str:
    """Stop a child service and report whether escalation was required."""
    if process.poll() is not None:
        return "already-exited"
    os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)
        return "forced-kill"
    return "clean"


def _run_browser(command: list[str], workspace: Path,
    environment: dict[str, str], log: Path) -> int:
    """Stream Playwright output while retaining the exact same bytes."""
    with log.open("w", encoding="utf-8") as retained:
        process = subprocess.Popen(
            command, cwd=workspace, env=environment, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="")
            retained.write(line)
        return process.wait()


def run_ui_check(definition: AppDefinition, workspace: Path, suite: object = None,
    *, evidence: bool = False) -> Path:
    """Build, serve, and browser-check one application with preserved evidence."""
    from monotools.management import BrowserSuite
    browser_suite = (suite if isinstance(suite, BrowserSuite)
        else BrowserSuite(Path(suite)) if suite is not None else None)
    universal_suite = BrowserSuite(
        workspace / "tests" / "browser-framework" / "universal.spec.js",
        frozenset({"browser-integration"}),
    )
    from monotools.browser import validate_browser_suite
    universal_report = validate_browser_suite(universal_suite, workspace)
    proof_report = (validate_browser_suite(browser_suite, workspace)
        if browser_suite else {"counts": {}})
    validate_app(definition, workspace)
    build_app(definition, workspace)
    validate_dist(definition)
    playwright = workspace / "node_modules" / ".bin" / "playwright"
    if not playwright.is_file():
        raise LifecycleError("Playwright is not installed; run python manage.py bootstrap first")
    artifacts = ui_artifact_directory(definition)
    artifacts.mkdir(parents=True, exist_ok=True)
    service_log = artifacts / "service.log"
    playwright_log = artifacts / "playwright.log"
    summary_path = artifacts / "summary.json"
    port = available_local_port()
    environment = os.environ | {
        "BASE_URL": f"http://127.0.0.1:{port}",
        "PLAYWRIGHT_OUTPUT_DIR": str(artifacts / "test-results"),
        "XENOREPO_FRONTEND_ROUTES": json.dumps([
            {"path": route, "artifact": str(definition.artifact(name).output)}
            for route, name in definition.routes
        ]),
        "PLAYWRIGHT_RETAIN_EVIDENCE": "1" if evidence else "0",
    }
    if "database" in definition.capabilities:
        database = artifacts / "browser.db"
        database.unlink(missing_ok=True)
        environment[f"{definition.name.upper()}_DATABASE_URL"] = f"sqlite:///{database}"
    suites = [universal_suite.path]
    if browser_suite:
        suites.append(browser_suite.path)
    command = [str(playwright), "test", *(str(path.relative_to(workspace)) for path in suites)]
    process: subprocess.Popen[bytes] | None = None
    primary_failure: Exception | None = None
    cleanup_status = "not-started"
    browser_status: int | None = None
    started = time.time()
    database = artifacts / "browser.db" if "database" in definition.capabilities else None
    try:
        with service_log.open("wb") as output:
            process = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", definition.module + ":app",
                    "--host", "127.0.0.1", "--port", str(port)],
                cwd=workspace,
                env=environment,
                stdout=output,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            wait_for_health(port, process)
            browser_status = _run_browser(command, workspace, environment, playwright_log)
            if browser_status:
                raise LifecycleError(
                    f"browser checks failed ({browser_status}); inspect {artifacts.relative_to(workspace)}"
                )
    except (FileNotFoundError, LifecycleError) as error:
        primary_failure = error
        raise
    finally:
        if process is not None:
            cleanup_status = _terminate(process)
        summary_path.write_text(json.dumps({
            "schemaVersion": 1,
            "app": definition.name,
            "suites": [str(path.relative_to(workspace)) for path in suites],
            "proofCounts": {key: universal_report["counts"].get(key, 0)
                + proof_report["counts"].get(key, 0) for key in universal_report["counts"]},
            "viewports": sorted(universal_suite.viewports),
            "inputModalities": sorted(browser_suite.input_modalities) if browser_suite else [],
            "startedAt": started,
            "durationSeconds": time.time() - started,
            "browserStatus": browser_status,
            "database": str(database.relative_to(workspace)) if database else None,
            "serviceLog": str(service_log.relative_to(workspace)),
            "playwrightLog": str(playwright_log.relative_to(workspace)),
            "cleanup": cleanup_status,
            "failure": str(primary_failure) if primary_failure else None,
            "successfulEvidenceRetained": evidence,
        }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return artifacts
