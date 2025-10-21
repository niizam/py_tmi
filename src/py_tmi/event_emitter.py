from __future__ import annotations

import asyncio
import inspect
from collections import defaultdict
from typing import Any, Awaitable, Callable, DefaultDict, Dict, Iterable, List, Optional

Listener = Callable[..., Any]


class EventEmitter:
    """A lightweight event emitter inspired by Node.js' implementation."""

    def __init__(self) -> None:
        self._events: DefaultDict[str, List[Listener]] = defaultdict(list)
        self._max_listeners: int = 0

    def set_max_listeners(self, n: int) -> "EventEmitter":
        self._max_listeners = n
        return self

    def on(self, event: str, listener: Listener) -> "EventEmitter":
        listeners = self._events[event]
        if self._max_listeners and len(listeners) >= self._max_listeners:
            raise RuntimeError(f"Max listeners exceeded for event '{event}'")
        listeners.append(listener)
        return self

    def once(self, event: str, listener: Listener) -> "EventEmitter":
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            self.off(event, wrapper)
            return listener(*args, **kwargs)

        return self.on(event, wrapper)

    def off(self, event: str, listener: Listener) -> "EventEmitter":
        listeners = self._events.get(event)
        if not listeners:
            return self
        try:
            listeners.remove(listener)
        except ValueError:
            return self
        if not listeners:
            self._events.pop(event, None)
        return self

    def remove_all_listeners(self, event: Optional[str] = None) -> "EventEmitter":
        if event is None:
            self._events.clear()
        else:
            self._events.pop(event, None)
        return self

    def listeners(self, event: str) -> Iterable[Listener]:
        return tuple(self._events.get(event, ()))

    def listener_count(self, event: str) -> int:
        return len(self._events.get(event, ()))

    def emit(self, event: str, *args: Any, **kwargs: Any) -> bool:
        listeners = list(self._events.get(event, ()))
        if not listeners:
            if event == "error":
                error = args[0] if args else RuntimeError('Uncaught "error" event.')
                raise error if isinstance(error, BaseException) else RuntimeError(error)
            return False

        for listener in listeners:
            result = listener(*args, **kwargs)
            if inspect.isawaitable(result):
                asyncio.create_task(self._ensure_future(result))
        return True

    def emit_many(
        self, events: Iterable[str], payloads: Iterable[Iterable[Any]]
    ) -> None:
        payloads_list = list(payloads)
        for index, event in enumerate(events):
            payload = payloads_list[index] if index < len(payloads_list) else payloads_list[-1]
            self.emit(event, *payload)

    @staticmethod
    async def _ensure_future(awaitable: Awaitable[Any]) -> None:
        try:
            await awaitable
        except Exception as exc:  # pragma: no cover - best effort logging
            loop = asyncio.get_running_loop()
            loop.call_exception_handler(
                {"message": "Unhandled error in EventEmitter listener", "exception": exc}
            )


__all__ = ["EventEmitter"]
