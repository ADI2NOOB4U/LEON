from __future__ import annotations

import asyncio
import inspect
from collections import defaultdict, deque
from typing import Any, Callable, Coroutine

from backend.app.events.schemas import Event, EventTopic

EventHandler = Callable[[Event], Any] | Callable[[Event], Coroutine[Any, Any, Any]]


class EventBus:
    def __init__(self, max_history: int = 100):
        self._subscribers: dict[str, set[EventHandler]] = defaultdict(set)
        self._wildcard_subscribers: set[EventHandler] = set()
        self._history: deque[Event] = deque(maxlen=max_history)

    @staticmethod
    def _topic(topic: EventTopic | str) -> str:
        return topic.value if isinstance(topic, EventTopic) else str(topic)

    def subscribe(self, topic: EventTopic | str, handler: EventHandler) -> None:
        key = self._topic(topic)
        (self._wildcard_subscribers if key == "*" else self._subscribers[key]).add(handler)

    def unsubscribe(self, topic: EventTopic | str, handler: EventHandler) -> None:
        key = self._topic(topic)
        (self._wildcard_subscribers if key == "*" else self._subscribers[key]).discard(handler)

    async def publish(self, event: Event) -> None:
        self._history.append(event)
        handlers = list(self._subscribers.get(self._topic(event.topic), set())) + list(self._wildcard_subscribers)
        for handler in handlers:
            try:
                result = handler(event)
                if inspect.isawaitable(result):
                    await result
            except Exception:
                continue

    def publish_sync(self, event: Event) -> None:
        self._history.append(event)
        for handler in list(self._subscribers.get(self._topic(event.topic), set())) + list(self._wildcard_subscribers):
            try:
                result = handler(event)
                if inspect.isawaitable(result):
                    try:
                        asyncio.get_running_loop().create_task(result)
                    except RuntimeError:
                        asyncio.run(result)
            except Exception:
                continue

    def emit(self, topic: EventTopic | str, **payload: Any) -> Event:
        event = Event(topic=self._topic(topic), payload=payload)
        self.publish_sync(event)
        return event

    def get_recent_events(self, limit: int = 50, topic_filter: str | None = None) -> list[Event]:
        events = list(self._history)
        if topic_filter:
            events = [event for event in events if event.topic.startswith(topic_filter)]
        return events[-limit:]

    def clear(self) -> None:
        self._subscribers.clear(); self._wildcard_subscribers.clear(); self._history.clear()


event_bus = EventBus()
