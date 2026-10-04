from contextlib import asynccontextmanager

import time
import logging
import secrets

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from backend.app.api.command import router as command_router
from backend.app.api.chat import router as chat_router
from backend.app.api.chat import agent as chat_agent
from backend.app.api.health import router as health_router
from backend.app.api.memory import router as memory_router
from backend.app.api.tasks import router as tasks_router
from backend.app.api.tools import router as tools_router
from backend.app.api.news import router as news_router
from backend.app.api.voice import router as voice_router
from backend.app.api.vision import router as vision_router
from backend.app.api.media import router as media_router
from backend.app.api.intelligence import router as intelligence_router
from backend.app.api.missions import router as missions_router
from backend.app.api.improvement import router as improvement_router
from backend.app.api.computer import router as computer_router
from backend.app.api.email import router as email_router
from backend.app.tools.browser_tools import browser_session
from backend.app.config.settings import settings
from backend.app.db.database import init_db
from backend.app.jobs.worker import worker
from backend.app.jobs.scheduler import scheduler


logger = logging.getLogger("leon.api")


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
    await chat_agent.close()
    await browser_session.close()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="LEON - Personal AI Agent and Digital Operating System",
    lifespan=lifespan,
)


@app.middleware("http")
async def latency_metrics(request, call_next):
    supplied_request_id = request.headers.get("X-Request-ID", "").strip()
    request_id = supplied_request_id[:100] if supplied_request_id else f"LEON-REQ-{secrets.token_urlsafe(12)}"
    request.state.request_id = request_id
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("request_failed request_id=%s method=%s path=%s", request_id, request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": {"code": "INTERNAL_ERROR", "message": "LEON could not process this request.", "request_id": request_id}},
            headers={"X-Request-ID": request_id},
        )
    elapsed_ms = (time.perf_counter() - started) * 1000
    response.headers["Server-Timing"] = f"total;dur={elapsed_ms:.1f}"
    response.headers["X-Request-ID"] = request_id
    logger.info("request_complete request_id=%s method=%s path=%s status=%s latency_ms=%.1f", request_id, request.method, request.url.path, response.status_code, elapsed_ms)
    return response
app.include_router(command_router, prefix="/api")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Accept",
        "Accept-Language",
        "Authorization",
        "Content-Type",
        "Origin",
        "X-Requested-With",
        "X-Request-ID",
    ],
    expose_headers=["X-Request-ID", "Server-Timing"],
)

app.include_router(health_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(tasks_router, prefix="/api")
app.include_router(tools_router, prefix="/api")
app.include_router(memory_router, prefix="/api")
app.include_router(news_router, prefix="/api")
app.include_router(voice_router, prefix="/api")
app.include_router(vision_router, prefix="/api")
app.include_router(media_router, prefix="/api")
app.include_router(intelligence_router, prefix="/api")
app.include_router(missions_router, prefix="/api")
app.include_router(improvement_router, prefix="/api")
app.include_router(computer_router, prefix="/api")
app.include_router(email_router, prefix="/api")


@app.get("/")
async def root():
    return {
        "name": "LEON",
        "status": "online",
        "version": settings.app_version,
    }
