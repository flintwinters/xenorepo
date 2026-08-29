"""FastAPI service for Rock Paper Scissors guest identity and persistence."""

from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from apps.rps.backend.auth import issue_credential
from apps.rps.backend.arena import ArenaCoordinator
from apps.rps.backend.database import Base, DomainError, RpsRepository, _migrate_realtime_columns
from apps.rps.backend.scheduling import AsyncIOScheduler, Clock, Scheduler, SystemClock
from monotools.runtime.appkit import create_app_context
from monotools.runtime.http import (
    domain_error_handler,
    enforce_same_origin,
    json_error,
    resolve_cookie_principal,
    set_session_cookie,
)
from monotools.runtime.realtime import websocket_origin_allowed
from monotools.runtime.application import create_application


DIRECTORY = Path(__file__).parent
DEFAULT_DATABASE = DIRECTORY / "data" / "rps.db"
COOKIE = "throw98_guest"
COOKIE_AGE = 365 * 24 * 60 * 60


class NicknameInput(BaseModel):
    nickname: str = ""


class PlayerState(BaseModel):
    id: str
    nickname: str
    competitive_streak: int


async def dispatch_arena_command(coordinator: ArenaCoordinator, player_id: str,
    payload: object) -> None:
    if not isinstance(payload, dict):
        raise DomainError("Arena command must be a JSON object.")
    command, client_id = payload.get("type"), payload.get("client_id")
    if not isinstance(client_id, str) or not 1 <= len(client_id) <= 64:
        raise DomainError("Client mutation ID is required.")
    simple_operations = {
        "queue_join": coordinator.join_queue,
        "queue_leave": coordinator.leave_queue,
    }
    if command in simple_operations:
        await simple_operations[command](player_id, client_id)
    elif command in {"rematch", "throw"}:
        await dispatch_match_command(coordinator, player_id, command, payload, client_id)
    elif command in {"spectate", "spectate_leave"}:
        operation = coordinator.spectate if command == "spectate" else coordinator.leave_spectator
        await operation(player_id,
            required_string(payload, "match_id", "Match ID is required."), client_id)
    else:
        raise DomainError("Unknown arena command.")


async def dispatch_match_command(coordinator: ArenaCoordinator, player_id: str,
    command: object, payload: dict[str, object], client_id: str) -> None:
    if command == "rematch":
        await coordinator.request_rematch(player_id,
            required_string(payload, "match_id", "Match ID is required."), client_id)
    else:
        await coordinator.submit_throw(player_id,
            required_string(payload, "selection", "Throw must be rock, paper, or scissors."),
            client_id)


def required_string(payload: dict[str, object], key: str, message: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str):
        raise DomainError(message)
    return value


def player_state(player: object) -> dict[str, object]:
    return {"id": player.id, "nickname": player.nickname,
        "competitive_streak": player.competitive_streak}


def create_app(database_url: str | None = None, *, clock: Clock | None = None,
    scheduler: Scheduler | None = None) -> FastAPI:
    resolved_clock = clock or SystemClock()
    context = create_app_context("rps", metadata=Base.metadata,
        default_database=DEFAULT_DATABASE, environment_key="RPS_DATABASE_URL",
        database_url=database_url, prepare=_migrate_realtime_columns, clock=resolved_clock)
    repository = RpsRepository(context.require_sessions(), context.clock.now)
    coordinator = ArenaCoordinator(repository, resolved_clock,
        scheduler or AsyncIOScheduler(resolved_clock))
    application = create_application("rps")

    def current_player(request: Request) -> object | None:
        return resolve_cookie_principal(request, COOKIE, repository.restore_guest)

    application.add_exception_handler(DomainError, domain_error_handler())

    @application.get("/api/session", response_model=PlayerState)
    def session_state(request: Request) -> PlayerState | JSONResponse:
        player = current_player(request)
        if player is not None:
            return JSONResponse(player_state(player))
        credential = issue_credential()
        player = repository.create_guest(credential)
        response = JSONResponse(player_state(player), status_code=201)
        return set_session_cookie(response, request, COOKIE, credential, COOKIE_AGE)

    @application.patch("/api/session", response_model=PlayerState)
    def update_session(payload: NicknameInput, request: Request) -> dict[str, object] | JSONResponse:
        rejected = enforce_same_origin(request, lambda message: json_error(message, 403))
        if rejected is not None:
            return rejected
        player = current_player(request)
        if player is None:
            return json_error("Guest session is required.", 401)
        return player_state(repository.rename(player.id, payload.nickname))

    @application.websocket("/ws")
    async def arena_socket(socket: WebSocket) -> None:
        if not websocket_origin_allowed(socket):
            await socket.close(code=1008, reason="Origin is not allowed.")
            return
        player = repository.restore_guest(socket.cookies.get(COOKIE))
        if player is None:
            await socket.close(code=1008, reason="Guest session is required.")
            return
        await coordinator.connect(socket, player)
        try:
            while True:
                try:
                    payload = await socket.receive_json()
                    await dispatch_arena_command(coordinator, player.id, payload)
                except (DomainError, ValueError) as failure:
                    await socket.send_json({"type": "error", "message": str(failure)})
        except WebSocketDisconnect:
            pass
        finally:
            await coordinator.disconnect(socket)

    application.state.repository = repository
    application.state.coordinator = coordinator
    return application


app = create_app()
