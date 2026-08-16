"""Shared HTTP security, provenance, and response primitives."""

from typing import Any
from urllib.parse import urlsplit

from fastapi import Request
from fastapi.responses import JSONResponse, Response


def same_origin_allowed(request: Request) -> bool:
    """Allow non-browser requests or browser requests from this exact origin."""
    origin = request.headers.get("origin")
    if not origin:
        return True
    parsed = urlsplit(origin)
    return parsed.scheme == request.url.scheme and parsed.netloc == request.url.netloc


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
