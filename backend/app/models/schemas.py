from enum import Enum

from pydantic import BaseModel, Field, field_validator


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


class PlanCreate(BaseModel):
    steps: list[str] = Field(min_length=1, max_length=100)

    @field_validator("steps")
    @classmethod
    def steps_must_not_be_blank(cls, steps: list[str]) -> list[str]:
        normalized = [step.strip() for step in steps]
        if any(not step for step in normalized):
            raise ValueError("steps must not contain blank titles")
        return normalized


class PlanStepResponse(BaseModel):
    id: int
    task_id: int
    step_number: int
    title: str
    status: PlanStepStatus
    result: str | None = None


class PlanResponse(BaseModel):
    id: int
    task_id: int
    created_at: str
    updated_at: str
    steps: list[PlanStepResponse]
