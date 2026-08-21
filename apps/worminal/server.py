"""Single FastAPI runtime for the localhost shell workspace."""

from fastapi import WebSocket

from apps.worminal.terminal import PtySession, bridge_terminal, is_loopback_client
from monotools.realtime import websocket_origin_allowed
from monotools.runtime import create_application


app = create_application("worminal")


@app.websocket("/ws/terminal")
async def terminal(socket: WebSocket) -> None:
    if not is_loopback_client(socket) or not websocket_origin_allowed(socket):
        await socket.close(code=1008, reason="Worminal accepts same-origin loopback clients only.")
        return
    await socket.accept()
    await bridge_terminal(socket, PtySession())
