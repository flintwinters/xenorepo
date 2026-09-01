"""FastAPI runtime for the Xenorepo Cockpit."""

import asyncio
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status

from apps.xenoview.backend.database import Base, SnapshotRepository
from apps.xenoview.backend.scanner import (
    scan_history, scan_modules, scan_overview, scan_tree,
)
from apps.xenoview.backend.schemas import (
    ModuleFact, MonoappStatus, Overview, RepositoryHistory, SnapshotResult, SnapshotView, TreeNode,
)
from monotools.orchestration.apps import discover_apps
from monotools.orchestration.services import ServiceError, ServiceSupervisor
from monotools.runtime.appkit import create_app_context
from monotools.runtime.http import enforce_same_origin
from monotools.runtime.application import create_application


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATABASE = Path(__file__).parent.parent / "data" / "xenoview.db"


def _delta(metrics: dict[str, int], latest: dict[str, object] | None) -> dict[str, int]:
    previous = latest["metrics"] if latest else {}
    return {key: value - int(previous.get(key, value)) for key, value in metrics.items()}


def create_app(database_url: str | None = None, repository: SnapshotRepository | None = None,
    root: Path = ROOT, supervisor: ServiceSupervisor | None = None) -> FastAPI:
    context = create_app_context("xenoview", metadata=Base.metadata,
        default_database=DEFAULT_DATABASE, environment_key="XENOVIEW_DATABASE_URL",
        database_url=database_url)
    snapshots = repository or SnapshotRepository(context.require_sessions(), clock=context.clock.now)
    application = create_application("xenoview")
    application.state.snapshots = snapshots
    services = supervisor or ServiceSupervisor(discover_apps(), root)
    application.state.services = services

    @application.get("/api/overview", response_model=Overview)
    async def overview() -> dict[str, object]:
        result = scan_overview(root)
        result["delta"] = _delta(result["metrics"], snapshots.latest())
        return result

    @application.get("/api/modules", response_model=list[ModuleFact])
    async def modules() -> list[dict[str, object]]:
        return scan_modules(root)

    @application.get("/api/tree", response_model=TreeNode)
    async def tree() -> dict[str, object]:
        return scan_tree(root)

    @application.get("/api/history", response_model=list[SnapshotView])
    async def history() -> list[dict[str, object]]:
        return snapshots.list()

    @application.get("/api/repository-history", response_model=RepositoryHistory)
    async def repository_history() -> dict[str, object]:
        return scan_history(root)

    @application.get("/api/monoapps", response_model=list[MonoappStatus])
    async def monoapps() -> list[dict[str, object]]:
        return [asdict(item) for item in services.statuses()]

    async def transition(request: Request, name: str, action: str) -> dict[str, object]:
        enforce_same_origin(request, lambda message: HTTPException(status_code=403, detail=message))
        try:
            operation = services.start if action == "start" else services.stop
            return asdict(await asyncio.to_thread(operation, name))
        except ServiceError as error:
            code = 404 if str(error).startswith("unknown monoapp:") else 409
            raise HTTPException(status_code=code, detail=str(error)) from error

    @application.post("/api/monoapps/{name}/start", response_model=MonoappStatus)
    async def start_monoapp(request: Request, name: str) -> dict[str, object]:
        return await transition(request, name, "start")

    @application.post("/api/monoapps/{name}/stop", response_model=MonoappStatus)
    async def stop_monoapp(request: Request, name: str) -> dict[str, object]:
        return await transition(request, name, "stop")

    @application.post("/api/snapshots", response_model=SnapshotResult,
        status_code=status.HTTP_201_CREATED)
    async def snapshot(request: Request) -> dict[str, object]:
        enforce_same_origin(request, lambda message: HTTPException(status_code=403, detail=message))
        current = scan_overview(root)
        value, created = snapshots.record(current["fingerprint"], current["revision"],
            current["dirty"], current["metrics"])
        return {"snapshot": value, "created": created}

    return application


app = create_app()
