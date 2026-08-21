"""Durable localhost terminal workspace served by one FastAPI application."""

import asyncio
import hmac
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from pydantic import BaseModel, Field

from apps.worminal.database import Base, WorkspaceRepository, _migrate_legacy_schema
from apps.worminal.terminal import PtySession, is_loopback_client, resolve_shell_account
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


class PasswordChangeInput(BaseModel):
    current_password: str = Field(min_length=1, max_length=1024)
    new_password: str = Field(min_length=1, max_length=1024)


@dataclass
class ManagedTerminal:
    session: PtySession
    sockets: set[WebSocket] = field(default_factory=set)
    reader: asyncio.Task[None] | None = None


class TerminalManager:
    """Own each PTY once and broadcast its output to every attached view."""

    def __init__(self, shell_user: str | None, repository: WorkspaceRepository) -> None:
        self.terminals: dict[str, ManagedTerminal] = {}
        self.shell_user = shell_user
        self.repository = repository

    def attach(self, window_id: str, socket: WebSocket) -> PtySession:
        terminal = self.terminals.get(window_id)
        if terminal is None or terminal.session.process.poll() is not None:
            terminal = ManagedTerminal(PtySession(user=self.shell_user))
            self.terminals[window_id] = terminal
        terminal.sockets.add(socket)
        if terminal.reader is None or terminal.reader.done():
            terminal.reader = asyncio.create_task(self._broadcast(window_id, terminal))
        return terminal.session

    async def _broadcast(self, window_id: str, terminal: ManagedTerminal) -> None:
        try:
            while True:
                output = await asyncio.to_thread(terminal.session.read)
                if not output:
                    return
                workspace = self.repository.shared_workspace()
                await asyncio.to_thread(self.repository.append_output, workspace, window_id, output)
                for socket in tuple(terminal.sockets):
                    try:
                        await socket.send_bytes(output)
                    except Exception:
                        terminal.sockets.discard(socket)
        except (OSError, asyncio.CancelledError):
            return

    def detach(self, window_id: str, socket: WebSocket) -> None:
        terminal = self.terminals.get(window_id)
        if terminal is not None:
            terminal.sockets.discard(socket)

    def close(self, window_id: str) -> None:
        terminal = self.terminals.pop(window_id, None)
        if terminal is not None:
            if terminal.reader is not None:
                terminal.reader.cancel()
            terminal.session.close()

    def close_all(self) -> None:
        for window_id in list(self.terminals):
            self.close(window_id)


def access_cookie_value(access_session_version: str) -> str:
    """Derive the browser cookie from an opaque, rotatable server generation."""
    return hmac.digest(access_session_version.encode(), b"worminal remote access", "sha256").hex()


def remote_access_authorized(password: str | None, repository: WorkspaceRepository) -> bool:
    """Validate one supplied password against the durable salted verifier."""
    return repository.verify_access_password(password)


def create_app(database_url: str | None = None) -> FastAPI:
    context = create_app_context("worminal", metadata=Base.metadata,
        default_database=DEFAULT_DATABASE, environment_key="WORMINAL_DATABASE_URL",
        database_url=database_url, prepare=_migrate_legacy_schema)
    repository = WorkspaceRepository(context.require_sessions(), context.clock.now)
    shell_user = os.environ.get("WORMINAL_SHELL_USER")
    resolve_shell_account(shell_user)
    manager = TerminalManager(shell_user, repository)
    remote_access_token = os.environ.get("WORMINAL_ACCESS_TOKEN")
    repository.initialize(remote_access_token)

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
        version = repository.access_session_version()
        return bool(version and cookie) and hmac.compare_digest(
            cookie, access_cookie_value(version))

    @application.middleware("http")
    async def guard_remote_access(request: Request, call_next):
        if is_loopback_client(request) or request.url.path in {"/worminal", "/api/access"}:
            return await call_next(request)
        if remote_session_authorized(request.cookies.get(ACCESS_COOKIE)):
            return await call_next(request)
        if repository.access_session_version():
            return PlainTextResponse("Worminal requires its access password.", status_code=401)
        return PlainTextResponse("Set WORMINAL_ACCESS_TOKEN before allowing remote access.",
            status_code=403)

    def workspace_id(request: Request) -> str | None:
        del request
        return repository.shared_workspace()

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
        if not is_loopback_client(request) and not remote_access_authorized(payload.password, repository):
            raise HTTPException(status_code=401, detail="Access password is not valid.")
        response = Response(status_code=204)
        version = repository.access_session_version()
        if version:
            set_session_cookie(response, request, ACCESS_COOKIE,
                access_cookie_value(version), COOKIE_AGE)
        return response

    @application.post("/api/access/password", status_code=204)
    def change_access_password(payload: PasswordChangeInput, request: Request) -> Response:
        reject_cross_origin(request)
        if not repository.change_access_password(
            payload.current_password, payload.new_password):
            raise HTTPException(status_code=401, detail="Current access password is not valid.")
        response = Response(status_code=204)
        set_session_cookie(response, request, ACCESS_COOKIE,
            access_cookie_value(repository.access_session_version()), COOKIE_AGE)
        return response

    @application.get("/api/workspace")
    def get_workspace(request: Request) -> JSONResponse:
        identifier = workspace_id(request)
        response = JSONResponse({"windows": repository.windows(identifier),
            "shortcuts": repository.shortcuts(identifier)})
        return response

    @application.put("/api/workspace", status_code=204)
    def save_workspace(payload: WorkspaceInput, request: Request) -> Response:
        reject_cross_origin(request)
        identifier = require_workspace(request)
        repository.replace_windows(identifier, [window.model_dump() for window in payload.windows])
        repository.replace_shortcuts(identifier, [shortcut.model_dump() for shortcut in payload.shortcuts])
        return Response(status_code=204)

    @application.delete("/api/workspace/windows/{window_id}", status_code=204)
    async def close_window(window_id: str, request: Request) -> Response:
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
        workspace = repository.shared_workspace()
        transcript = repository.transcript(workspace, window_id)
        if transcript is None:
            await socket.close(code=1008, reason="Terminal window is unavailable.")
            return
        await socket.accept()
        try:
            if transcript:
                await socket.send_bytes(transcript)
            session = manager.attach(window_id, socket)
            while True:
                payload = await socket.receive_json()
                if payload.get("type") == "input" and isinstance(payload.get("data"), str):
                    session.write(payload["data"])
                elif payload.get("type") == "resize":
                    session.resize(payload.get("columns", 100), payload.get("rows", 30))
        except (OSError, TypeError, ValueError, WebSocketDisconnect):
            pass
        finally:
            manager.detach(window_id, socket)

    return application


app = create_app()
