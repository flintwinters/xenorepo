"""FastAPI runtime for the read-only Xenorepo Cockpit."""

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status

from apps.xenoview.backend.database import Base, SnapshotRepository
from apps.xenoview.backend.scanner import (
    scan_history, scan_modules, scan_overview, scan_tree,
)
from apps.xenoview.backend.schemas import (
    ModuleFact, Overview, RepositoryHistory, SnapshotResult, SnapshotView, TreeNode,
)
from monotools.runtime.appkit import create_app_context
from monotools.runtime.http import enforce_same_origin
from monotools.runtime.application import create_application


ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATABASE = Path(__file__).parent.parent / "data" / "xenoview.db"


def _delta(metrics: dict[str, int], latest: dict[str, object] | None) -> dict[str, int]:
    previous = latest["metrics"] if latest else {}
    return {key: value - int(previous.get(key, value)) for key, value in metrics.items()}


def create_app(database_url: str | None = None, repository: SnapshotRepository | None = None,
    root: Path = ROOT) -> FastAPI:
    context = create_app_context("xenoview", metadata=Base.metadata,
        default_database=DEFAULT_DATABASE, environment_key="XENOVIEW_DATABASE_URL",
        database_url=database_url)
    snapshots = repository or SnapshotRepository(context.require_sessions(), clock=context.clock.now)
    application = create_application("xenoview")
    application.state.snapshots = snapshots

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
