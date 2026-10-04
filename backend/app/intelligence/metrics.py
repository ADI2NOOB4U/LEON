from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from threading import Lock
from typing import Any


class RouteMetrics:
    """Small process-local telemetry buffer; it never stores request text."""
    def __init__(self, maxlen: int = 500):
        self._events: deque[dict[str, Any]] = deque(maxlen=maxlen)
        self._lock = Lock()

    def record(self, *, intent: str, route: str, confidence: float, provider: str,
               success: bool | None = None, latency_ms: float = 0,
               fallback_used: bool = False, confirmation_required: bool = False,
               verification_result: bool | None = None) -> None:
        event = {"timestamp": datetime.now(timezone.utc).isoformat(), "intent": intent,
                 "route": route, "confidence": round(confidence, 4), "provider": provider,
                 "success": success, "latency_ms": round(latency_ms, 3),
                 "fallback_used": fallback_used, "confirmation_required": confirmation_required,
                 "verification_result": verification_result}
        with self._lock:
            self._events.append(event)

    def snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._events)
