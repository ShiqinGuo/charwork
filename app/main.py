import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.app_state import stroke_service

from app.api.v1 import (
    routes_assignments,
    routes_auth,
    routes_comments,
    routes_export,
    routes_hanzi,
    routes_import,
    routes_logs,
    routes_messages,
    routes_submissions,
    routes_students,
    routes_teachers,
)

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="HanziProject 迁移至 FastAPI 异步架构"
)

if settings.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(routes_hanzi.router, prefix="/api/v1/hanzi", tags=["hanzi"])
app.include_router(routes_assignments.router, prefix="/api/v1/assignments", tags=["assignments"])
app.include_router(routes_auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(routes_import.router, prefix="/api/v1/import", tags=["import"])
app.include_router(routes_export.router, prefix="/api/v1/export", tags=["export"])
app.include_router(routes_logs.router, prefix="/api/v1/logs", tags=["logs"])
app.include_router(routes_teachers.router, prefix="/api/v1/teachers", tags=["teachers"])
app.include_router(routes_students.router, prefix="/api/v1/students", tags=["students"])
app.include_router(routes_submissions.router, prefix="/api/v1", tags=["submissions"])
app.include_router(routes_comments.router, prefix="/api/v1/comments", tags=["comments"])
app.include_router(routes_messages.router, prefix="/api/v1/messages", tags=["messages"])
app.mount("/media", StaticFiles(directory=settings.MEDIA_ROOT), name="media")


@app.lifespan("startup")
async def on_startup() -> None:
    setup_logging(settings.ENVIRONMENT)
    os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
    stroke_service.load()


@app.get("/")
def read_root():
    return {"message": "欢迎使用 HanziProject API"}


@app.get("/health")
def health_check():
    return {"status": "ok"}
