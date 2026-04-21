from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Course
from app.models.teaching_class import TeachingClassMember, TeachingClassMemberStatus
from app.schemas.course import CourseCreate, CourseUpdate


class CourseRepository:
    def __init__(self, db: AsyncSession):
        """
        功能描述：
            初始化CourseRepository并准备运行所需的依赖对象。

        参数：
            db (AsyncSession): 数据库会话，用于执行持久化操作。

        返回值：
            None: 无返回值。
        """
        self.db = db

    async def get(self, id: str) -> Optional[Course]:
        """
        功能描述：
            获取CourseRepository。

        参数：
            id (str): 目标记录ID。
        返回值：
            Optional[Course]: 返回处理结果对象；无可用结果时返回 None。
        """
        result = await self.db.execute(select(Course).where(Course.id == id))
        return result.scalars().first()

    async def list_by_teaching_class(self, teaching_class_id: str) -> list[Course]:
        """
        功能描述：
            按条件查询by教学班级列表。

        参数：
            teaching_class_id (str): 教学班级ID。

        返回值：
            list[Course]: 返回列表形式的结果数据。
        """
        result = await self.db.execute(
            select(Course)
            .where(Course.teaching_class_id == teaching_class_id)
            .order_by(Course.is_default.desc(), Course.created_at.asc())
        )
        return result.scalars().all()

    async def list_ids_for_student(self, student_id: str) -> list[str]:
        """
        功能描述：
            按条件查询标识列表for学生列表。

        参数：
            student_id (str): 学生ID。
        返回值：
            list[str]: 返回列表形式的结果数据。
        """
        result = await self.db.execute(
            select(Course.id)
            .join(TeachingClassMember, TeachingClassMember.teaching_class_id == Course.teaching_class_id)
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
        """
        功能描述：
            按条件获取all。

        参数：
            skip (int): 分页偏移量。
            limit (int): 单次查询的最大返回数量。
            teaching_class_id (Optional[str]): 教学班级ID。
            teacher_id (Optional[str]): 教师ID。
            status (Optional[str]): 状态筛选条件或目标状态。

        返回值：
            list[Course]: 返回列表形式的结果数据。
        """
        query = select(Course)
        if teaching_class_id:
            query = query.where(Course.teaching_class_id == teaching_class_id)
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
        """
        功能描述：
            统计CourseRepository。

        参数：
            teaching_class_id (Optional[str]): 教学班级ID。
            teacher_id (Optional[str]): 教师ID。
            status (Optional[str]): 状态筛选条件或目标状态。

        返回值：
            int: 返回int类型的处理结果。
        """
        query = select(func.count()).select_from(Course)
        if teaching_class_id:
            query = query.where(Course.teaching_class_id == teaching_class_id)
        if teacher_id:
            query = query.where(Course.teacher_id == teacher_id)
        if status:
            query = query.where(Course.status == status)
        result = await self.db.execute(query)
        return int(result.scalar() or 0)

    async def create(self, course_in: CourseCreate, teacher_id: str) -> Course:
        """
        功能描述：
            创建CourseRepository。

        参数：
            course_in (CourseCreate): 课程输入对象。
            teacher_id (str): 教师ID。
        返回值：
            Course: 返回Course类型的处理结果。
        """
        payload = course_in.model_dump()
        payload.pop("custom_field_values", None)
        item = Course(**payload, teacher_id=teacher_id)
        self.db.add(item)
        await self.db.commit()
        await self.db.refresh(item)
        return item

    async def update(self, course: Course, course_in: CourseUpdate) -> Course:
        """
        功能描述：
            更新CourseRepository。

        参数：
            course (Course): Course 类型的数据。
            course_in (CourseUpdate): 课程输入对象。

        返回值：
            Course: 返回Course类型的处理结果。
        """
        update_data = course_in.model_dump(exclude_unset=True)
        update_data.pop("custom_field_values", None)
        for key, value in update_data.items():
            setattr(course, key, value)
        await self.db.commit()
        await self.db.refresh(course)
        return course

    async def add(self, course: Course) -> Course:
        """
        功能描述：
            新增CourseRepository。

        参数：
            course (Course): Course 类型的数据。

        返回值：
            Course: 返回Course类型的处理结果。
        """
        self.db.add(course)
        await self.db.flush()
        return course

    async def save(self) -> None:
        """
        功能描述：
            保存CourseRepository。

        参数：
            无。

        返回值：
            None: 无返回值。
        """
        await self.db.commit()

    async def refresh(self, course: Course) -> None:
        """
        功能描述：
            刷新CourseRepository。

        参数：
            course (Course): Course 类型的数据。

        返回值：
            None: 无返回值。
        """
        await self.db.refresh(course)
