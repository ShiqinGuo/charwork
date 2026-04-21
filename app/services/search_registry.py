"""
为什么这样做：检索注册中心把“表 -> 文档构建器”统一声明，便于增删模块时最小改动接入。
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
    build_document: Callable[[AsyncSession, Any], Awaitable[SearchDocument | None]]


async def _load_teacher_user_id(db: AsyncSession, teacher_id: str | None) -> str | None:
    if not teacher_id:
        return None
    result = await db.execute(select(Teacher.user_id).where(Teacher.id == teacher_id))
    return result.scalar_one_or_none()


async def _load_assignment(db: AsyncSession, source_id: str) -> Assignment | None:
    return (await db.execute(select(Assignment).where(Assignment.id == source_id))).scalars().first()


async def _load_submission(db: AsyncSession, source_id: str) -> Submission | None:
    return (await db.execute(select(Submission).where(Submission.id == source_id))).scalars().first()


async def _resolve_submission_teacher_context(
    db: AsyncSession,
    submission: Submission | None,
) -> tuple[str | None, str | None]:
    if not submission:
        return None, None
    assignment = await _load_assignment(db, submission.assignment_id)
    if not assignment:
        return None, None
    teacher_user_id = await _load_teacher_user_id(db, assignment.teacher_id)
    return teacher_user_id, assignment.course_id


async def _load_all_assignments(db: AsyncSession) -> list[Assignment]:
    return (await db.execute(select(Assignment))).scalars().all()


async def _build_assignment_document(db: AsyncSession, item: Assignment) -> SearchDocument | None:
    teacher_user_id = await _load_teacher_user_id(db, item.teacher_id)
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


async def _load_all_comments(db: AsyncSession) -> list[Comment]:
    return (await db.execute(select(Comment))).scalars().all()


async def _load_comment(db: AsyncSession, source_id: str) -> Comment | None:
    return (await db.execute(select(Comment).where(Comment.id == source_id))).scalars().first()


async def _resolve_comment_scope(db: AsyncSession, item: Comment) -> tuple[str | None, str | None]:
    if item.target_type == TargetType.ASSIGNMENT:
        assignment = await _load_assignment(db, item.target_id)
        if not assignment:
            return None, None
        return await _load_teacher_user_id(db, assignment.teacher_id), assignment.course_id
    if item.target_type == TargetType.SUBMISSION:
        submission = await _load_submission(db, item.target_id)
        return await _resolve_submission_teacher_context(db, submission)
    return None, None


async def _build_comment_document(db: AsyncSession, item: Comment) -> SearchDocument | None:
    teacher_user_id, course_id = await _resolve_comment_scope(db, item)
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


async def _load_all_hanzi(db: AsyncSession) -> list[Hanzi]:
    return (await db.execute(select(Hanzi))).scalars().all()


async def _load_hanzi(db: AsyncSession, source_id: str) -> Hanzi | None:
    return (await db.execute(select(Hanzi).where(Hanzi.id == source_id))).scalars().first()


async def _build_hanzi_document(_db: AsyncSession, item: Hanzi) -> SearchDocument | None:
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


async def _load_all_courses(db: AsyncSession) -> list[Course]:
    return (await db.execute(select(Course))).scalars().all()


async def _load_course(db: AsyncSession, source_id: str) -> Course | None:
    return (await db.execute(select(Course).where(Course.id == source_id))).scalars().first()


async def _build_course_document(db: AsyncSession, item: Course) -> SearchDocument | None:
    teacher_user_id = await _load_teacher_user_id(db, item.teacher_id)
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


async def _load_all_teaching_classes(db: AsyncSession) -> list[TeachingClass]:
    return (await db.execute(select(TeachingClass))).scalars().all()


async def _load_teaching_class(db: AsyncSession, source_id: str) -> TeachingClass | None:
    return (await db.execute(select(TeachingClass).where(TeachingClass.id == source_id))).scalars().first()


async def _build_teaching_class_document(db: AsyncSession, item: TeachingClass) -> SearchDocument | None:
    teacher_user_id = await _load_teacher_user_id(db, item.teacher_id)
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


async def _load_all_students(db: AsyncSession) -> list[Student]:
    return (await db.execute(select(Student))).scalars().all()


async def _load_student(db: AsyncSession, source_id: str) -> Student | None:
    return (await db.execute(select(Student).where(Student.id == source_id))).scalars().first()


async def _load_student_teacher_user_ids(db: AsyncSession, student_id: str) -> list[str]:
    result = await db.execute(
        select(Teacher.user_id)
        .join(TeachingClass, TeachingClass.teacher_id == Teacher.id)
        .join(TeachingClassMember, TeachingClassMember.teaching_class_id == TeachingClass.id)
        .where(
            TeachingClassMember.student_id == student_id,
            TeachingClassMember.status == TeachingClassMemberStatus.ACTIVE,
        )
        .distinct()
    )
    return [row[0] for row in result.all() if row[0]]


async def _build_student_document(db: AsyncSession, item: Student) -> SearchDocument | None:
    teacher_user_ids = await _load_student_teacher_user_ids(db, item.id)
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
    return {item.strip() for item in settings.SEARCH_SYNC_CANAL_TABLES.split(",") if item.strip()}


def get_enabled_search_module_configs() -> dict[str, SearchModuleConfig]:
    configured_tables = get_configured_search_sync_tables()
    return {
        table: config
        for table, config in SEARCH_MODULE_REGISTRY.items()
        if table in configured_tables
    }
