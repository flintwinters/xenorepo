"""Single FastAPI runtime for a local, ephemeral browser shell."""

import asyncio
import ipaddress
import json
import os
from pathlib import Path
import pty
import pwd
import signal
import struct
import subprocess
import termios
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from monotools.runtime.application import create_local_application
from monotools.runtime.realtime import websocket_origin_allowed


MAX_DIMENSION = 1000


def loopback_client(socket: WebSocket) -> bool:
    """Return whether the transport peer is local, without trusting proxy headers."""
    if socket.client is None:
        return False
    try:
        return ipaddress.ip_address(socket.client.host).is_loopback
    except ValueError:
        return socket.client.host == "localhost"


def terminal_size(payload: dict[str, Any]) -> tuple[int, int] | None:
    """Validate an untrusted resize message and return rows, columns."""
    if payload.get("type") != "resize":
        return None
    rows, columns = payload.get("rows"), payload.get("columns")
    if (not isinstance(rows, int) or isinstance(rows, bool)
        or not isinstance(columns, int) or isinstance(columns, bool)):
        return None
    if not (1 <= rows <= MAX_DIMENSION and 1 <= columns <= MAX_DIMENSION):
        return None
    return rows, columns


class PtySession:
    """Own one shell process group and its pseudoterminal descriptor."""

    def __init__(self, directory: Path | None = None, shell: str | None = None) -> None:
        master, slave = pty.openpty()
        command = shell or pwd.getpwuid(os.getuid()).pw_shell or "/bin/sh"
        try:
            self.process = subprocess.Popen([command, "-i"], cwd=directory or Path.home(),
                stdin=slave, stdout=slave, stderr=slave, start_new_session=True,
                close_fds=True)
        except Exception:
            os.close(master)
            raise
        finally:
            os.close(slave)
        self.master = master
        os.set_blocking(self.master, False)
        self.closed = False

    async def read(self) -> bytes:
        while True:
            try:
                return os.read(self.master, 65536)
            except BlockingIOError:
                if self.process.poll() is not None:
                    return b""
                await asyncio.sleep(0.01)

    def write(self, data: str) -> None:
        os.write(self.master, data.encode())

    def resize(self, rows: int, columns: int) -> None:
        size = struct.pack("HHHH", rows, columns, 0, 0)
        __import__("fcntl").ioctl(self.master, termios.TIOCSWINSZ, size)

    async def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        if self.process.poll() is None:
            os.killpg(self.process.pid, signal.SIGTERM)
            for _ in range(20):
                if self.process.poll() is not None:
                    break
                await asyncio.sleep(0.05)
            if self.process.poll() is None:
                os.killpg(self.process.pid, signal.SIGKILL)
                self.process.wait()
        os.close(self.master)


async def serve_terminal(socket: WebSocket, session: PtySession) -> None:
    """Bridge one accepted WebSocket to one already-created PTY."""
    def handle_text(text: str) -> None:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            session.write(text)
            return
        if not isinstance(payload, dict):
            return
        size = terminal_size(payload)
        if size:
            session.resize(*size)
        data = payload.get("data")
        if payload.get("type") == "input" and isinstance(data, str):
            session.write(data)

    async def send_output() -> None:
        while data := await session.read():
            await socket.send_bytes(data)

    async def receive_input() -> None:
        while True:
            message = await socket.receive()
            if message.get("text") is not None:
                handle_text(message["text"])
            elif message.get("bytes") is not None:
                os.write(session.master, message["bytes"])
            else:
                raise WebSocketDisconnect()

    output = asyncio.create_task(send_output())
    incoming = asyncio.create_task(receive_input())
    done, pending = await asyncio.wait((output, incoming), return_when=asyncio.FIRST_COMPLETED)
    for task in pending:
        task.cancel()
    await asyncio.gather(*done, *pending, return_exceptions=True)


def create_app(session_factory: type[PtySession] = PtySession) -> FastAPI:
    application = create_local_application(__file__)

    @application.websocket("/ws/terminal")
    async def terminal(socket: WebSocket) -> None:
        if not loopback_client(socket) or not websocket_origin_allowed(socket):
            await socket.close(code=1008, reason="A local same-origin connection is required.")
            return
        session = session_factory()
        await socket.accept()
        try:
            await serve_terminal(socket, session)
        finally:
            await session.close()

    return application


app = create_app()
