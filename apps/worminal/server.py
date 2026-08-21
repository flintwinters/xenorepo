"""Durable localhost terminal workspace served by one FastAPI application."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from apps.worminal.database import Base, WorkspaceRepository, _migrate_legacy_schema
from apps.worminal.terminal import PtySession, bridge_terminal, is_loopback_client
from monotools.appkit import create_app_context
from monotools.http import enforce_same_origin, set_session_cookie
from monotools.realtime import websocket_origin_allowed
from monotools.runtime import create_application


DIRECTORY = Path(__file__).parent
DEFAULT_DATABASE = DIRECTORY / "data" / "worminal.db"
COOKIE = "worminal_workspace"
COOKIE_AGE = 365 * 24 * 60 * 60


class WindowInput(BaseModel):
    id: str = Field(min_length=36, max_length=36)
    title: str = Field(min_length=1, max_length=80)
    x: int
    y: int
    width: int = Field(ge=300, le=5000)
    height: int = Field(ge=190, le=5000)
    z: int = Field(ge=1, le=100_000)
    minimized: bool
    maximized: bool


class WorkspaceInput(BaseModel):
    windows: list[WindowInput] = Field(max_length=50)


class TerminalManager:
    """Keep each live shell attached to its durable window, not a socket."""

    def __init__(self) -> None:
        self.sessions: dict[str, PtySession] = {}
        self.active: set[str] = set()

    def session(self, window_id: str) -> PtySession:
        session = self.sessions.get(window_id)
        if session is None or session.process.poll() is not None:
            session = PtySession()
            self.sessions[window_id] = session
        return session

    def attach(self, window_id: str) -> PtySession | None:
        if window_id in self.active:
            return None
        self.active.add(window_id)
        return self.session(window_id)

    def detach(self, window_id: str) -> None:
        self.active.discard(window_id)

    def close(self, window_id: str) -> None:
        self.active.discard(window_id)
        session = self.sessions.pop(window_id, None)
        if session is not None:
            session.close()

    def close_all(self) -> None:
        for window_id in list(self.sessions):
            self.close(window_id)


def create_app(database_url: str | None = None) -> FastAPI:
    context = create_app_context("worminal", metadata=Base.metadata,
        default_database=DEFAULT_DATABASE, environment_key="WORMINAL_DATABASE_URL",
        database_url=database_url, prepare=_migrate_legacy_schema)
    repository = WorkspaceRepository(context.require_sessions(), context.clock.now)
    manager = TerminalManager()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            manager.close_all()

    application = create_application("worminal")
    application.router.lifespan_context = lifespan
    application.state.repository = repository
    application.state.terminal_manager = manager

    def workspace_id(request: Request) -> str | None:
        candidate = request.cookies.get(COOKIE)
        return candidate if repository.workspace_exists(candidate) else None

    def require_workspace(request: Request) -> str:
        identifier = workspace_id(request)
        if identifier is None:
            raise HTTPException(status_code=401, detail="Workspace is required.")
        return identifier

    def reject_cross_origin(request: Request) -> None:
        enforce_same_origin(request, lambda message: HTTPException(status_code=403, detail=message))

    @application.get("/api/workspace")
    def get_workspace(request: Request) -> JSONResponse:
        identifier = workspace_id(request)
        created = identifier is None
        identifier = identifier or repository.create_workspace()
        response = JSONResponse({"windows": repository.windows(identifier)})
        return set_session_cookie(response, request, COOKIE, identifier, COOKIE_AGE) if created else response

    @application.put("/api/workspace", status_code=204)
    def save_workspace(payload: WorkspaceInput, request: Request) -> Response:
        reject_cross_origin(request)
        identifier = require_workspace(request)
        repository.replace_windows(identifier, [window.model_dump() for window in payload.windows])
        return Response(status_code=204)

    @application.delete("/api/workspace/windows/{window_id}", status_code=204)
    def close_window(window_id: str, request: Request) -> Response:
        reject_cross_origin(request)
        identifier = require_workspace(request)
        if not repository.delete_window(identifier, window_id):
            raise HTTPException(status_code=404, detail="Terminal window not found.")
        manager.close(window_id)
        return Response(status_code=204)

    @application.websocket("/ws/terminal/{window_id}")
    async def terminal(socket: WebSocket, window_id: str) -> None:
        if not is_loopback_client(socket) or not websocket_origin_allowed(socket):
            await socket.close(code=1008, reason="Worminal accepts same-origin loopback clients only.")
            return
        workspace = socket.cookies.get(COOKIE)
        transcript = repository.transcript(workspace or "", window_id)
        session = manager.attach(window_id) if transcript is not None else None
        if session is None:
            await socket.close(code=1008, reason="Terminal window is unavailable.")
            return
        await socket.accept()
        try:
            if transcript:
                await socket.send_bytes(transcript)

            async def record(output: bytes) -> None:
                await asyncio.to_thread(repository.append_output, workspace, window_id, output)

            await bridge_terminal(socket, session, record, close_session=False)
        finally:
            manager.detach(window_id)

    return application


app = create_app()
