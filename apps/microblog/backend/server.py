"""Single FastAPI runtime for the WIRE/98 public microblog."""

from collections.abc import Iterator
from pathlib import Path
from threading import Condition

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from apps.microblog.backend.auth import ValidationError, issue_token
from apps.microblog.backend.database import Base, DomainError, MicroblogRepository
from monotools.runtime.appkit import create_app_context
from monotools.runtime.http import (
    client_provenance,
    delete_session_cookie,
    domain_error_handler,
    enforce_same_origin,
    json_error,
    require_cookie_principal,
    resolve_cookie_principal,
    set_session_cookie,
)
from monotools.runtime.application import create_application


DIRECTORY = Path(__file__).parent
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

    def wait_for_event(self, last_seen: int) -> tuple[int, str]:
        """Wait for a revision and construct its SSE frame while synchronized."""
        with self.condition:
            changed = self.condition.wait_for(
                lambda: self.revision > last_seen, timeout=self.keepalive_seconds
            )
            revision = self.revision if changed else last_seen
            event = (f"id: {revision}\nevent: feed\ndata: {revision}\n\n"
                if changed else ": keepalive\n\n")
        return revision, event

    def events(self, last_seen: int = 0) -> Iterator[str]:
        revision = last_seen
        while True:
            revision, event = self.wait_for_event(revision)
            yield event


def create_app(database_url: str | None = None) -> FastAPI:
    context = create_app_context("microblog", metadata=Base.metadata,
        default_database=DEFAULT_DATABASE, environment_key="MICROBLOG_DATABASE_URL",
        database_url=database_url)
    repository = MicroblogRepository(context.require_sessions(), context.clock.now)
    changes = ChangeFeed()
    application = create_application("microblog")

    def current_account(request: Request) -> object | None:
        return resolve_cookie_principal(request, COOKIE, repository.account_for_token)

    def enforce_origin(request: Request) -> None:
        enforce_same_origin(request, lambda message: DomainError(message, "forbidden"))

    def require_account(request: Request) -> object:
        return require_cookie_principal(
            request, COOKIE, repository.account_for_token,
            lambda message: DomainError(message, "authentication"),
            "Authentication required.",
        )

    application.add_exception_handler(DomainError, domain_error_handler(statuses={
        "authentication": 401, "conflict": 409, "forbidden": 403, "missing": 404,
    }))

    @application.exception_handler(ValidationError)
    async def validation_error(_request: Request, failure: ValidationError) -> JSONResponse:
        return json_error(str(failure), 400)

    @application.get("/api/session")
    def session_state(request: Request) -> dict[str, object]:
        account = current_account(request)
        return {"authenticated": account is not None,
            "account": {"id": account.id, "handle": account.handle} if account else None}

    def signed_in_response(account: object, request: Request) -> JSONResponse:
        token = issue_token()
        repository.create_session(account.id, token, client_provenance(request))
        response = JSONResponse({"authenticated": True,
            "account": {"id": account.id, "handle": account.handle}}, status_code=201)
        return set_session_cookie(response, request, COOKIE, token, COOKIE_AGE)

    @application.post("/api/accounts")
    def register(payload: Credentials, request: Request) -> JSONResponse:
        enforce_origin(request)
        return signed_in_response(repository.register(payload.handle, payload.password), request)

    @application.post("/api/sessions")
    def login(payload: Credentials, request: Request) -> JSONResponse:
        enforce_origin(request)
        account = repository.verify_login(payload.handle, payload.password)
        if account is None:
            return json_error("Invalid handle or password.", 401)
        return signed_in_response(account, request)

    @application.delete("/api/session")
    def logout(request: Request) -> JSONResponse:
        enforce_origin(request)
        repository.revoke_session(request.cookies.get(COOKIE))
        response = JSONResponse({"authenticated": False, "account": None})
        return delete_session_cookie(response, COOKIE)

    @application.get("/api/posts", response_model=None)
    def list_posts(request: Request, before: str | None = None,
        limit: str = "50") -> list[dict[str, object]] | JSONResponse:
        try:
            parsed_before = int(before) if before is not None else None
            parsed_limit = int(limit)
            if parsed_before is not None and parsed_before < 1:
                raise ValueError
        except ValueError:
            return json_error("Pagination parameters are invalid.", 400)
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

    return application


app = create_app()
