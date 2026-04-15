"""
应用主入口模块。

初始化 FastAPI 应用，配置中间件（CORS、静态文件）、路由、生命周期事件等。
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1 import (
    routes_ai_chat,
    routes_assignment_reminders,
    routes_assignments,
    routes_auth,
    routes_comments,
    routes_courses,
    routes_custom_fields,
    routes_export,
    routes_hanzi,
    routes_import,
    routes_logs,
    routes_management_systems,
    routes_messages,
    routes_search,
    routes_student_classes,
    routes_students,
    routes_submissions,
    routes_teachers,
    routes_teaching_classes,
)
from app.core.app_state import stroke_service
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.logging import setup_logging
from app.services.cross_search_service import CrossSearchService
from app.services.hanzi_dictionary_search_service import HanziDictionarySearchService
from app.services.hanzi_dictionary_service import HanziDictionaryService
from app.services.management_system_service import ManagementSystemService


ROOT_MESSAGE = "Shaneguo's project"
HEALTH_STATUS = "ok"
ROUTER_CONFIGS = (
    (routes_hanzi.router, f"{settings.API_V1_STR}/hanzi", ["hanzi"]),
    (routes_assignments.router, f"{settings.API_V1_STR}/assignments", ["assignments"]),
    (routes_assignment_reminders.router, f"{settings.API_V1_STR}/assignments", ["assignment-reminders"]),
    (routes_auth.router, f"{settings.API_V1_STR}/auth", ["auth"]),
    (routes_courses.router, f"{settings.API_V1_STR}/courses", ["courses"]),
    (routes_custom_fields.router, f"{settings.API_V1_STR}/management-systems", ["custom-fields"]),
    (routes_management_systems.router, f"{settings.API_V1_STR}/management-systems", ["management-systems"]),
    (routes_import.router, f"{settings.API_V1_STR}/import", ["import"]),
    (routes_export.router, f"{settings.API_V1_STR}/export", ["export"]),
    (routes_logs.router, f"{settings.API_V1_STR}/logs", ["logs"]),
    (routes_teachers.router, f"{settings.API_V1_STR}/teachers", ["teachers"]),
    (routes_students.router, f"{settings.API_V1_STR}/students", ["students"]),
    (routes_student_classes.router, f"{settings.API_V1_STR}/students", ["student-classes"]),
    (routes_submissions.router, settings.API_V1_STR, ["submissions"]),
    (routes_comments.router, f"{settings.API_V1_STR}/comments", ["comments"]),
    (routes_messages.router, f"{settings.API_V1_STR}/messages", ["messages"]),
    (routes_search.router, f"{settings.API_V1_STR}/search", ["search"]),
    (routes_ai_chat.router, f"{settings.API_V1_STR}/ai-chat", ["ai-chat"]),
    (routes_teaching_classes.router, f"{settings.API_V1_STR}/teaching-classes", ["teaching-classes"]),
)


def _build_cors_options() -> dict[str, object]:
    """
    功能描述：
        构建corsoptions。

    参数：
        无。

    返回值：
        dict[str, object]: 返回字典形式的结果数据。
    """
    allow_all = "*" in settings.CORS_ORIGINS
    return {
        "allow_origins": ["*"] if allow_all else [str(origin) for origin in settings.CORS_ORIGINS],
        "allow_credentials": not allow_all,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
    }


async def _bootstrap_application() -> None:
    """
    功能描述：
        启动app时执行的钩子函数。

    参数：
        无。

    返回值：
        None: 无返回值。
    """
    setup_logging(settings.ENVIRONMENT)
    os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
    stroke_service.load()
    async with AsyncSessionLocal() as db:
        await ManagementSystemService(db).backfill_default_systems()
        await CrossSearchService(db).ensure_index_with_bootstrap()
        await HanziDictionaryService(db).initialize_from_strokes(settings.STROKES_FILE_PATH, force=False)
        await HanziDictionarySearchService(db).ensure_index_with_bootstrap()


def _include_routers(application: FastAPI) -> None:
    """
    功能描述：
        处理routers。

    参数：
        application (FastAPI): FastAPI 类型的数据。

    返回值：
        None: 无返回值。
    """
    for router, prefix, tags in ROUTER_CONFIGS:
        application.include_router(router, prefix=prefix, tags=tags)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """
    功能描述：
        处理main。

    参数：
        _app (FastAPI): FastAPI实例。

    返回值：
        None: 无返回值。
    """
    await _bootstrap_application()
    yield


app = FastAPI(
    title="CharWork API",
    lifespan=lifespan
)


if settings.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        **_build_cors_options(),
    )

_include_routers(app)
app.mount("/media", StaticFiles(directory=settings.MEDIA_ROOT), name="media")


@app.get("/")
def read_root():
    """
    功能描述：
        API节点测试

    参数：
        无。

    返回值：
        dict[str, object]: 返回ROOT_MESSAGE。
    """
    return {"message": ROOT_MESSAGE}


@app.get("/health")
def health_check():
    """
    功能描述：
        处理check。

    参数：
        无。

    返回值：
        None: 无返回值。
    """
    return {"status": HEALTH_STATUS}
