from typing import Optional, List
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.teacher import Teacher
from app.schemas.teacher import TeacherCreate, TeacherUpdate


class TeacherRepository:
    def __init__(self, db: AsyncSession):
        """
        功能描述：
            初始化TeacherRepository并准备运行所需的依赖对象。

        参数：
            db (AsyncSession): 数据库会话，用于执行持久化操作。

        返回值：
            None: 无返回值。
        """
        self.db = db

    async def get(self, id: str) -> Optional[Teacher]:
        """
        功能描述：
            获取TeacherRepository。

        参数：
            id (str): 目标记录ID。

        返回值：
            Optional[Teacher]: 返回处理结果对象；无可用结果时返回 None。
        """
        result = await self.db.execute(select(Teacher).where(Teacher.id == id))
        return result.scalars().first()

    async def get_by_user_id(self, user_id: str) -> Optional[Teacher]:
        """
        功能描述：
            按条件获取by用户标识。

        参数：
            user_id (str): 用户ID。

        返回值：
            Optional[Teacher]: 返回查询到的结果对象；未命中时返回 None。
        """
        result = await self.db.execute(select(Teacher).where(Teacher.user_id == user_id))
        return result.scalars().first()

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[Teacher]:
        """
        功能描述：
            按条件获取all。

        参数：
            skip (int): 分页偏移量。
            limit (int): 单次查询的最大返回数量。

        返回值：
            List[Teacher]: 返回查询到的结果对象。
        """
        result = await self.db.execute(select(Teacher).offset(skip).limit(limit))
        return result.scalars().all()

    async def count(self) -> int:
        """
        功能描述：
            统计TeacherRepository。

        参数：
            无。

        返回值：
            int: 返回int类型的处理结果。
        """
        result = await self.db.execute(select(func.count()).select_from(Teacher))
        return result.scalar()

    async def create(self, teacher_in: TeacherCreate) -> Teacher:
        """
        功能描述：
            创建TeacherRepository。

        参数：
            teacher_in (TeacherCreate): 教师输入对象。

        返回值：
            Teacher: 返回Teacher类型的处理结果。
        """
        teacher = Teacher(**teacher_in.model_dump())
        self.db.add(teacher)
        await self.db.commit()
        await self.db.refresh(teacher)
        return teacher

    async def update(self, teacher: Teacher, teacher_in: TeacherUpdate) -> Teacher:
        """
        功能描述：
            更新TeacherRepository。

        参数：
            teacher (Teacher): Teacher 类型的数据。
            teacher_in (TeacherUpdate): 教师输入对象。

        返回值：
            Teacher: 返回Teacher类型的处理结果。
        """
        update_data = teacher_in.model_dump(exclude_unset=True)
        for k, v in update_data.items():
            setattr(teacher, k, v)
        await self.db.commit()
        await self.db.refresh(teacher)
        return teacher

    async def delete(self, teacher: Teacher) -> None:
        """
        功能描述：
            删除TeacherRepository。

        参数：
            teacher (Teacher): Teacher 类型的数据。

        返回值：
            None: 无返回值。
        """
        await self.db.delete(teacher)
        await self.db.commit()
