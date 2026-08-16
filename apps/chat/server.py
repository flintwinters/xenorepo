"""Single FastAPI runtime for durable anonymous group chat."""

import json
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from apps.chat.database import MessageRepository, create_session_factory, sqlite_url


DIRECTORY = Path(__file__).parent
DIST = DIRECTORY / "dist"
DEFAULT_DATABASE = DIRECTORY.parent.parent / ".state" / "chat.db"
MAX_AUTHOR_LENGTH = 40
MAX_MESSAGE_LENGTH = 2000


class ConnectionHub:
    """Coordinate ephemeral connections while storage owns durable state."""

    def __init__(self) -> None:
        self.connections: set[WebSocket] = set()

    async def connect(self, socket: WebSocket, repository: MessageRepository) -> None:
        await socket.accept()
        self.connections.add(socket)
        history = repository.all()
        await socket.send_json({"type": "history", "messages": history})
        await self.broadcast({"type": "presence", "count": len(self.connections)})

    async def disconnect(self, socket: WebSocket) -> None:
        self.connections.discard(socket)
        await self.broadcast({"type": "presence", "count": len(self.connections)})

    async def publish(
        self, repository: MessageRepository, author: str, body: str
    ) -> None:
        message = repository.add(author, body)
        await self.broadcast({"type": "message", "message": message})

    async def broadcast(self, event: dict[str, Any]) -> None:
        payload = json.dumps(event)
        stale: list[WebSocket] = []
        for socket in tuple(self.connections):
            try:
                await socket.send_text(payload)
            except RuntimeError:
                stale.append(socket)
        if stale:
            self.connections.difference_update(stale)


def clean_message(payload: dict[str, Any]) -> tuple[str, str] | None:
    author = str(payload.get("author", "")).strip()[:MAX_AUTHOR_LENGTH]
    body = str(payload.get("body", "")).strip()[:MAX_MESSAGE_LENGTH]
    if not author or not body:
        return None
    return author, body


def create_app(database_url: str | None = None) -> FastAPI:
    resolved_url = database_url or os.environ.get("CHAT_DATABASE_URL") or sqlite_url(DEFAULT_DATABASE)
    repository = MessageRepository(create_session_factory(resolved_url))
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
        await hub.connect(socket, repository)
        try:
            while True:
                cleaned = clean_message(await socket.receive_json())
                if cleaned is None:
                    await socket.send_json({"type": "error", "message": "Name and message are required."})
                    continue
                await hub.publish(repository, *cleaned)
        except WebSocketDisconnect:
            await hub.disconnect(socket)

    @application.get("/", response_class=FileResponse)
    def index() -> Path:
        return DIST / "index.html"

    return application


app = create_app()
