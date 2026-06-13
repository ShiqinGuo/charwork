from typing import Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.course import Course, CourseTeachingClass
from app.models.teaching_class import TeachingClassMember, TeachingClassMemberStatus
from app.schemas.course import CourseCreate, CourseUpdate

JUNCTION_COLS = [CourseTeachingClass.course_id, CourseTeachingClass.teaching_class_id]


class CourseRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, id: str) -> Optional[Course]:
        result = await self.db.execute(
            select(Course)
            .where(Course.id == id)
            .options(selectinload(Course.class_links))
        )
        return result.scalars().first()

    async def list_by_teaching_class(self, teaching_class_id: str) -> list[Course]:
        result = await self.db.execute(
            select(Course)
            .join(CourseTeachingClass, CourseTeachingClass.course_id == Course.id)
            .where(CourseTeachingClass.teaching_class_id == teaching_class_id)
            .order_by(Course.is_default.desc(), Course.created_at.asc())
        )
        return result.scalars().all()

    async def list_ids_for_student(self, student_id: str) -> list[str]:
        result = await self.db.execute(
            select(Course.id)
            .join(CourseTeachingClass, CourseTeachingClass.course_id == Course.id)
            .join(TeachingClassMember, TeachingClassMember.teaching_class_id == CourseTeachingClass.teaching_class_id)
            .where(
                TeachingClassMember.student_id == student_id,
                TeachingClassMember.status == TeachingClassMemberStatus.ACTIVE,
            )
            .distinct()
        )
        return [row[0] for row in result.all()]

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 20,
        teaching_class_id: Optional[str] = None,
        teacher_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[Course]:
        query = select(Course).options(selectinload(Course.class_links))
        if teaching_class_id:
            query = (
                query.join(CourseTeachingClass, CourseTeachingClass.course_id == Course.id)
                .where(CourseTeachingClass.teaching_class_id == teaching_class_id)
            )
        if teacher_id:
            query = query.where(Course.teacher_id == teacher_id)
        if status:
            query = query.where(Course.status == status)
        result = await self.db.execute(
            query.order_by(Course.is_default.desc(), Course.updated_at.desc()).offset(skip).limit(limit)
        )
        return result.scalars().all()

    async def count(
        self,
        teaching_class_id: Optional[str] = None,
        teacher_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> int:
        query = select(func.count()).select_from(Course)
        if teaching_class_id:
            query = (
                query.join(CourseTeachingClass, CourseTeachingClass.course_id == Course.id)
                .where(CourseTeachingClass.teaching_class_id == teaching_class_id)
            )
        if teacher_id:
            query = query.where(Course.teacher_id == teacher_id)
        if status:
            query = query.where(Course.status == status)
        result = await self.db.execute(query)
        return int(result.scalar() or 0)

    async def create(
        self, course_in: CourseCreate, teacher_id: str, teaching_class_ids: list[str]
    ) -> Course:
        payload = course_in.model_dump()
        payload.pop("custom_field_values", None)
        payload.pop("teaching_class_ids", None)
        first_class_id = teaching_class_ids[0] if teaching_class_ids else None
        item = Course(**payload, teacher_id=teacher_id, teaching_class_id=first_class_id)
        self.db.add(item)
        await self.db.flush()
        if teaching_class_ids:
            links = [
                CourseTeachingClass(
                    course_id=item.id,
                    teaching_class_id=tcid,
                )
                for tcid in teaching_class_ids
            ]
            self.db.add_all(links)
        await self.db.commit()
        await self.db.refresh(item)
        return item

    async def set_teaching_classes(self, course_id: str, teaching_class_ids: list[str]) -> None:
        await self.db.execute(
            delete(CourseTeachingClass).where(CourseTeachingClass.course_id == course_id)
        )
        if teaching_class_ids:
            links = [
                CourseTeachingClass(course_id=course_id, teaching_class_id=tcid)
                for tcid in teaching_class_ids
            ]
            self.db.add_all(links)

    async def update(self, course: Course, course_in: CourseUpdate) -> Course:
        update_data = course_in.model_dump(exclude_unset=True)
        update_data.pop("custom_field_values", None)
        update_data.pop("teaching_class_ids", None)
        for key, value in update_data.items():
            setattr(course, key, value)
        await self.db.commit()
        await self.db.refresh(course)
        return course

    async def add(self, course: Course) -> Course:
        self.db.add(course)
        await self.db.flush()
        return course

    async def save(self) -> None:
        await self.db.commit()

    async def refresh(self, course: Course) -> None:
        await self.db.refresh(course)
