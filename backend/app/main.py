from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.api.command import router as command_router
from backend.app.api.chat import router as chat_router
from backend.app.api.health import router as health_router
from backend.app.api.memory import router as memory_router
from backend.app.api.tasks import router as tasks_router
from backend.app.api.tools import router as tools_router
from backend.app.api.news import router as news_router
from backend.app.api.voice import router as voice_router
from backend.app.config.settings import settings
from backend.app.db.database import init_db
from backend.app.jobs.worker import worker
from backend.app.jobs.scheduler import scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    from backend.app.news.service import news_service
    news_service.ensure_schedules(scheduler)
    worker.start()
    scheduler.start()

    yield

    worker.stop()
    scheduler.stop()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="LEON - Personal AI Agent and Digital Operating System",
    lifespan=lifespan,
)
app.include_router(command_router, prefix="/api")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(tasks_router, prefix="/api")
app.include_router(tools_router, prefix="/api")
app.include_router(memory_router, prefix="/api")
app.include_router(news_router, prefix="/api")
app.include_router(voice_router, prefix="/api")


@app.get("/")
async def root():
    return {
        "name": "LEON",
        "status": "online",
        "version": settings.app_version,
    }
