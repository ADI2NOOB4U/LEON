from pydantic import BaseModel, Field


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    max_retries: int = Field(default=2, ge=0, le=10)
    task_type: str = Field(default="standard", pattern="^(standard|research)$")
    research_source_count: int = Field(default=5, ge=1, le=20)
    notify_on_completion: bool = True


class TaskArtifact(BaseModel):
    id: int
    task_id: int
    path: str
    type: str
    size: int
    created_at: str


class TaskResponse(BaseModel):
    id: int
    title: str
    status: str
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    updated_at: str | None = None
    last_activity: str | None = None
    result: str | None = None
    summary: str | None = None
    error: str | None = None
    progress: int
    current_stage: str
    retry_count: int
    max_retries: int
    cancel_requested: int
    task_type: str = "standard"
    research_source_count: int = 5
    notify_on_completion: int = 1
    artifacts: list[TaskArtifact] = []


class TaskLog(BaseModel):
    timestamp: str
    stage: str
    message: str
