from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.teaching_class import (
    TeachingClass,
    TeachingClassJoinToken,
    TeachingClassMember,
    TeachingClassMemberStatus,
)


class TeachingClassRepository:
    def __init__(self, db: AsyncSession):
        """
        功能描述：
            初始化TeachingClassRepository并准备运行所需的依赖对象。

        参数：
            db (AsyncSession): 数据库会话，用于执行持久化操作。

        返回值：
            None: 无返回值。
        """
        self.db = db

    async def get(self, id: str, management_system_id: Optional[str] = None) -> Optional[TeachingClass]:
        """
        功能描述：
            获取TeachingClassRepository。

        参数：
            id (str): 目标记录ID。
            management_system_id (Optional[str]): 管理系统ID，用于限制数据作用域。

        返回值：
            Optional[TeachingClass]: 返回处理结果对象；无可用结果时返回 None。
        """
        query = (
            select(TeachingClass)
            .where(TeachingClass.id == id)
            .options(selectinload(TeachingClass.members))
        )
        if management_system_id:
            query = query.where(TeachingClass.management_system_id == management_system_id)
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_default(self, management_system_id: str) -> Optional[TeachingClass]:
        """
        功能描述：
            按条件获取默认。

        参数：
            management_system_id (str): 管理系统ID，用于限制数据作用域。

        返回值：
            Optional[TeachingClass]: 返回查询到的结果对象；未命中时返回 None。
        """
        result = await self.db.execute(
            select(TeachingClass)
            .where(
                TeachingClass.management_system_id == management_system_id,
                TeachingClass.is_default.is_(True),
            )
            .options(selectinload(TeachingClass.members))
        )
        return result.scalars().first()

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 20,
        management_system_id: Optional[str] = None,
        teacher_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[TeachingClass]:
        """
        功能描述：
            按条件获取all。

        参数：
            skip (int): 分页偏移量。
            limit (int): 单次查询的最大返回数量。
            management_system_id (Optional[str]): 管理系统ID，用于限制数据作用域。
            teacher_id (Optional[str]): 教师ID。
            status (Optional[str]): 状态筛选条件或目标状态。

        返回值：
            list[TeachingClass]: 返回列表形式的结果数据。
        """
        query = select(TeachingClass).options(selectinload(TeachingClass.members))
        if management_system_id:
            query = query.where(TeachingClass.management_system_id == management_system_id)
        if teacher_id:
            query = query.where(TeachingClass.teacher_id == teacher_id)
        if status:
            query = query.where(TeachingClass.status == status)
        result = await self.db.execute(
            query.order_by(TeachingClass.is_default.desc(), TeachingClass.updated_at.desc()).offset(skip).limit(limit)
        )
        return result.scalars().all()

    async def count(
        self,
        management_system_id: Optional[str] = None,
        teacher_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> int:
        """
        功能描述：
            统计TeachingClassRepository。

        参数：
            management_system_id (Optional[str]): 管理系统ID，用于限制数据作用域。
            teacher_id (Optional[str]): 教师ID。
            status (Optional[str]): 状态筛选条件或目标状态。

        返回值：
            int: 返回int类型的处理结果。
        """
        query = select(func.count()).select_from(TeachingClass)
        if management_system_id:
            query = query.where(TeachingClass.management_system_id == management_system_id)
        if teacher_id:
            query = query.where(TeachingClass.teacher_id == teacher_id)
        if status:
            query = query.where(TeachingClass.status == status)
        result = await self.db.execute(query)
        return int(result.scalar() or 0)

    async def list_ids_for_student(self, student_id: str, management_system_id: str) -> list[str]:
        """
        功能描述：
            按条件查询标识列表for学生列表。

        参数：
            student_id (str): 学生ID。
            management_system_id (str): 管理系统ID，用于限制数据作用域。

        返回值：
            list[str]: 返回列表形式的结果数据。
        """
        result = await self.db.execute(
            select(TeachingClass.id)
            .join(TeachingClassMember, TeachingClassMember.teaching_class_id == TeachingClass.id)
            .where(
                TeachingClass.management_system_id == management_system_id,
                TeachingClassMember.student_id == student_id,
                TeachingClassMember.status == TeachingClassMemberStatus.ACTIVE,
            )
            .distinct()
        )
        return [row[0] for row in result.all()]

    async def create(self, item: TeachingClass) -> TeachingClass:
        """
        功能描述：
            创建TeachingClassRepository。

        参数：
            item (TeachingClass): 当前处理的实体对象。

        返回值：
            TeachingClass: 返回TeachingClass类型的处理结果。
        """
        self.db.add(item)
        await self.db.commit()
        await self.db.refresh(item)
        return item

    async def add(self, item) -> None:
        """
        功能描述：
            新增TeachingClassRepository。

        参数：
            item (Any): 当前处理的实体对象。

        返回值：
            None: 无返回值。
        """
        self.db.add(item)
        await self.db.flush()

    async def list_members(self, teaching_class_id: str) -> list[TeachingClassMember]:
        """
        功能描述：
            按条件查询members列表。

        参数：
            teaching_class_id (str): 教学班级ID。

        返回值：
            list[TeachingClassMember]: 返回列表形式的结果数据。
        """
        result = await self.db.execute(
            select(TeachingClassMember)
            .where(TeachingClassMember.teaching_class_id == teaching_class_id)
            .options(selectinload(TeachingClassMember.student))
            .order_by(TeachingClassMember.joined_at.asc())
        )
        return result.scalars().all()

    async def count_members(self, teaching_class_id: str) -> int:
        """
        功能描述：
            统计members数量。

        参数：
            teaching_class_id (str): 教学班级ID。

        返回值：
            int: 返回统计结果。
        """
        result = await self.db.execute(
            select(func.count()).select_from(TeachingClassMember).where(
                TeachingClassMember.teaching_class_id == teaching_class_id
            )
        )
        return int(result.scalar() or 0)

    async def get_member(self, teaching_class_id: str, student_id: str) -> Optional[TeachingClassMember]:
        """
        功能描述：
            按条件获取member。

        参数：
            teaching_class_id (str): 教学班级ID。
            student_id (str): 学生ID。

        返回值：
            Optional[TeachingClassMember]: 返回查询到的结果对象；未命中时返回 None。
        """
        result = await self.db.execute(
            select(TeachingClassMember)
            .where(
                TeachingClassMember.teaching_class_id == teaching_class_id,
                TeachingClassMember.student_id == student_id,
            )
            .options(selectinload(TeachingClassMember.student))
        )
        return result.scalars().first()

    async def get_join_token_by_value(self, token: str) -> Optional[TeachingClassJoinToken]:
        """
        功能描述：
            按条件获取加入令牌by值。

        参数：
            token (str): 令牌字符串。

        返回值：
            Optional[TeachingClassJoinToken]: 返回查询到的结果对象；未命中时返回 None。
        """
        result = await self.db.execute(
            select(TeachingClassJoinToken)
            .where(TeachingClassJoinToken.token == token)
            .options(selectinload(TeachingClassJoinToken.teaching_class))
        )
        return result.scalars().first()

    async def save(self) -> None:
        """
        功能描述：
            保存TeachingClassRepository。

        参数：
            无。

        返回值：
            None: 无返回值。
        """
        await self.db.commit()

    async def refresh(self, item) -> None:
        """
        功能描述：
            刷新TeachingClassRepository。

        参数：
            item (Any): 当前处理的实体对象。

        返回值：
            None: 无返回值。
        """
        await self.db.refresh(item)
