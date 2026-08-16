"""Single FastAPI runtime for durable anonymous group chat."""

import os
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from apps.chat.database import ChatRepository, create_session_factory, sqlite_url
from tooling.realtime import (
    ConnectionRegistry,
    bounded_text,
    client_provenance,
    websocket_origin_allowed,
)


DIRECTORY = Path(__file__).parent
DIST = DIRECTORY / "dist"
DEFAULT_DATABASE = DIRECTORY / "data" / "chat.db"
MAX_AUTHOR_LENGTH = 40
MAX_MESSAGE_LENGTH = 2000


class ConnectionHub:
    """Coordinate ephemeral connections while storage owns durable state."""

    def __init__(self) -> None:
        self.connections = ConnectionRegistry[str]()

    async def connect(self, socket: WebSocket, repository: ChatRepository) -> None:
        await socket.accept()
        session_id = repository.open_session(client_provenance(socket))
        self.connections.register(socket, session_id)
        history = repository.all()
        await socket.send_json({"type": "history", "messages": history})
        await self.broadcast({"type": "presence", "count": len(self.connections)}, repository)

    async def disconnect(self, socket: WebSocket, repository: ChatRepository) -> None:
        session_id = self.connections.remove(socket)
        if session_id:
            repository.close_session(session_id)
        await self.broadcast({"type": "presence", "count": len(self.connections)}, repository)

    def identify(self, socket: WebSocket, repository: ChatRepository,
        participant_id: str, author: str) -> None:
        repository.identify(self.connections.context_for(socket), participant_id, author)

    async def publish(self, socket: WebSocket, repository: ChatRepository,
        author: str, body: str, client_id: str | None) -> None:
        message = repository.add(self.connections.context_for(socket), author, body, client_id)
        await self.broadcast({"type": "message", "message": message}, repository, int(message["id"]))

    async def broadcast(self, event: dict[str, Any], repository: ChatRepository,
        message_id: int | None = None) -> None:
        report = await self.connections.broadcast(event)
        if message_id:
            for session_id in report.delivered:
                repository.delivered(message_id, session_id)
        for disconnected in report.disconnected:
            repository.close_session(disconnected.context)


def clean_message(payload: dict[str, Any]) -> tuple[str, str, str | None] | None:
    author = bounded_text(payload.get("author"), MAX_AUTHOR_LENGTH)
    body = bounded_text(payload.get("body"), MAX_MESSAGE_LENGTH)
    if not author or not body:
        return None
    client_id = str(payload.get("client_message_id", "")) or None
    return author, body, client_id


def clean_identity(payload: dict[str, Any]) -> tuple[str, str] | None:
    try:
        participant_id = str(UUID(str(payload.get("participant_id", ""))))
    except ValueError:
        return None
    author = bounded_text(payload.get("author"), MAX_AUTHOR_LENGTH)
    return (participant_id, author) if author else None


def create_app(database_url: str | None = None) -> FastAPI:
    resolved_url = database_url or os.environ.get("CHAT_DATABASE_URL") or sqlite_url(DEFAULT_DATABASE)
    repository = ChatRepository(create_session_factory(resolved_url))
    hub = ConnectionHub()
    application = FastAPI(title="Common Room")

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/api/messages")
    def messages() -> list[dict[str, int | str]]:
        return repository.all()

    @application.websocket("/ws")
    async def live_chat(socket: WebSocket) -> None:
        if not websocket_origin_allowed(socket):
            await socket.close(code=1008, reason="Origin is not allowed.")
            return
        await hub.connect(socket, repository)
        try:
            while True:
                payload = await socket.receive_json()
                if payload.get("type") == "hello":
                    identity = clean_identity(payload)
                    if identity:
                        hub.identify(socket, repository, *identity)
                    continue
                cleaned = clean_message(payload)
                if cleaned is None:
                    await socket.send_json({"type": "error", "message": "Name and message are required."})
                    continue
                await hub.publish(socket, repository, *cleaned)
        except WebSocketDisconnect:
            await hub.disconnect(socket, repository)

    @application.get("/", response_class=FileResponse)
    def index() -> Path:
        return DIST / "index.html"

    return application


app = create_app()
