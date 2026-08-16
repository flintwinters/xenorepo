"""Single FastAPI runtime for the WIRE/98 public microblog."""

from collections.abc import Iterator
import os
from pathlib import Path
from threading import Condition
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from apps.microblog.auth import ValidationError, issue_token
from apps.microblog.database import DomainError, MicroblogRepository, create_session_factory, sqlite_url


DIRECTORY = Path(__file__).parent
DIST = DIRECTORY / "dist"
DEFAULT_DATABASE = DIRECTORY / "data" / "microblog.db"
COOKIE = "wire98_session"
COOKIE_AGE = 30 * 24 * 60 * 60


class Credentials(BaseModel):
    handle: str = ""
    password: str = ""


class PostInput(BaseModel):
    body: str = ""


class ChangeFeed:
    """Wake every connected feed when durable public state changes."""

    def __init__(self, keepalive_seconds: float = 20) -> None:
        self.condition = Condition()
        self.revision = 0
        self.keepalive_seconds = keepalive_seconds

    def publish(self) -> int:
        with self.condition:
            self.revision += 1
            self.condition.notify_all()
            return self.revision

    def events(self, last_seen: int = 0) -> Iterator[str]:
        revision = last_seen
        while True:
            with self.condition:
                changed = self.condition.wait_for(
                    lambda: self.revision > revision, timeout=self.keepalive_seconds
                )
                if changed:
                    revision = self.revision
                event = (f"id: {revision}\nevent: feed\ndata: {revision}\n\n"
                    if changed else ": keepalive\n\n")
            yield event


def error(message: str, status: int) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status)


def provenance(request: Request) -> dict[str, str | None]:
    return {"client_host": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
        "origin": request.headers.get("origin")}


def origin_is_valid(request: Request) -> bool:
    origin = request.headers.get("origin")
    if not origin:
        return True
    parsed = urlsplit(origin)
    return parsed.scheme == request.url.scheme and parsed.netloc == request.url.netloc


def create_app(database_url: str | None = None) -> FastAPI:
    resolved = database_url or os.environ.get("MICROBLOG_DATABASE_URL") or sqlite_url(DEFAULT_DATABASE)
    repository = MicroblogRepository(create_session_factory(resolved))
    changes = ChangeFeed()
    application = FastAPI(title="WIRE/98")

    def current_account(request: Request) -> object | None:
        return repository.account_for_token(request.cookies.get(COOKIE))

    def enforce_origin(request: Request) -> None:
        if not origin_is_valid(request):
            raise DomainError("Request origin is not allowed.", "forbidden")

    def require_account(request: Request) -> object:
        account = current_account(request)
        if account is None:
            raise DomainError("Authentication required.", "authentication")
        return account

    @application.exception_handler(DomainError)
    async def domain_error(_request: Request, failure: DomainError) -> JSONResponse:
        statuses = {"authentication": 401, "conflict": 409, "forbidden": 403, "missing": 404}
        return error(str(failure), statuses.get(failure.kind, 400))

    @application.exception_handler(ValidationError)
    async def validation_error(_request: Request, failure: ValidationError) -> JSONResponse:
        return error(str(failure), 400)

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/api/session")
    def session_state(request: Request) -> dict[str, object]:
        account = current_account(request)
        return {"authenticated": account is not None,
            "account": {"id": account.id, "handle": account.handle} if account else None}

    def signed_in_response(account: object, request: Request) -> JSONResponse:
        token = issue_token()
        repository.create_session(account.id, token, provenance(request))
        response = JSONResponse({"authenticated": True,
            "account": {"id": account.id, "handle": account.handle}}, status_code=201)
        response.set_cookie(COOKIE, token, max_age=COOKIE_AGE, httponly=True,
            samesite="lax", secure=request.url.scheme == "https", path="/")
        return response

    @application.post("/api/accounts")
    def register(payload: Credentials, request: Request) -> JSONResponse:
        enforce_origin(request)
        return signed_in_response(repository.register(payload.handle, payload.password), request)

    @application.post("/api/sessions")
    def login(payload: Credentials, request: Request) -> JSONResponse:
        enforce_origin(request)
        account = repository.verify_login(payload.handle, payload.password)
        if account is None:
            return error("Invalid handle or password.", 401)
        return signed_in_response(account, request)

    @application.delete("/api/session")
    def logout(request: Request) -> JSONResponse:
        enforce_origin(request)
        repository.revoke_session(request.cookies.get(COOKIE))
        response = JSONResponse({"authenticated": False, "account": None})
        response.delete_cookie(COOKIE, path="/")
        return response

    @application.get("/api/posts", response_model=None)
    def list_posts(request: Request, before: str | None = None,
        limit: str = "50") -> list[dict[str, object]] | JSONResponse:
        try:
            parsed_before = int(before) if before is not None else None
            parsed_limit = int(limit)
            if parsed_before is not None and parsed_before < 1:
                raise ValueError
        except ValueError:
            return error("Pagination parameters are invalid.", 400)
        account = current_account(request)
        return repository.posts(account.id if account else None, parsed_before, parsed_limit)

    @application.get("/api/events", response_class=StreamingResponse)
    def live_events(request: Request) -> StreamingResponse:
        try:
            last_seen = int(request.headers.get("last-event-id", "0"))
        except ValueError:
            last_seen = 0
        return StreamingResponse(changes.events(last_seen), media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @application.post("/api/posts", status_code=201)
    def publish(payload: PostInput, request: Request) -> dict[str, object]:
        enforce_origin(request)
        account = require_account(request)
        post = repository.add_post(account.id, payload.body)
        changes.publish()
        return post

    @application.put("/api/posts/{post_id}/like")
    def like(post_id: int, request: Request) -> dict[str, object]:
        enforce_origin(request)
        account = require_account(request)
        post = repository.set_like(account.id, post_id, True)
        changes.publish()
        return post

    @application.delete("/api/posts/{post_id}/like")
    def unlike(post_id: int, request: Request) -> dict[str, object]:
        enforce_origin(request)
        account = require_account(request)
        post = repository.set_like(account.id, post_id, False)
        changes.publish()
        return post

    @application.get("/", response_class=FileResponse)
    def index() -> Path:
        return DIST / "index.html"

    return application


app = create_app()
