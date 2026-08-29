"""Injectable time and scheduling boundaries for arena coordination."""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Protocol

from monotools.runtime.appkit import Clock, SystemClock


Callback = Callable[[], Awaitable[None]]


class Scheduler(Protocol):
    def call_at(self, when: datetime, callback: Callback) -> None: ...


class AsyncIOScheduler:
    def __init__(self, clock: Clock) -> None:
        self.clock = clock

    def call_at(self, when: datetime, callback: Callback) -> None:
        async def run() -> None:
            delay = max(0.0, (when - self.clock.now()).total_seconds())
            await asyncio.sleep(delay)
            await callback()

        asyncio.create_task(run())
