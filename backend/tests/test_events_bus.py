"""
Tests for Event Bus subsystem.
"""
import asyncio
import pytest
from backend.app.events.schemas import EventTopic, Event
from backend.app.events.bus import EventBus


def test_event_bus_subscribe_and_publish():
    bus = EventBus()
    received_events = []

    def handler(event: Event):
        received_events.append(event)

    bus.subscribe(EventTopic.TASK_COMPLETED, handler)

    event = Event(
        topic=EventTopic.TASK_COMPLETED,
        payload={"task_id": "task_123", "status": "success"},
    )

    async def _run():
        await bus.publish(event)
        await asyncio.sleep(0.05)

    asyncio.run(_run())

    assert len(received_events) == 1
    assert received_events[0].topic == EventTopic.TASK_COMPLETED
    assert received_events[0].payload["task_id"] == "task_123"


def test_event_bus_unsubscribe():
    bus = EventBus()
    received_events = []

    def handler(event: Event):
        received_events.append(event)

    bus.subscribe(EventTopic.VOICE_COMMAND_DETECTED, handler)
    bus.unsubscribe(EventTopic.VOICE_COMMAND_DETECTED, handler)

    event = Event(
        topic=EventTopic.VOICE_COMMAND_DETECTED,
        payload={"text": "hello"},
    )

    async def _run():
        await bus.publish(event)
        await asyncio.sleep(0.05)

    asyncio.run(_run())

    assert len(received_events) == 0


def test_event_bus_async_handler():
    bus = EventBus()
    async_received = []

    async def async_handler(event: Event):
        await asyncio.sleep(0.01)
        async_received.append(event)

    bus.subscribe(EventTopic.SECURITY_VIOLATION, async_handler)

    event = Event(
        topic=EventTopic.SECURITY_VIOLATION,
        payload={"reason": "injection_detected"},
    )

    async def _run():
        await bus.publish(event)
        await asyncio.sleep(0.05)

    asyncio.run(_run())

    assert len(async_received) == 1
    assert async_received[0].payload["reason"] == "injection_detected"

