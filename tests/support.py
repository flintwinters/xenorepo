"""Curated deterministic doubles and async helpers for repository tests."""

import asyncio
import json
from types import SimpleNamespace
from typing import Any, Coroutine, TypeVar


Result = TypeVar("Result")


def run_async(operation: Coroutine[Any, Any, Result]) -> Result:
    return asyncio.run(operation)


class SocketDouble:
    def __init__(self, *, fail_sends: bool = False) -> None:
        self.events: list[dict[str, Any]] = []
        self.client = SimpleNamespace(host="127.0.0.1")
        self.headers: dict[str, str] = {}
        self.fail_sends = fail_sends
        self.accepted = False

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, event: dict[str, Any]) -> None:
        self.events.append(event)

    async def send_text(self, payload: str) -> None:
        if self.fail_sends:
            raise RuntimeError("socket closed")
        self.events.append(json.loads(payload))
