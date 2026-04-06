"""
为什么这样做：学生服务保持最小职责，仅做仓储调用与响应转换，便于后续按域扩展校验逻辑。
特殊逻辑：更新/删除在对象不存在时直接返回空结果，明确资源边界而不抛异常中断流程。
"""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.student_repo import StudentRepository
from app.schemas.student import StudentCreate, StudentUpdate, StudentResponse


class StudentService:
    def __init__(self, db: AsyncSession):
        """
        功能描述：
            初始化StudentService并准备运行所需的依赖对象。

        参数：
            db (AsyncSession): 数据库会话，用于执行持久化操作。

        返回值：
            None: 无返回值。
        """
        self.repo = StudentRepository(db)

    async def get_student(self, id: str) -> Optional[StudentResponse]:
        """
        功能描述：
            按条件获取学生。

        参数：
            id (str): 目标记录ID。

        返回值：
            Optional[StudentResponse]: 返回查询到的结果对象；未命中时返回 None。
        """
        student = await self.repo.get(id)
        return StudentResponse.model_validate(student) if student else None

    async def list_students(self, skip: int = 0, limit: int = 20) -> dict:
        """
        功能描述：
            按条件查询学生列表。

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
            "items": [StudentResponse.model_validate(i) for i in items],
        }

    async def create_student(self, student_in: StudentCreate) -> StudentResponse:
        """
        功能描述：
            创建学生并返回结果。

        参数：
            student_in (StudentCreate): 学生输入对象。

        返回值：
            StudentResponse: 返回创建后的结果对象。
        """
        student = await self.repo.create(student_in)
        return StudentResponse.model_validate(student)

    async def update_student(self, id: str, student_in: StudentUpdate) -> Optional[StudentResponse]:
        """
        功能描述：
            更新学生并返回最新结果。

        参数：
            id (str): 目标记录ID。
            student_in (StudentUpdate): 学生输入对象。

        返回值：
            Optional[StudentResponse]: 返回更新后的结果对象；未命中时返回 None。
        """
        student = await self.repo.get(id)
        if not student:
            return None
        student = await self.repo.update(student, student_in)
        return StudentResponse.model_validate(student)

    async def delete_student(self, id: str) -> bool:
        """
        功能描述：
            删除学生。

        参数：
            id (str): 目标记录ID。

        返回值：
            bool: 返回操作是否成功。
        """
        student = await self.repo.get(id)
        if not student:
            return False
        await self.repo.delete(student)
        return True
