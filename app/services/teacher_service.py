"""
为什么这样做：教师服务保持仓储代理形态，确保基础资料维护路径清晰且便于后续叠加业务规则。
特殊逻辑：更新/删除在未命中目标时返回空结果，避免把“资源不存在”误判为系统异常。
"""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.teacher_repo import TeacherRepository
from app.schemas.teacher import TeacherCreate, TeacherUpdate, TeacherResponse


class TeacherService:
    def __init__(self, db: AsyncSession):
        """
        功能描述：
            初始化TeacherService并准备运行所需的依赖对象。

        参数：
            db (AsyncSession): 数据库会话，用于执行持久化操作。

        返回值：
            None: 无返回值。
        """
        self.repo = TeacherRepository(db)

    async def get_teacher(self, id: str) -> Optional[TeacherResponse]:
        """
        功能描述：
            按条件获取教师。

        参数：
            id (str): 目标记录ID。

        返回值：
            Optional[TeacherResponse]: 返回查询到的结果对象；未命中时返回 None。
        """
        teacher = await self.repo.get(id)
        return TeacherResponse.model_validate(teacher) if teacher else None

    async def list_teachers(self, skip: int = 0, limit: int = 20) -> dict:
        """
        功能描述：
            按条件查询教师列表。

        参数：
            skip (int): 分页偏移量。
            limit (int): 单次查询的最大返回数量。

        返回值：
            dict: 返回字典形式的结果数据。
        """
        items = await self.repo.get_all(skip, limit)
        total = await self.repo.count()
        return {
            "total": total,
            "items": [TeacherResponse.model_validate(i) for i in items],
        }

    async def create_teacher(self, teacher_in: TeacherCreate) -> TeacherResponse:
        """
        功能描述：
            创建教师并返回结果。

        参数：
            teacher_in (TeacherCreate): 教师输入对象。

        返回值：
            TeacherResponse: 返回创建后的结果对象。
        """
        teacher = await self.repo.create(teacher_in)
        return TeacherResponse.model_validate(teacher)

    async def update_teacher(self, id: str, teacher_in: TeacherUpdate) -> Optional[TeacherResponse]:
        """
        功能描述：
            更新教师并返回最新结果。

        参数：
            id (str): 目标记录ID。
            teacher_in (TeacherUpdate): 教师输入对象。

        返回值：
            Optional[TeacherResponse]: 返回更新后的结果对象；未命中时返回 None。
        """
        teacher = await self.repo.get(id)
        if not teacher:
            return None
        teacher = await self.repo.update(teacher, teacher_in)
        return TeacherResponse.model_validate(teacher)

    async def delete_teacher(self, id: str) -> bool:
        """
        功能描述：
            删除教师。

        参数：
            id (str): 目标记录ID。

        返回值：
            bool: 返回操作是否成功。
        """
        teacher = await self.repo.get(id)
        if not teacher:
            return False
        await self.repo.delete(teacher)
        return True
