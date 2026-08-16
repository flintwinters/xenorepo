"""FastAPI service for Rock Paper Scissors guest identity and persistence."""

import os
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from apps.rps.auth import issue_credential
from apps.rps.arena import ArenaCoordinator
from apps.rps.database import DomainError, RpsRepository, create_session_factory, sqlite_url
from apps.rps.scheduling import AsyncIOScheduler, Clock, Scheduler, SystemClock
from tooling.http import (
    json_error,
    same_origin_allowed,
    set_session_cookie,
)
from tooling.realtime import websocket_origin_allowed
from tooling.runtime import create_application


DIRECTORY = Path(__file__).parent
DIST = DIRECTORY / "dist"
DEFAULT_DATABASE = DIRECTORY / "data" / "rps.db"
COOKIE = "throw98_guest"
COOKIE_AGE = 365 * 24 * 60 * 60


class NicknameInput(BaseModel):
    nickname: str = ""


def player_state(player: object) -> dict[str, object]:
    return {"id": player.id, "nickname": player.nickname,
        "competitive_streak": player.competitive_streak}


def create_app(database_url: str | None = None, *, clock: Clock | None = None,
    scheduler: Scheduler | None = None) -> FastAPI:
    resolved = database_url or os.environ.get("RPS_DATABASE_URL") or sqlite_url(DEFAULT_DATABASE)
    resolved_clock = clock or SystemClock()
    repository = RpsRepository(create_session_factory(resolved), resolved_clock.now)
    coordinator = ArenaCoordinator(repository, resolved_clock,
        scheduler or AsyncIOScheduler(resolved_clock))
    application = create_application("Rock Paper Scissors", DIST / "index.html")

    def current_player(request: Request) -> object | None:
        return repository.restore_guest(request.cookies.get(COOKIE))

    @application.exception_handler(DomainError)
    async def domain_error(_request: Request, failure: DomainError) -> JSONResponse:
        return json_error(str(failure), 400)

    @application.get("/api/session")
    def session_state(request: Request) -> JSONResponse:
        player = current_player(request)
        if player is not None:
            return JSONResponse(player_state(player))
        credential = issue_credential()
        player = repository.create_guest(credential)
        response = JSONResponse(player_state(player), status_code=201)
        return set_session_cookie(response, request, COOKIE, credential, COOKIE_AGE)

    @application.patch("/api/session", response_model=None)
    def update_session(payload: NicknameInput, request: Request) -> dict[str, object] | JSONResponse:
        if not same_origin_allowed(request):
            return json_error("Request origin is not allowed.", 403)
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
                    if not isinstance(payload, dict):
                        raise DomainError("Arena command must be a JSON object.")
                    command = payload.get("type")
                    client_id = payload.get("client_id")
                    if not isinstance(client_id, str) or not 1 <= len(client_id) <= 64:
                        raise DomainError("Client mutation ID is required.")
                    if command == "queue_join":
                        await coordinator.join_queue(player.id, client_id)
                    elif command == "queue_leave":
                        await coordinator.leave_queue(player.id, client_id)
                    elif command == "throw":
                        selection = payload.get("selection")
                        if not isinstance(selection, str):
                            raise DomainError("Throw must be rock, paper, or scissors.")
                        await coordinator.submit_throw(player.id, selection, client_id)
                    elif command in {"spectate", "spectate_leave"}:
                        match_id = payload.get("match_id")
                        if not isinstance(match_id, str):
                            raise DomainError("Match ID is required.")
                        operation = coordinator.spectate if command == "spectate" \
                            else coordinator.leave_spectator
                        await operation(player.id, match_id, client_id)
                    else:
                        raise DomainError("Unknown arena command.")
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
