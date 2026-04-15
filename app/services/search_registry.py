"""
为什么这样做：检索注册中心把“表 -> 文档构建器”统一声明，便于增删模块时最小改动接入。
特殊逻辑：按配置表名动态启用模块，避免未开放数据被同步到全局检索索引。
"""

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.assignment import Assignment
from app.models.comment import Comment, TargetType
from app.models.course import Course
from app.models.hanzi import Hanzi
from app.models.management_system import UserManagementSystem
from app.models.student import Student
from app.models.submission import Submission
from app.models.teaching_class import TeachingClass


DICTIONARY_SEARCH_TABLE = "hanzi_dictionary"


@dataclass(frozen=True)
class SearchDocument:
    module: str
    source_id: str
    title: str
    content: str
    management_system_ids: list[str]
    extra_fields: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SearchModuleConfig:
    table: str
    module: str
    load_all: Callable[[AsyncSession], Awaitable[list[Any]]]
    load_one: Callable[[AsyncSession, str], Awaitable[Any | None]]
    build_document: Callable[[AsyncSession, Any], Awaitable[SearchDocument | None]]


async def _load_all_assignments(db: AsyncSession) -> list[Assignment]:
    """
    功能描述：
        加载all作业。

    参数：
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        list[Assignment]: 返回列表形式的结果数据。
    """
    return (await db.execute(select(Assignment))).scalars().all()


async def _load_assignment(db: AsyncSession, source_id: str) -> Assignment | None:
    """
    功能描述：
        加载作业。

    参数：
        db (AsyncSession): 数据库会话，用于执行持久化操作。
        source_id (str): sourceID。

    返回值：
        Assignment | None: 返回处理结果对象；无可用结果时返回 None。
    """
    return (await db.execute(select(Assignment).where(Assignment.id == source_id))).scalars().first()


async def _build_assignment_document(_db: AsyncSession, item: Assignment) -> SearchDocument | None:
    """
    功能描述：
        构建作业document。

    参数：
        _db (AsyncSession): 异步数据库会话对象。
        item (Assignment): 当前处理的实体对象。

    返回值：
        SearchDocument | None: 返回处理结果对象；无可用结果时返回 None。
    """
    if not item.management_system_id:
        return None
    return SearchDocument(
        module="assignment",
        source_id=item.id,
        title=item.title,
        content=f"{item.title} {item.description or ''}",
        management_system_ids=[item.management_system_id],
        extra_fields={"course_id": item.course_id or "", "target_type": "assignment"},
    )


async def _load_all_comments(db: AsyncSession) -> list[Comment]:
    """
    功能描述：
        加载all评论。

    参数：
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        list[Comment]: 返回列表形式的结果数据。
    """
    return (await db.execute(select(Comment))).scalars().all()


async def _load_comment(db: AsyncSession, source_id: str) -> Comment | None:
    """
    功能描述：
        加载评论。

    参数：
        db (AsyncSession): 数据库会话，用于执行持久化操作。
        source_id (str): sourceID。

    返回值：
        Comment | None: 返回处理结果对象；无可用结果时返回 None。
    """
    return (await db.execute(select(Comment).where(Comment.id == source_id))).scalars().first()


async def _resolve_comment_scope(db: AsyncSession, item: Comment) -> tuple[str | None, str | None]:
    """
    功能描述：
        解析评论作用域。

    参数：
        db (AsyncSession): 数据库会话，用于执行持久化操作。
        item (Comment): 当前处理的实体对象。

    返回值：
        tuple[str | None, str | None]: 返回处理结果对象；无可用结果时返回 None。
    """
    if item.target_type == TargetType.ASSIGNMENT:
        assignment = await _load_assignment(db, item.target_id)
        if not assignment:
            return None, None
        return assignment.management_system_id, assignment.course_id
    if item.target_type == TargetType.SUBMISSION:
        submission = (await db.execute(select(Submission).where(Submission.id == item.target_id))).scalars().first()
        if not submission:
            return None, None
        assignment = await _load_assignment(db, submission.assignment_id)
        course_id = assignment.course_id if assignment else None
        return submission.management_system_id, course_id
    return None, None


