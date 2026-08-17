"""Typed, app-independent primitives for realtime WebSocket services."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import json
from typing import Any, Generic, Protocol, TypeVar
from urllib.parse import urlsplit

from monotools.http import client_provenance


Context = TypeVar("Context")


class RealtimeSocket(Protocol):
    """The minimal socket interface required by the connection registry."""

    async def send_text(self, payload: str) -> None: ...


@dataclass(frozen=True)
class Disconnect(Generic[Context]):
    socket: RealtimeSocket
    context: Context
    error: Exception


@dataclass(frozen=True)
class SendReport(Generic[Context]):
    delivered: tuple[Context, ...]
    disconnected: tuple[Disconnect[Context], ...]


class ConnectionRegistry(Generic[Context]):
    """Own active sockets and provide deterministic scoped delivery."""

    def __init__(self) -> None:
        self._connections: dict[RealtimeSocket, Context] = {}

    def __len__(self) -> int:
        return len(self._connections)

    def register(self, socket: RealtimeSocket, context: Context) -> None:
        self._connections[socket] = context

    def context_for(self, socket: RealtimeSocket) -> Context:
        return self._connections[socket]

    def remove(self, socket: RealtimeSocket) -> Context | None:
        return self._connections.pop(socket, None)

    def connections(self) -> tuple[tuple[RealtimeSocket, Context], ...]:
        return tuple(self._connections.items())

    async def send(self, socket: RealtimeSocket, event: Mapping[str, Any]) -> SendReport[Context]:
        context = self._connections.get(socket)
        if context is None:
            return SendReport((), ())
        return await self._deliver(((socket, context),), encode_event(event))

    async def broadcast(
        self,
        event: Mapping[str, Any],
        where: Callable[[Context], bool] | None = None,
    ) -> SendReport[Context]:
        selected = tuple(
            (socket, context)
            for socket, context in self._connections.items()
            if where is None or where(context)
        )
        return await self._deliver(selected, encode_event(event))

    async def _deliver(
        self,
        connections: tuple[tuple[RealtimeSocket, Context], ...],
        payload: str,
    ) -> SendReport[Context]:
        delivered: list[Context] = []
        disconnected: list[Disconnect[Context]] = []
        for socket, context in connections:
            try:
                await socket.send_text(payload)
                delivered.append(context)
            except Exception as error:
                if self._connections.get(socket) == context:
                    self._connections.pop(socket)
                disconnected.append(Disconnect(socket, context, error))
        return SendReport(tuple(delivered), tuple(disconnected))


def encode_event(event: Mapping[str, Any]) -> str:
    """Encode server events consistently and compactly."""
    return json.dumps(event, separators=(",", ":"), ensure_ascii=False)


def websocket_origin_allowed(socket: Any) -> bool:
    """Allow non-browser clients or browsers whose Origin matches the socket host."""
    origin = socket.headers.get("origin")
    if not origin:
        return True
    parsed = urlsplit(origin)
    expected_scheme = "https" if socket.url.scheme == "wss" else "http"
    return parsed.scheme == expected_scheme and parsed.netloc == socket.headers.get("host")


def bounded_text(value: Any, maximum: int) -> str | None:
    """Normalize required user text without silently truncating domain facts."""
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    return cleaned if 0 < len(cleaned) <= maximum else None
