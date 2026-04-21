from typing import Optional
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.student_class import StudentClass
from app.models.teaching_class import TeachingClass
from app.models.teacher import Teacher
from app.models.student import Student


class StudentClassRepository:
    def __init__(self, db: AsyncSession):
        """
        功能描述：
            初始化StudentClassRepository并准备运行所需的依赖对象。

        参数：
            db (AsyncSession): 数据库会话，用于执行持久化操作。

        返回值：
            None: 无返回值。
        """
        self.db = db

    async def get(self, id: str) -> Optional[StudentClass]:
        """
        功能描述：
            按ID获取学生班级关系。

        参数：
            id (str): 目标记录ID。

        返回值：
            Optional[StudentClass]: 返回处理结果对象；无可用结果时返回 None。
        """
        result = await self.db.execute(select(StudentClass).where(StudentClass.id == id))
        return result.scalars().first()

    async def get_by_student_and_class(
        self, student_id: str, teaching_class_id: str
    ) -> Optional[StudentClass]:
        """
        功能描述：
            按学生和班级ID获取学生班级关系。

        参数：
            student_id (str): 学生ID。
            teaching_class_id (str): 班级ID。

        返回值：
            Optional[StudentClass]: 返回查询到的结果对象；未命中时返回 None。
        """
        result = await self.db.execute(
            select(StudentClass).where(
                and_(
                    StudentClass.student_id == student_id,
                    StudentClass.teaching_class_id == teaching_class_id,
                )
            )
        )
        return result.scalars().first()

    async def list_by_student(
        self, student_id: str, skip: int = 0, limit: int = 20
    ) -> tuple[list[StudentClass], int]:
        """
        功能描述：
            获取学生加入的所有班级，返回列表和总数。

        参数：
            student_id (str): 学生ID。
            skip (int): 分页偏移量。
            limit (int): 单次查询的最大返回数量。

        返回值：
            tuple[list[StudentClass], int]: 返回查询到的结果对象列表和总数。
        """
        # 获取总数
        count_result = await self.db.execute(
            select(func.count()).select_from(StudentClass).where(StudentClass.student_id == student_id)
        )
        total = int(count_result.scalar() or 0)

        # 获取分页数据，预加载关联的班级和教师信息
        result = await self.db.execute(
            select(StudentClass)
            .options(
                joinedload(StudentClass.teaching_class)
                .joinedload(TeachingClass.teacher)
            )
            .where(StudentClass.student_id == student_id)
            .order_by(StudentClass.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        items = result.scalars().all()

        # 为每个班级计算学生人数
        for item in items:
            if item.teaching_class:
                # 查询班级学生人数
                count_query = select(func.count()).select_from(StudentClass).where(
                    StudentClass.teaching_class_id == item.teaching_class_id
                )
                count_result = await self.db.execute(count_query)
                item.teaching_class.student_count = count_result.scalar() or 0

        return items, total

    async def create(self, student_id: str, teaching_class_id: str) -> StudentClass:
        """
        功能描述：
            创建新的学生班级关系。

        参数：
            student_id (str): 学生ID。
            teaching_class_id (str): 班级ID。

        返回值：
            StudentClass: 返回StudentClass类型的处理结果。
        """
        student_class = StudentClass(student_id=student_id, teaching_class_id=teaching_class_id)
        self.db.add(student_class)
        await self.db.commit()
        await self.db.refresh(student_class)
        return student_class

    async def update(self, id: str, status: str) -> Optional[StudentClass]:
        """
        功能描述：
            更新学生班级关系的状态。

        参数：
            id (str): 学生班级关系ID。
            status (str): 新的状态值。

        返回值：
            Optional[StudentClass]: 返回更新后的StudentClass对象；未找到时返回 None。
        """
        student_class = await self.get(id)
        if not student_class:
            return None
        student_class.status = status
        await self.db.commit()
        await self.db.refresh(student_class)
        return student_class

    async def delete(self, id: str) -> bool:
        """
        功能描述：
            删除学生班级关系。

        参数：
            id (str): 学生班级关系ID。

        返回值：
            bool: 删除成功返回 True，未找到返回 False。
        """
        student_class = await self.get(id)
        if not student_class:
            return False
        await self.db.delete(student_class)
        await self.db.commit()
        return True

    async def get_class_info_with_teacher(self, student_class_id: str) -> Optional[dict]:
        """
        功能描述：
            获取班级信息及教师信息（用于加入班级响应）。

        参数：
            student_class_id (str): 学生班级关系ID。

        返回值：
            Optional[dict]: 返回包含 student_class、teaching_class、teacher_name 的字典；未找到时返回 None。
        """
        result = await self.db.execute(
            select(StudentClass, TeachingClass, Teacher).where(
                StudentClass.id == student_class_id
            )
            .join(TeachingClass, StudentClass.teaching_class_id == TeachingClass.id)
            .join(Teacher, TeachingClass.teacher_id == Teacher.id)
        )
        row = result.first()
        if not row:
            return None

        student_class, teaching_class, teacher = row
        return {
            "student_class": student_class,
            "teaching_class": teaching_class,
            "teacher_name": teacher.name,
        }

    async def list_class_members(
        self, teaching_class_id: str, skip: int = 0, limit: int = 20
    ) -> tuple[list[dict], int]:
        """
        功能描述：
            获取班级成员列表，返回成员信息和总数。

        参数：
            teaching_class_id (str): 班级ID。
            skip (int): 分页偏移量。
            limit (int): 单次查询的最大返回数量。

        返回值：
            tuple[list[dict], int]: 返回包含成员信息的字典列表和总数。
        """
        # 获取总数
        count_result = await self.db.execute(
            select(func.count()).select_from(StudentClass).where(
                StudentClass.teaching_class_id == teaching_class_id
            )
        )
        total = int(count_result.scalar() or 0)

        # 获取分页数据
        result = await self.db.execute(
            select(Student, StudentClass).where(
                StudentClass.teaching_class_id == teaching_class_id
            )
            .join(Student, StudentClass.student_id == Student.id)
            .order_by(StudentClass.joined_at.asc())
            .offset(skip)
            .limit(limit)
        )
        rows = result.all()

        items = [
            {
                "id": student.id,
                "name": student.name,
                "joined_at": student_class.joined_at,
            }
            for student, student_class in rows
        ]
        return items, total