async def _build_comment_document(db: AsyncSession, item: Comment) -> SearchDocument | None:
    """
    功能描述：
        构建评论document。

    参数：
        db (AsyncSession): 数据库会话，用于执行持久化操作。
        item (Comment): 当前处理的实体对象。

    返回值：
        SearchDocument | None: 返回处理结果对象；无可用结果时返回 None。
    """
    management_system_id, course_id = await _resolve_comment_scope(db, item)
    if not management_system_id:
        return None
    return SearchDocument(
        module="discussion",
        source_id=item.id,
        title=str(item.target_type),
        content=item.content,
        management_system_ids=[management_system_id],
        extra_fields={
            "course_id": course_id or "",
            "target_type": "discussion",
            "comment_target_type": str(item.target_type),
            "target_id": item.target_id,
        },
    )


async def _load_all_hanzi(db: AsyncSession) -> list[Hanzi]:
    """
    功能描述：
        加载all汉字。

    参数：
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        list[Hanzi]: 返回列表形式的结果数据。
    """
    return (await db.execute(select(Hanzi))).scalars().all()


async def _load_hanzi(db: AsyncSession, source_id: str) -> Hanzi | None:
    """
    功能描述：
        加载汉字。

    参数：
        db (AsyncSession): 数据库会话，用于执行持久化操作。
        source_id (str): sourceID。

    返回值：
        Hanzi | None: 返回处理结果对象；无可用结果时返回 None。
    """
    return (await db.execute(select(Hanzi).where(Hanzi.id == source_id))).scalars().first()


async def _build_hanzi_document(_db: AsyncSession, item: Hanzi) -> SearchDocument | None:
    """
    功能描述：
        构建汉字document。

    参数：
        _db (AsyncSession): 异步数据库会话对象。
        item (Hanzi): 当前处理的实体对象。

    返回值：
        SearchDocument | None: 返回处理结果对象；无可用结果时返回 None。
    """
    if not item.management_system_id:
        return None
    return SearchDocument(
        module="hanzi",
        source_id=item.id,
        title=item.character,
        content=f"{item.character} {item.pinyin or ''} {item.comment or ''}",
        management_system_ids=[item.management_system_id],
        extra_fields={"target_type": "hanzi"},
    )


async def _load_all_courses(db: AsyncSession) -> list[Course]:
    """
    功能描述：
        加载all课程。

    参数：
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        list[Course]: 返回列表形式的结果数据。
    """
    return (await db.execute(select(Course))).scalars().all()


async def _load_course(db: AsyncSession, source_id: str) -> Course | None:
    """
    功能描述：
        加载课程。

    参数：
        db (AsyncSession): 数据库会话，用于执行持久化操作。
        source_id (str): sourceID。

    返回值：
        Course | None: 返回处理结果对象；无可用结果时返回 None。
    """
    return (await db.execute(select(Course).where(Course.id == source_id))).scalars().first()


async def _build_course_document(_db: AsyncSession, item: Course) -> SearchDocument | None:
    """
    功能描述：
        构建课程document。

    参数：
        _db (AsyncSession): 异步数据库会话对象。
        item (Course): 当前处理的实体对象。

    返回值：
        SearchDocument | None: 返回处理结果对象；无可用结果时返回 None。
    """
    return SearchDocument(
        module="course",
        source_id=item.id,
        title=item.name,
        content=f"{item.name} {item.code or ''} {item.description or ''}",
        management_system_ids=[item.management_system_id],
        extra_fields={"teaching_class_id": item.teaching_class_id, "target_type": "course"},
    )


async def _load_all_teaching_classes(db: AsyncSession) -> list[TeachingClass]:
    """
    功能描述：
        加载all教学班级。

    参数：
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        list[TeachingClass]: 返回列表形式的结果数据。
    """
    return (await db.execute(select(TeachingClass))).scalars().all()


async def _load_teaching_class(db: AsyncSession, source_id: str) -> TeachingClass | None:
    """
    功能描述：
        加载教学班级。

    参数：
        db (AsyncSession): 数据库会话，用于执行持久化操作。
        source_id (str): sourceID。

    返回值：
        TeachingClass | None: 返回处理结果对象；无可用结果时返回 None。
    """
    return (await db.execute(select(TeachingClass).where(TeachingClass.id == source_id))).scalars().first()


