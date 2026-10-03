from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10000)


class ChatResponse(BaseModel):
    assistant: str
    provider: str


class MemoryType(str, Enum):
    fact = "fact"
    preference = "preference"
    project = "project"
    note = "note"


class MemoryCreate(BaseModel):
    type: MemoryType
    content: str = Field(min_length=1, max_length=10000)
    importance: float = Field(default=0.5, ge=0, le=1)

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("content must not be blank")
        return value


class MemoryResponse(MemoryCreate):
    id: int
    created_at: str
    updated_at: str


class PlanStepStatus(str, Enum):
    pending = "pending"
    running = "running"
    completed = "completed"
    failed = "failed"
    skipped = "skipped"


class PlannedStep(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2000)
    tool_name: str | None = Field(default=None, min_length=1, max_length=100)
    arguments: dict[str, Any] | None = None

    @field_validator("title", "description")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("tool_name")
    @classmethod
    def tool_name_must_not_be_blank(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value


class PlanCreate(BaseModel):
    steps: list[str | PlannedStep] = Field(min_length=1, max_length=100)

    @field_validator("steps")
    @classmethod
    def steps_must_not_be_blank(
        cls, steps: list[str | PlannedStep]
    ) -> list[str | PlannedStep]:
        normalized = [step.strip() if isinstance(step, str) else step for step in steps]
        if any(isinstance(step, str) and not step for step in normalized):
            raise ValueError("steps must not contain blank titles")
        return normalized


class GeneratedPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    steps: list[PlannedStep] = Field(min_length=1, max_length=100)


class PlanStepResponse(BaseModel):
    id: int
    task_id: int
    step_number: int
    title: str
    description: str
    tool_name: str | None = None
    arguments: dict[str, Any] | None = None
    status: PlanStepStatus
    result: str | None = None


class PlanResponse(BaseModel):
    id: int
    task_id: int
    created_at: str
    updated_at: str
    steps: list[PlanStepResponse]
