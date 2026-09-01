"""Supervise local monoapp services through the canonical lifecycle contract."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys
import threading
import urllib.error
import urllib.request

from monotools.orchestration.apps import AppDefinition
from monotools.orchestration.lifecycle import build_app, validate_app, validate_dist


class ServiceError(RuntimeError):
    """Raised when a requested local service transition is invalid."""


@dataclass(frozen=True)
class ServiceStatus:
    """One observable local service state."""

    name: str
    title: str
    port: int
    url: str
    running: bool
    healthy: bool
    managed: bool


class ServiceSupervisor:
    """Start, inspect, and stop monoapps owned by one supervisor process."""

    def __init__(self, definitions: tuple[AppDefinition, ...], workspace: Path,
        *, first_port: int = 8100,
        launcher: Callable[..., subprocess.Popen[bytes]] = subprocess.Popen) -> None:
        self._definitions = {item.name: item for item in definitions}
        self._workspace = workspace
        self._ports = {item.name: first_port + index
            for index, item in enumerate(sorted(definitions, key=lambda value: value.name))}
        self._launcher = launcher
        self._processes: dict[str, subprocess.Popen[bytes]] = {}
        self._lock = threading.Lock()

    def statuses(self) -> list[ServiceStatus]:
        """Return every managed definition in deterministic order."""
        with self._lock:
            return [self._status(self._definitions[name]) for name in sorted(self._definitions)]

    def start(self, name: str) -> ServiceStatus:
        """Build and launch one stopped monoapp."""
        definition = self._definition(name)
        with self._lock:
            current = self._status(definition)
            if current.running:
                raise ServiceError(f"{name} is already running")
            validate_app(definition, self._workspace)
            build_app(definition, self._workspace)
            validate_dist(definition)
            port = self._ports[name]
            process = self._launcher(
                [sys.executable, "-m", "uvicorn", definition.module + ":app",
                    "--host", "127.0.0.1", "--port", str(port)],
                cwd=self._workspace,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._processes[name] = process
            return self._status(definition)

    def stop(self, name: str) -> ServiceStatus:
        """Stop one process launched by this supervisor."""
        definition = self._definition(name)
        with self._lock:
            process = self._live_process(name)
            if process is None:
                raise ServiceError(f"{name} is not running under Xenoview")
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            self._processes.pop(name, None)
            return self._status(definition)

    def _definition(self, name: str) -> AppDefinition:
        try:
            return self._definitions[name]
        except KeyError as error:
            raise ServiceError(f"unknown monoapp: {name}") from error

    def _live_process(self, name: str) -> subprocess.Popen[bytes] | None:
        process = self._processes.get(name)
        if process is not None and process.poll() is not None:
            self._processes.pop(name, None)
            return None
        return process

    def _status(self, definition: AppDefinition) -> ServiceStatus:
        port = self._ports[definition.name]
        process = self._live_process(definition.name)
        healthy = _healthy(port)
        return ServiceStatus(definition.name, definition.title, port,
            f"http://127.0.0.1:{port}", process is not None or healthy,
            healthy, process is not None)


def _healthy(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=.15) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError):
        return False
