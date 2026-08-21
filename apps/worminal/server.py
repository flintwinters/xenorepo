"""Durable localhost terminal workspace served by one FastAPI application."""

import asyncio
import hmac
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from pydantic import BaseModel, Field

from apps.worminal.database import Base, WorkspaceRepository, _migrate_legacy_schema
from apps.worminal.terminal import PtySession, bridge_terminal, is_loopback_client, resolve_shell_account
from monotools.appkit import create_app_context
from monotools.http import enforce_same_origin, set_session_cookie
from monotools.realtime import websocket_origin_allowed
from monotools.runtime import create_application


DIRECTORY = Path(__file__).parent
DEFAULT_DATABASE = DIRECTORY / "data" / "worminal.db"
COOKIE = "worminal_workspace"
ACCESS_COOKIE = "worminal_access"
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


class ShortcutInput(BaseModel):
    action: str = Field(pattern="^new-shell$")
    key: str = Field(min_length=1, max_length=40)
    control: bool
    alt: bool
    shift: bool
    meta: bool


class WorkspaceInput(BaseModel):
    windows: list[WindowInput] = Field(max_length=50)
    shortcuts: list[ShortcutInput] = Field(min_length=1, max_length=1)


class AccessInput(BaseModel):
    password: str = Field(min_length=1, max_length=1024)


class TerminalManager:
    """Keep each live shell attached to its durable window, not a socket."""

    def __init__(self, shell_user: str | None = None) -> None:
        self.sessions: dict[str, PtySession] = {}
        self.active: set[str] = set()
        self.shell_user = shell_user

    def session(self, window_id: str) -> PtySession:
        session = self.sessions.get(window_id)
        if session is None or session.process.poll() is not None:
            session = PtySession(user=self.shell_user)
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


def access_cookie_value(access_token: str) -> str:
    """Derive a non-reversible browser session value from the configured password."""
    return hmac.digest(access_token.encode(), b"worminal remote access", "sha256").hex()


def remote_access_authorized(password: str | None, access_token: str | None) -> bool:
    """Validate one supplied password without retaining it in browser storage."""
    if not access_token or not password:
        return False
    return hmac.compare_digest(password, access_token)


def create_app(database_url: str | None = None) -> FastAPI:
    context = create_app_context("worminal", metadata=Base.metadata,
        default_database=DEFAULT_DATABASE, environment_key="WORMINAL_DATABASE_URL",
        database_url=database_url, prepare=_migrate_legacy_schema)
    repository = WorkspaceRepository(context.require_sessions(), context.clock.now)
    shell_user = os.environ.get("WORMINAL_SHELL_USER")
    resolve_shell_account(shell_user)
    manager = TerminalManager(shell_user)
    remote_access_token = os.environ.get("WORMINAL_ACCESS_TOKEN")

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

    def remote_session_authorized(cookie: str | None) -> bool:
        return bool(remote_access_token and cookie) and hmac.compare_digest(
            cookie, access_cookie_value(remote_access_token)
        )

    @application.middleware("http")
    async def guard_remote_access(request: Request, call_next):
        if is_loopback_client(request) or request.url.path in {"/worminal", "/api/access"}:
            return await call_next(request)
        if remote_session_authorized(request.cookies.get(ACCESS_COOKIE)):
            return await call_next(request)
        if remote_access_token:
            return PlainTextResponse("Worminal requires its access password.", status_code=401)
        return PlainTextResponse("Set WORMINAL_ACCESS_TOKEN before allowing remote access.",
            status_code=403)

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

    @application.post("/api/access", status_code=204)
    def grant_remote_access(payload: AccessInput, request: Request) -> Response:
        reject_cross_origin(request)
        if not is_loopback_client(request) and not remote_access_authorized(payload.password, remote_access_token):
            raise HTTPException(status_code=401, detail="Access password is not valid.")
        response = Response(status_code=204)
        if remote_access_token:
            set_session_cookie(response, request, ACCESS_COOKIE, access_cookie_value(remote_access_token), COOKIE_AGE)
        return response

    @application.get("/api/workspace")
    def get_workspace(request: Request) -> JSONResponse:
        identifier = workspace_id(request)
        created = identifier is None
        identifier = identifier or repository.create_workspace()
        response = JSONResponse({"windows": repository.windows(identifier),
            "shortcuts": repository.shortcuts(identifier)})
        return set_session_cookie(response, request, COOKIE, identifier, COOKIE_AGE) if created else response

    @application.put("/api/workspace", status_code=204)
    def save_workspace(payload: WorkspaceInput, request: Request) -> Response:
        reject_cross_origin(request)
        identifier = require_workspace(request)
        repository.replace_windows(identifier, [window.model_dump() for window in payload.windows])
        repository.replace_shortcuts(identifier, [shortcut.model_dump() for shortcut in payload.shortcuts])
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
        if not websocket_origin_allowed(socket):
            await socket.close(code=1008, reason="Worminal accepts same-origin clients only.")
            return
        if not is_loopback_client(socket) and not remote_session_authorized(socket.cookies.get(ACCESS_COOKIE)):
            await socket.close(code=1008, reason="Worminal requires authenticated remote access.")
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
