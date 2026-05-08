"""
为什么这样做：检索注册中心把"表 -> 文档构建器"统一声明，便于增删模块时最小改动接入。
特殊逻辑：索引只存业务归属字段，不再把 management_system 作为通用可见性边界。
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
from app.models.student import Student
from app.models.submission import Submission
from app.models.teacher import Teacher
from app.models.teaching_class import TeachingClass, TeachingClassMember, TeachingClassMemberStatus


@dataclass(frozen=True)
class SearchDocument:
    module: str
    source_id: str
    title: str
    content: str
    extra_fields: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SearchModuleConfig:
    table: str
    module: str
    load_all: Callable[[AsyncSession], Awaitable[list[Any]]]
    load_one: Callable[[AsyncSession, str], Awaitable[Any | None]]
    build_document: Callable[[AsyncSession, Any, dict], Awaitable[SearchDocument | None]]
    preload: Callable[[AsyncSession], Awaitable[dict]] | None = None


# ===== 预加载函数（reindex 时批量加载，消除 N+1） =====

async def _preload_teacher_user_ids(db: AsyncSession) -> dict[str, str]:
    result = await db.execute(select(Teacher.id, Teacher.user_id))
    return {str(row[0]): str(row[1]) for row in result.all() if row[0] and row[1]}


async def _preload_student_teacher_user_ids(db: AsyncSession) -> dict[str, list[str]]:
    result = await db.execute(
        select(TeachingClassMember.student_id, Teacher.user_id)
        .join(TeachingClass, TeachingClassMember.teaching_class_id == TeachingClass.id)
        .join(Teacher, TeachingClass.teacher_id == Teacher.id)
        .where(TeachingClassMember.status == TeachingClassMemberStatus.ACTIVE)
    )
    mapping: dict[str, list[str]] = {}
    for student_id, user_id in result.all():
        mapping.setdefault(str(student_id), []).append(str(user_id))
    return mapping


async def _preload_comment_scope_maps(db: AsyncSession) -> dict[str, Any]:
    teacher_user_ids = await _preload_teacher_user_ids(db)
    assignment_rows = (await db.execute(
        select(Assignment.id, Assignment.teacher_id, Assignment.course_id)
    )).all()
    assignment_map = {
        str(row[0]): {"teacher_id": str(row[1]), "course_id": str(row[2])}
        for row in assignment_rows if row[0]
    }
    submission_rows = (await db.execute(
        select(Submission.id, Submission.assignment_id)
    )).all()
    submission_map = {str(row[0]): str(row[1]) for row in submission_rows if row[0]}
    return {
        "teacher_user_ids": teacher_user_ids,
        "assignment_map": assignment_map,
        "submission_map": submission_map,
    }


async def _preload_teacher_context(db: AsyncSession) -> dict[str, Any]:
    """assignment / course / teaching_class 共享的 teacher 预加载。"""
    return {"teacher_user_ids": await _preload_teacher_user_ids(db)}


async def _preload_student_context(db: AsyncSession) -> dict[str, Any]:
    return {"student_teacher_ids": await _preload_student_teacher_user_ids(db)}


# ===== CDC 单条查询回退（apply_cdc_change 路径使用） =====

async def _get_teacher_user_id_fallback(db: AsyncSession, teacher_id: str | None) -> str | None:
    if not teacher_id:
        return None
    result = await db.execute(select(Teacher.user_id).where(Teacher.id == teacher_id))
    return result.scalar_one_or_none()


async def _resolve_teacher_user_id(
    db: AsyncSession, teacher_id: str | None, context: dict
) -> str | None:
    """从 context 解析 teacher_user_id，context 为空时走 CDC 逐条回退。"""
    if not teacher_id:
        return None
    teacher_user_ids = context.get("teacher_user_ids", {})
    teacher_user_id = teacher_user_ids.get(teacher_id)
    if not teacher_user_id and "teacher_user_ids" not in context:
        teacher_user_id = await _get_teacher_user_id_fallback(db, teacher_id)
    return teacher_user_id


# ===== load 函数 =====

async def _load_all_assignments(db: AsyncSession) -> list[Assignment]:
    return (await db.execute(select(Assignment))).scalars().all()


async def _load_assignment(db: AsyncSession, source_id: str) -> Assignment | None:
    return (await db.execute(select(Assignment).where(Assignment.id == source_id))).scalars().first()


async def _load_all_comments(db: AsyncSession) -> list[Comment]:
    return (await db.execute(select(Comment))).scalars().all()


async def _load_comment(db: AsyncSession, source_id: str) -> Comment | None:
    return (await db.execute(select(Comment).where(Comment.id == source_id))).scalars().first()


async def _load_all_hanzi(db: AsyncSession) -> list[Hanzi]:
    return (await db.execute(select(Hanzi))).scalars().all()


async def _load_hanzi(db: AsyncSession, source_id: str) -> Hanzi | None:
    return (await db.execute(select(Hanzi).where(Hanzi.id == source_id))).scalars().first()


async def _load_all_courses(db: AsyncSession) -> list[Course]:
    return (await db.execute(select(Course))).scalars().all()


async def _load_course(db: AsyncSession, source_id: str) -> Course | None:
    return (await db.execute(select(Course).where(Course.id == source_id))).scalars().first()


async def _load_all_teaching_classes(db: AsyncSession) -> list[TeachingClass]:
    return (await db.execute(select(TeachingClass))).scalars().all()


async def _load_teaching_class(db: AsyncSession, source_id: str) -> TeachingClass | None:
    return (await db.execute(select(TeachingClass).where(TeachingClass.id == source_id))).scalars().first()


async def _load_all_students(db: AsyncSession) -> list[Student]:
    return (await db.execute(select(Student))).scalars().all()


async def _load_student(db: AsyncSession, source_id: str) -> Student | None:
    return (await db.execute(select(Student).where(Student.id == source_id))).scalars().first()


# ===== build_document 函数（使用 context 参数） =====

async def _build_assignment_document(
    db: AsyncSession, item: Assignment, context: dict
) -> SearchDocument | None:
    teacher_user_id = await _resolve_teacher_user_id(db, item.teacher_id, context)
    if not teacher_user_id:
        return None
    return SearchDocument(
        module="assignment",
        source_id=item.id,
        title=item.title,
        content=f"{item.title} {item.description or ''}",
        extra_fields={
            "course_id": item.course_id or "",
            "teacher_user_id": teacher_user_id,
            "target_type": "assignment",
        },
    )


async def _build_comment_document(
    db: AsyncSession, item: Comment, context: dict
) -> SearchDocument | None:
    teacher_user_ids = context.get("teacher_user_ids", {})
    assignment_map = context.get("assignment_map", {})
    submission_map = context.get("submission_map", {})

    teacher_user_id = None
    course_id = None

    if item.target_type == TargetType.ASSIGNMENT:
        assignment_info = assignment_map.get(item.target_id)
        if assignment_info:
            teacher_user_id = teacher_user_ids.get(assignment_info["teacher_id"])
            course_id = assignment_info.get("course_id")
        elif not assignment_map:
            # CDC 回退
            assignment = await _load_assignment(db, item.target_id)
            if assignment:
                teacher_user_id = await _get_teacher_user_id_fallback(db, assignment.teacher_id)
                course_id = assignment.course_id
    elif item.target_type == TargetType.SUBMISSION:
        assignment_id = submission_map.get(item.target_id)
        if assignment_id:
            assignment_info = assignment_map.get(assignment_id)
            if assignment_info:
                teacher_user_id = teacher_user_ids.get(assignment_info["teacher_id"])
                course_id = assignment_info.get("course_id")
        elif not submission_map:
            # CDC 回退
            submission = await (await db.execute(
                select(Submission).where(Submission.id == item.target_id)
            )).scalars().first()
            if submission:
                assignment = await _load_assignment(db, submission.assignment_id)
                if assignment:
                    teacher_user_id = await _get_teacher_user_id_fallback(db, assignment.teacher_id)
                    course_id = assignment.course_id

    if not teacher_user_id:
        return None
    return SearchDocument(
        module="discussion",
        source_id=item.id,
        title=str(item.target_type),
        content=item.content,
        extra_fields={
            "course_id": course_id or "",
            "teacher_user_id": teacher_user_id,
            "target_type": "discussion",
            "comment_target_type": str(item.target_type),
            "target_id": item.target_id,
        },
    )


async def _build_hanzi_document(
    _db: AsyncSession, item: Hanzi, context: dict
) -> SearchDocument | None:
    return SearchDocument(
        module="hanzi",
        source_id=item.id,
        title=item.character,
        content=f"{item.character} {item.pinyin or ''} {item.comment or ''}",
        extra_fields={
            "created_by_user_id": item.created_by_user_id,
            "dictionary_id": item.dictionary_id,
            "target_type": "hanzi",
        },
    )


async def _build_course_document(
    db: AsyncSession, item: Course, context: dict
) -> SearchDocument | None:
    teacher_user_id = await _resolve_teacher_user_id(db, item.teacher_id, context)
    if not teacher_user_id:
        return None
    return SearchDocument(
        module="course",
        source_id=item.id,
        title=item.name,
        content=f"{item.name} {item.code or ''} {item.description or ''}",
        extra_fields={
            "teaching_class_id": item.teaching_class_id,
            "teacher_user_id": teacher_user_id,
            "target_type": "course",
        },
    )


async def _build_teaching_class_document(
    db: AsyncSession, item: TeachingClass, context: dict
) -> SearchDocument | None:
    teacher_user_id = await _resolve_teacher_user_id(db, item.teacher_id, context)
    if not teacher_user_id:
        return None
    return SearchDocument(
        module="teaching_class",
        source_id=item.id,
        title=item.name,
        content=f"{item.name} {item.description or ''} {item.status}",
        extra_fields={
            "teacher_user_id": teacher_user_id,
            "target_type": "teaching_class",
        },
    )


async def _build_student_document(
    db: AsyncSession, item: Student, context: dict
) -> SearchDocument | None:
    student_teacher_ids = context.get("student_teacher_ids", {})
    teacher_user_ids = student_teacher_ids.get(item.id, [])
    if not teacher_user_ids and not student_teacher_ids:
        # CDC 回退
        result = await db.execute(
            select(Teacher.user_id)
            .join(TeachingClass, TeachingClass.teacher_id == Teacher.id)
            .join(TeachingClassMember, TeachingClassMember.teaching_class_id == TeachingClass.id)
            .where(
                TeachingClassMember.student_id == item.id,
                TeachingClassMember.status == TeachingClassMemberStatus.ACTIVE,
            )
            .distinct()
        )
        teacher_user_ids = [row[0] for row in result.all() if row[0]]
    if not teacher_user_ids:
        return None
    return SearchDocument(
        module="student",
        source_id=item.id,
        title=item.name,
        content=f"{item.name} {item.class_name or ''}",
        extra_fields={
            "student_user_id": item.user_id,
            "teacher_user_ids": teacher_user_ids,
            "target_type": "student",
        },
    )


# ===== 注册表 =====

SEARCH_MODULE_REGISTRY: dict[str, SearchModuleConfig] = {
    "assignment": SearchModuleConfig(
        table="assignment",
        module="assignment",
        load_all=_load_all_assignments,
        load_one=_load_assignment,
        build_document=_build_assignment_document,
        preload=_preload_teacher_context,
    ),
    "comment": SearchModuleConfig(
        table="comment",
        module="discussion",
        load_all=_load_all_comments,
        load_one=_load_comment,
        build_document=_build_comment_document,
        preload=_preload_comment_scope_maps,
    ),
    "hanzi": SearchModuleConfig(
        table="hanzi",
        module="hanzi",
        load_all=_load_all_hanzi,
        load_one=_load_hanzi,
        build_document=_build_hanzi_document,
        preload=None,
    ),
    "course": SearchModuleConfig(
        table="course",
        module="course",
        load_all=_load_all_courses,
        load_one=_load_course,
        build_document=_build_course_document,
        preload=_preload_teacher_context,
    ),
    "teaching_class": SearchModuleConfig(
        table="teaching_class",
        module="teaching_class",
        load_all=_load_all_teaching_classes,
        load_one=_load_teaching_class,
        build_document=_build_teaching_class_document,
        preload=_preload_teacher_context,
    ),
    "student": SearchModuleConfig(
        table="student",
        module="student",
        load_all=_load_all_students,
        load_one=_load_student,
        build_document=_build_student_document,
        preload=_preload_student_context,
    ),
}


def get_configured_search_sync_tables() -> set[str]:
    return {item.strip() for item in settings.SEARCH_SYNC_CANAL_TABLES.split(",") if item.strip()}


def get_enabled_search_module_configs() -> dict[str, SearchModuleConfig]:
    configured_tables = get_configured_search_sync_tables()
    return {
        table: config
        for table, config in SEARCH_MODULE_REGISTRY.items()
        if table in configured_tables
    }
