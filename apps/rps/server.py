"""FastAPI service for Rock Paper Scissors guest identity and persistence."""

import os
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from apps.rps.auth import issue_credential
from apps.rps.database import DomainError, RpsRepository, create_session_factory, sqlite_url


DIRECTORY = Path(__file__).parent
DIST = DIRECTORY / "dist"
DEFAULT_DATABASE = DIRECTORY / "data" / "rps.db"
COOKIE = "throw98_guest"
COOKIE_AGE = 365 * 24 * 60 * 60


class NicknameInput(BaseModel):
    nickname: str = ""


def origin_allowed(request: Request) -> bool:
    origin = request.headers.get("origin")
    if not origin:
        return True
    parsed = urlsplit(origin)
    return parsed.scheme == request.url.scheme and parsed.netloc == request.url.netloc


def player_state(player: object) -> dict[str, object]:
    return {"id": player.id, "nickname": player.nickname,
        "competitive_streak": player.competitive_streak}


def create_app(database_url: str | None = None) -> FastAPI:
    resolved = database_url or os.environ.get("RPS_DATABASE_URL") or sqlite_url(DEFAULT_DATABASE)
    repository = RpsRepository(create_session_factory(resolved))
    application = FastAPI(title="Rock Paper Scissors")

    def current_player(request: Request) -> object | None:
        return repository.restore_guest(request.cookies.get(COOKIE))

    @application.exception_handler(DomainError)
    async def domain_error(_request: Request, failure: DomainError) -> JSONResponse:
        return JSONResponse({"error": str(failure)}, status_code=400)

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/api/session")
    def session_state(request: Request) -> JSONResponse:
        player = current_player(request)
        if player is not None:
            return JSONResponse(player_state(player))
        credential = issue_credential()
        player = repository.create_guest(credential)
        response = JSONResponse(player_state(player), status_code=201)
        response.set_cookie(COOKIE, credential, max_age=COOKIE_AGE, httponly=True,
            samesite="lax", secure=request.url.scheme == "https", path="/")
        return response

    @application.patch("/api/session", response_model=None)
    def update_session(payload: NicknameInput, request: Request) -> dict[str, object] | JSONResponse:
        if not origin_allowed(request):
            return JSONResponse({"error": "Request origin is not allowed."}, status_code=403)
        player = current_player(request)
        if player is None:
            return JSONResponse({"error": "Guest session is required."}, status_code=401)
        return player_state(repository.rename(player.id, payload.nickname))

    @application.get("/", response_class=FileResponse)
    def index() -> Path:
        return DIST / "index.html"

    application.state.repository = repository
    return application


app = create_app()
