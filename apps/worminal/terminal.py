"""Pseudo-terminal sessions and locality checks for Worminal."""

import asyncio
import fcntl
import ipaddress
import os
from pathlib import Path
import pty
import shutil
import signal
import struct
import subprocess
import termios
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect


MAX_INPUT_BYTES = 64 * 1024
DEFAULT_COLUMNS = 100
DEFAULT_ROWS = 30


def is_loopback_client(socket: Any) -> bool:
    """Report whether a request or socket originates on the local machine."""
    host = getattr(getattr(socket, "client", None), "host", "")
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def login_shell() -> str:
    """Resolve the operator's configured shell without invoking a shell parser."""
    configured = os.environ.get("SHELL", "")
    if configured and Path(configured).is_absolute() and os.access(configured, os.X_OK):
        return configured
    return shutil.which("zsh") or shutil.which("bash") or "/bin/sh"


class PtySession:
    """Own one shell process and its pseudo-terminal file descriptor."""

    def __init__(self, shell: str | None = None) -> None:
        master, slave = pty.openpty()
        command = shell or login_shell()
        environment = os.environ | {"TERM": "xterm-256color", "COLORTERM": "truecolor"}
        try:
            self.process = subprocess.Popen(
                [command, "-l"], stdin=slave, stdout=slave, stderr=slave,
                cwd=Path.home(), env=environment, start_new_session=True, close_fds=True,
            )
        finally:
            os.close(slave)
        self.master = master
        self.closed = False
        self.resize(DEFAULT_COLUMNS, DEFAULT_ROWS)

    def resize(self, columns: int, rows: int) -> None:
        columns = min(max(int(columns), 20), 500)
        rows = min(max(int(rows), 5), 300)
        fcntl.ioctl(self.master, termios.TIOCSWINSZ, struct.pack("HHHH", rows, columns, 0, 0))

    def write(self, data: str) -> None:
        encoded = data.encode("utf-8")
        if len(encoded) > MAX_INPUT_BYTES:
            raise ValueError("terminal input exceeds the 64 KiB message limit")
        os.write(self.master, encoded)

    def read(self) -> bytes:
        return os.read(self.master, MAX_INPUT_BYTES)

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        os.close(self.master)
        if self.process.poll() is None:
            os.killpg(self.process.pid, signal.SIGTERM)
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(self.process.pid, signal.SIGKILL)
                self.process.wait(timeout=2)


async def bridge_terminal(socket: WebSocket, session: PtySession,
    on_output: Callable[[bytes], Awaitable[None]] | None = None, *, close_session: bool = True) -> None:
    """Relay one WebSocket bidirectionally until either side disconnects."""
    async def send_output() -> None:
        while True:
            data = await asyncio.to_thread(session.read)
            if not data:
                return
            if on_output is not None:
                await on_output(data)
            await socket.send_bytes(data)

    async def receive_input() -> None:
        while True:
            payload = await socket.receive_json()
            if payload.get("type") == "input" and isinstance(payload.get("data"), str):
                session.write(payload["data"])
            elif payload.get("type") == "resize":
                session.resize(payload.get("columns", DEFAULT_COLUMNS), payload.get("rows", DEFAULT_ROWS))

    tasks = {asyncio.create_task(send_output()), asyncio.create_task(receive_input())}
    try:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
        for task in pending:
            task.cancel()
    except (OSError, TypeError, ValueError, WebSocketDisconnect):
        pass
    finally:
        if close_session:
            session.close()
        for task in tasks:
            if not task.done():
                task.cancel()
