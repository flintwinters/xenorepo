"""Pseudo-terminal sessions and locality checks for Worminal."""

import asyncio
import fcntl
import ipaddress
import os
from pathlib import Path
import pwd
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


class ShellAccount:
    """The Unix identity and login environment for one terminal process."""

    def __init__(self, name: str, uid: int, gid: int, home: Path, shell: str) -> None:
        self.name, self.uid, self.gid, self.home, self.shell = name, uid, gid, home, shell


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


def resolve_shell_account(name: str | None) -> ShellAccount | None:
    """Resolve a selected Unix account and reject unavailable privilege changes."""
    if name is None:
        return None
    try:
        record = pwd.getpwnam(name)
    except KeyError as error:
        raise ValueError(f"Unknown terminal user: {name}") from error
    if os.geteuid() != 0 and record.pw_uid != os.geteuid():
        raise PermissionError("Serving another terminal user requires a root-owned service.")
    home = Path(record.pw_dir)
    if not home.is_dir():
        raise ValueError(f"Terminal user {name} has no usable home directory: {home}")
    shell = record.pw_shell if Path(record.pw_shell).is_absolute() and os.access(record.pw_shell, os.X_OK) else login_shell()
    return ShellAccount(record.pw_name, record.pw_uid, record.pw_gid, home, shell)


def _drop_privileges(account: ShellAccount | None):
    """Return the child-only identity transition when the service is privileged."""
    if account is None or os.geteuid() != 0 or account.uid == 0:
        return None

    def drop() -> None:
        os.setgid(account.gid)
        os.initgroups(account.name, account.gid)
        os.setuid(account.uid)

    return drop


class PtySession:
    """Own one shell process and its pseudo-terminal file descriptor."""

    def __init__(self, shell: str | None = None, user: str | None = None) -> None:
        account = resolve_shell_account(user)
        master, slave = pty.openpty()
        command = shell or (account.shell if account is not None else login_shell())
        environment = os.environ | {"TERM": "xterm-256color", "COLORTERM": "truecolor"}
        if account is not None:
            environment |= {"HOME": str(account.home), "USER": account.name,
                "LOGNAME": account.name, "SHELL": command}
        try:
            self.process = subprocess.Popen(
                [command, "-l"], stdin=slave, stdout=slave, stderr=slave,
                cwd=account.home if account is not None else Path.home(), env=environment,
                preexec_fn=_drop_privileges(account), start_new_session=True, close_fds=True,
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
