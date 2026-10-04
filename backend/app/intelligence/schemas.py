from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class RequestKind(StrEnum):
    SIMPLE = "simple"
    ACTION = "action"
    TASK = "task"
    CHAT = "chat"


class Intent(BaseModel):
    """The safe, typed result of classifying one user turn."""

    name: str = Field(alias="intent")
    confidence: float = Field(ge=0, le=1)
    entities: dict[str, Any] = Field(default_factory=dict)
    capability: str = "chat.general"
    action: str = "chat"
    kind: RequestKind = RequestKind.CHAT
    needs_web: bool = False
    needs_vision: bool = False
    needs_memory: bool = False
    requires_confirmation: bool = False
    privacy_class: str = "public"

    model_config = {"populate_by_name": True}


class RouteCandidate(BaseModel):
    route: str
    score: float = Field(ge=0, le=1)
    provider: str
    available: bool = True
    explanation: list[str] = Field(default_factory=list)


class RouteDecision(BaseModel):
    intent: Intent
    route: str
    provider: str
    confidence: float = Field(ge=0, le=1)
    candidates: list[RouteCandidate] = Field(default_factory=list)
    requires_confirmation: bool = False
    permission: str = "SAFE"
    needs_web: bool = False
    needs_vision: bool = False
    needs_memory: bool = False
    model_role: str | None = None
    fallback_route: str | None = None
    explanation: list[str] = Field(default_factory=list)
    routing_ms: float = 0.0

    def diagnostic(self) -> dict[str, Any]:
        return {
            "intent": self.intent.name,
            "confidence": round(self.confidence, 4),
            "route": self.route,
            "provider": self.provider,
            "needs_web": self.needs_web,
            "needs_vision": self.needs_vision,
            "needs_memory": self.needs_memory,
            "requires_confirmation": self.requires_confirmation,
            "permission": self.permission,
            "kind": self.intent.kind.value,
            "model_role": self.model_role,
            "explanation": self.explanation,
        }
