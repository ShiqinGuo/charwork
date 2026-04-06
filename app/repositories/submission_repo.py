from typing import Optional, List
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.submission import Submission
from app.schemas.submission import SubmissionCreate


class SubmissionRepository:
    def __init__(self, db: AsyncSession):
        """
        功能描述：
            初始化SubmissionRepository并准备运行所需的依赖对象。

        参数：
            db (AsyncSession): 数据库会话，用于执行持久化操作。

        返回值：
            None: 无返回值。
        """
        self.db = db

    async def get(self, id: str, management_system_id: Optional[str] = None) -> Optional[Submission]:
        """
        功能描述：
            获取SubmissionRepository。

        参数：
            id (str): 目标记录ID。
            management_system_id (Optional[str]): 管理系统ID，用于限制数据作用域。

        返回值：
            Optional[Submission]: 返回处理结果对象；无可用结果时返回 None。
        """
        query = select(Submission).where(Submission.id == id)
        if management_system_id:
            query = query.where(Submission.management_system_id == management_system_id)
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_all_by_assignment(
        self,
        assignment_id: str,
        skip: int = 0,
        limit: int = 100,
        management_system_id: Optional[str] = None,
        student_id: Optional[str] = None,
    ) -> List[Submission]:
        """
        功能描述：
            按条件获取allby作业。

        参数：
            assignment_id (str): 作业ID。
            skip (int): 分页偏移量。
            limit (int): 单次查询的最大返回数量。
            management_system_id (Optional[str]): 管理系统ID，用于限制数据作用域。
            student_id (Optional[str]): 学生ID。

        返回值：
            List[Submission]: 返回查询到的结果对象。
        """
        query = select(Submission).where(Submission.assignment_id == assignment_id)
        if management_system_id:
            query = query.where(Submission.management_system_id == management_system_id)
        if student_id:
            query = query.where(Submission.student_id == student_id)
        result = await self.db.execute(
            query.order_by(desc(Submission.submitted_at)).offset(skip).limit(limit)
        )
        return result.scalars().all()

    async def count_by_assignment(
        self,
        assignment_id: str,
        management_system_id: Optional[str] = None,
        student_id: Optional[str] = None,
    ) -> int:
        """
        功能描述：
            统计by作业数量。

        参数：
            assignment_id (str): 作业ID。
            management_system_id (Optional[str]): 管理系统ID，用于限制数据作用域。
            student_id (Optional[str]): 学生ID。

        返回值：
            int: 返回统计结果。
        """
        query = select(func.count()).select_from(Submission).where(Submission.assignment_id == assignment_id)
        if management_system_id:
            query = query.where(Submission.management_system_id == management_system_id)
        if student_id:
            query = query.where(Submission.student_id == student_id)
        result = await self.db.execute(
            query
        )
        return result.scalar()

    async def create(self, assignment_id: str, submission_in: SubmissionCreate,
                     management_system_id: str) -> Submission:
        """
        功能描述：
            创建SubmissionRepository。

        参数：
            assignment_id (str): 作业ID。
            submission_in (SubmissionCreate): 提交记录输入对象。
            management_system_id (str): 管理系统ID，用于限制数据作用域。

        返回值：
            Submission: 返回Submission类型的处理结果。
        """
        submission = self.build_submission(assignment_id, submission_in, management_system_id)
        self.db.add(submission)
        await self.db.commit()
        await self.db.refresh(submission)
        return submission

    def build_submission(self, assignment_id: str, submission_in: SubmissionCreate,
                         management_system_id: str) -> Submission:
        """
        功能描述：
            构建提交记录。

        参数：
            assignment_id (str): 作业ID。
            submission_in (SubmissionCreate): 提交记录输入对象。
            management_system_id (str): 管理系统ID，用于限制数据作用域。

        返回值：
            Submission: 返回构建后的结果对象。
        """
        submission = Submission(
            assignment_id=assignment_id,
            student_id=submission_in.student_id,
            management_system_id=management_system_id,
            content=submission_in.content,
            image_paths=submission_in.image_paths,
        )
        return submission

    async def update(self, submission: Submission, update_data: dict) -> Submission:
        """
        功能描述：
            更新SubmissionRepository。

        参数：
            submission (Submission): Submission 类型的数据。
            update_data (dict): 字典形式的结果数据。

        返回值：
            Submission: 返回Submission类型的处理结果。
        """
        for k, v in update_data.items():
            setattr(submission, k, v)
        await self.db.commit()
        await self.db.refresh(submission)
        return submission

    async def commit(self) -> None:
        """
        功能描述：
            处理SubmissionRepository。

        参数：
            无。

        返回值：
            None: 无返回值。
        """
        await self.db.commit()

    async def refresh(self, submission: Submission) -> None:
        """
        功能描述：
            刷新SubmissionRepository。

        参数：
            submission (Submission): Submission 类型的数据。

        返回值：
            None: 无返回值。
        """
        await self.db.refresh(submission)
