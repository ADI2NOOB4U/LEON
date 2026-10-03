from pydantic import BaseModel, Field


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    max_retries: int = Field(default=2, ge=0, le=10)


class TaskResponse(BaseModel):
    id: int
    title: str
    status: str
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    updated_at: str | None = None
    result: str | None = None
    error: str | None = None
    progress: int
    current_stage: str
    retry_count: int
    max_retries: int
    cancel_requested: int


class TaskLog(BaseModel):
    timestamp: str
    stage: str
    message: str
