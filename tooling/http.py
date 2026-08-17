"""Shared HTTP security, provenance, principal, and response primitives."""

from collections.abc import Callable, Mapping
from typing import Any, TypeVar
from urllib.parse import urlsplit

from fastapi import Request
from fastapi.responses import JSONResponse, Response


Principal = TypeVar("Principal")
OriginRejection = Response | Exception


def same_origin_allowed(request: Request) -> bool:
    """Allow non-browser requests or browser requests from this exact origin."""
    origin = request.headers.get("origin")
    if not origin:
        return True
    parsed = urlsplit(origin)
    return parsed.scheme == request.url.scheme and parsed.netloc == request.url.netloc


def enforce_same_origin(
    request: Request, reject: Callable[[str], OriginRejection]
) -> Response | None:
    """Reject a cross-origin request using an application's established outcome.

    ``reject`` may return the application's JSON response or an exception to
    raise, allowing domains to preserve their existing error contract.
    """
    if same_origin_allowed(request):
        return None
    rejection = reject("Request origin is not allowed.")
    if isinstance(rejection, Exception):
        raise rejection
    return rejection


def resolve_cookie_principal(
    request: Request, cookie_name: str, resolver: Callable[[str | None], Principal | None]
) -> Principal | None:
    """Resolve a request principal from an opaque cookie through a repository."""
    return resolver(request.cookies.get(cookie_name))


def require_cookie_principal(
    request: Request,
    cookie_name: str,
    resolver: Callable[[str | None], Principal | None],
    reject: Callable[[str], Exception],
    message: str,
) -> Principal:
    """Resolve a cookie principal or raise an application's authentication error."""
    principal = resolve_cookie_principal(request, cookie_name, resolver)
    if principal is None:
        raise reject(message)
    return principal


def client_provenance(connection: Any) -> dict[str, str | None]:
    """Capture stable client facts for durable HTTP or WebSocket records."""
    client = getattr(connection, "client", None)
    headers = connection.headers
    return {
        "client_host": client.host if client else None,
        "user_agent": headers.get("user-agent"),
        "origin": headers.get("origin"),
    }


def json_error(message: str, status: int) -> JSONResponse:
    """Return the platform's stable JSON failure envelope."""
    return JSONResponse({"error": message}, status_code=status)


def domain_error_handler(
    *, statuses: Mapping[str, int] | None = None, default_status: int = 400
) -> Callable[[Request, Exception], JSONResponse]:
    """Build a stable JSON error handler for application domain exceptions."""
    status_by_kind = statuses or {}

    async def handle(_request: Request, failure: Exception) -> JSONResponse:
        kind = getattr(failure, "kind", None)
        return json_error(str(failure), status_by_kind.get(kind, default_status))

    return handle


def set_session_cookie(
    response: Response,
    request: Request,
    name: str,
    value: str,
    max_age: int,
) -> Response:
    """Attach a same-site, HTTP-only session cookie suitable for this request."""
    response.set_cookie(
        name,
        value,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        path="/",
    )
    return response


def delete_session_cookie(response: Response, name: str) -> Response:
    """Expire a session cookie using the platform's fixed root path."""
    response.delete_cookie(name, path="/")
    return response