async def _build_teaching_class_document(_db: AsyncSession, item: TeachingClass) -> SearchDocument | None:
    """
    功能描述：
        构建教学班级document。

    参数：
        _db (AsyncSession): 异步数据库会话对象。
        item (TeachingClass): 当前处理的实体对象。

    返回值：
        SearchDocument | None: 返回处理结果对象；无可用结果时返回 None。
    """
    return SearchDocument(
        module="teaching_class",
        source_id=item.id,
        title=item.name,
        content=f"{item.name} {item.description or ''} {item.status}",
        management_system_ids=[item.management_system_id],
        extra_fields={"target_type": "teaching_class"},
    )


async def _load_all_students(db: AsyncSession) -> list[Student]:
    """
    功能描述：
        加载all学生。

    参数：
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        list[Student]: 返回列表形式的结果数据。
    """
    return (await db.execute(select(Student))).scalars().all()


async def _load_student(db: AsyncSession, source_id: str) -> Student | None:
    """
    功能描述：
        加载学生。

    参数：
        db (AsyncSession): 数据库会话，用于执行持久化操作。
        source_id (str): sourceID。

    返回值：
        Student | None: 返回处理结果对象；无可用结果时返回 None。
    """
    return (await db.execute(select(Student).where(Student.id == source_id))).scalars().first()


async def _build_student_document(db: AsyncSession, item: Student) -> SearchDocument | None:
    """
    功能描述：
        构建学生document。

    参数：
        db (AsyncSession): 数据库会话，用于执行持久化操作。
        item (Student): 当前处理的实体对象。

    返回值：
        SearchDocument | None: 返回处理结果对象；无可用结果时返回 None。
    """
    result = await db.execute(
        select(UserManagementSystem.management_system_id).where(UserManagementSystem.user_id == item.user_id)
    )
    management_system_ids = [row[0] for row in result.all() if row[0]]
    if not management_system_ids:
        return None
    return SearchDocument(
        module="student",
        source_id=item.id,
        title=item.name,
        content=f"{item.name} {item.class_name or ''}",
        management_system_ids=management_system_ids,
        extra_fields={"target_type": "student"},
    )


SEARCH_MODULE_REGISTRY: dict[str, SearchModuleConfig] = {
    "assignment": SearchModuleConfig(
        table="assignment",
        module="assignment",
        load_all=_load_all_assignments,
        load_one=_load_assignment,
        build_document=_build_assignment_document,
    ),
    "comment": SearchModuleConfig(
        table="comment",
        module="discussion",
        load_all=_load_all_comments,
        load_one=_load_comment,
        build_document=_build_comment_document,
    ),
    "hanzi": SearchModuleConfig(
        table="hanzi",
        module="hanzi",
        load_all=_load_all_hanzi,
        load_one=_load_hanzi,
        build_document=_build_hanzi_document,
    ),
    "course": SearchModuleConfig(
        table="course",
        module="course",
        load_all=_load_all_courses,
        load_one=_load_course,
        build_document=_build_course_document,
    ),
    "teaching_class": SearchModuleConfig(
        table="teaching_class",
        module="teaching_class",
        load_all=_load_all_teaching_classes,
        load_one=_load_teaching_class,
        build_document=_build_teaching_class_document,
    ),
    "student": SearchModuleConfig(
        table="student",
        module="student",
        load_all=_load_all_students,
        load_one=_load_student,
        build_document=_build_student_document,
    ),
}


def get_configured_search_sync_tables() -> set[str]:
    """
    功能描述：
        按条件获取configured检索同步tables。

    参数：
        无。

    返回值：
        set[str]: 返回查询到的结果对象。
    """
    return {item.strip() for item in settings.SEARCH_SYNC_CANAL_TABLES.split(",") if item.strip()}


def get_enabled_search_module_configs() -> dict[str, SearchModuleConfig]:
    """
    功能描述：
        按条件获取enabled检索moduleconfigs。

    参数：
        无。

    返回值：
        dict[str, SearchModuleConfig]: 返回字典形式的结果数据。
    """
    configured_tables = get_configured_search_sync_tables()
    return {
        table: config
        for table, config in SEARCH_MODULE_REGISTRY.items()
        if table in configured_tables
    }
