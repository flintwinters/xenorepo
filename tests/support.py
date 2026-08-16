"""Curated deterministic doubles and async helpers for repository tests."""

import asyncio
from datetime import datetime, timedelta, timezone
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


class FakeClock:
    def __init__(self, value: datetime | None = None) -> None:
        self.value = value or datetime(2026, 1, 1, tzinfo=timezone.utc)

    def now(self) -> datetime:
        return self.value


class FakeScheduler:
    def __init__(self, clock: FakeClock) -> None:
        self.clock = clock
        self.pending: list[tuple[datetime, int, object]] = []
        self.sequence = 0

    def call_at(self, when: datetime, callback: object) -> None:
        self.sequence += 1
        self.pending.append((when, self.sequence, callback))

    async def advance(self, seconds: float) -> None:
        target = self.clock.value + timedelta(seconds=seconds)
        while True:
            due = [item for item in self.pending if item[0] <= target]
            if not due:
                break
            item = min(due, key=lambda candidate: (candidate[0], candidate[1]))
            self.pending.remove(item)
            self.clock.value = item[0]
            await item[2]()
        self.clock.value = target
