from __future__ import annotations
import asyncio
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

@dataclass(frozen=True)
class Event:
    name: str
    payload: dict[str, Any]

Handler = Callable[[Event], Awaitable[None]]

class EventBus:
    """Async event bus used to avoid polling and hard coupling."""
    def __init__(self) -> None:
        self._handlers: dict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, name: str, handler: Handler) -> None:
        self._handlers[name].append(handler)

    async def publish(self, name: str, **payload: Any) -> None:
        event = Event(name, payload)
        await asyncio.gather(*(h(event) for h in self._handlers.get(name, [])))
