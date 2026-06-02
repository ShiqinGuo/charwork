from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.student import Student
from app.schemas.student import StudentCreate, StudentUpdate


class StudentRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, id: str) -> Optional[Student]:
        result = await self.db.execute(select(Student).where(Student.id == id))
        return result.scalars().first()

    async def get_by_user_id(self, user_id: str) -> Optional[Student]:
        result = await self.db.execute(select(Student).where(Student.user_id == user_id))
        return result.scalars().first()

    async def get_all(self, skip: int = 0, limit: int = 100) -> list[Student]:
        result = await self.db.execute(select(Student).offset(skip).limit(limit))
        return result.scalars().all()

    async def get_by_ids(self, ids: list[str], skip: int = 0, limit: int = 100) -> list[Student]:
        if not ids:
            return []
        result = await self.db.execute(
            select(Student).where(Student.id.in_(ids)).offset(skip).limit(limit)
        )
        return result.scalars().all()

    async def count(self) -> int:
        """
        功能描述：
            统计StudentRepository。

        参数：
            无。

        返回值：
            int: 返回int类型的处理结果。
        """
        result = await self.db.execute(select(func.count()).select_from(Student))
        return result.scalar()

    async def create(self, student_in: StudentCreate) -> Student:
        """
        功能描述：
            创建StudentRepository。

        参数：
            student_in (StudentCreate): 学生输入对象。

        返回值：
            Student: 返回Student类型的处理结果。
        """
        student = Student(**student_in.model_dump())
        self.db.add(student)
        await self.db.commit()
        await self.db.refresh(student)
        return student

    async def update(self, student: Student, student_in: StudentUpdate) -> Student:
        """
        功能描述：
            更新StudentRepository。

        参数：
            student (Student): Student 类型的数据。
            student_in (StudentUpdate): 学生输入对象。

        返回值：
            Student: 返回Student类型的处理结果。
        """
        update_data = student_in.model_dump(exclude_unset=True)
        for k, v in update_data.items():
            setattr(student, k, v)
        await self.db.commit()
        await self.db.refresh(student)
        return student

    async def delete(self, student: Student) -> None:
        """
        功能描述：
            删除StudentRepository。

        参数：
            student (Student): Student 类型的数据。

        返回值：
            None: 无返回值。
        """
        await self.db.delete(student)
        await self.db.commit()
