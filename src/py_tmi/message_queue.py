from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional


@dataclass
class QueueItem:
    callback: Callable[[], Awaitable[None]]
    delay: Optional[float]


class MessageQueue:
    """Async delay queue that keeps Twitch commands within rate limits."""

    def __init__(self, default_delay: float, *, loop: Optional[asyncio.AbstractEventLoop] = None) -> None:
        self._default_delay = default_delay
        self._queue: "asyncio.Queue[QueueItem]" = asyncio.Queue()
        self._worker: Optional[asyncio.Task[None]] = None
        self._loop = loop or asyncio.get_event_loop()

    async def add(self, callback: Callable[[], Awaitable[None]], *, delay: Optional[float] = None) -> None:
        await self._queue.put(QueueItem(callback=callback, delay=delay))
        if self._worker is None or self._worker.done():
            self._worker = self._loop.create_task(self._run())

    async def _run(self) -> None:
        try:
            while True:
                item = await self._queue.get()
                try:
                    await item.callback()
                finally:
                    self._queue.task_done()
                await asyncio.sleep(item.delay or self._default_delay)
        except asyncio.CancelledError:
            raise

    async def join(self) -> None:
        await self._queue.join()

    def stop(self) -> None:
        if self._worker:
            self._worker.cancel()
            self._worker = None

