from typing import Optional, List
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

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

    async def get(self, id: str) -> Optional[Submission]:
        """
        功能描述：
            获取SubmissionRepository。

        参数：
            id (str): 目标记录ID。
        返回值：
            Optional[Submission]: 返回处理结果对象；无可用结果时返回 None。
        """
        query = select(Submission).where(Submission.id == id).options(joinedload(Submission.attachments))
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_all_by_assignment(
        self,
        assignment_id: str,
        skip: int = 0,
        limit: int = 100,
        student_id: Optional[str] = None,
    ) -> List[Submission]:
        """
        功能描述：
            按条件获取allby作业。

        参数：
            assignment_id (str): 作业ID。
            skip (int): 分页偏移量。
            limit (int): 单次查询的最大返回数量。
            student_id (Optional[str]): 学生ID。

        返回值：
            List[Submission]: 返回查询到的结果对象。
        """
        query = select(Submission).where(Submission.assignment_id == assignment_id)
        if student_id:
            query = query.where(Submission.student_id == student_id)
        query = query.options(joinedload(Submission.attachments))
        result = await self.db.execute(
            query.order_by(desc(Submission.submitted_at)).offset(skip).limit(limit)
        )
        return result.scalars().unique().all()

    async def count_by_assignment(
        self,
        assignment_id: str,
        student_id: Optional[str] = None,
    ) -> int:
        """
        功能描述：
            统计by作业数量。

        参数：
            assignment_id (str): 作业ID。
            student_id (Optional[str]): 学生ID。

        返回值：
            int: 返回统计结果。
        """
        query = select(func.count()).select_from(Submission).where(Submission.assignment_id == assignment_id)
        if student_id:
            query = query.where(Submission.student_id == student_id)
        result = await self.db.execute(
            query
        )
        return result.scalar()

    async def get_latest_by_assignment_student(
        self,
        assignment_id: str,
        student_id: str,
    ) -> Optional[Submission]:
        """
        功能描述：
            获取学生在指定作业下的最新提交记录。

        参数：
            assignment_id (str): 作业ID。
            student_id (str): 学生ID。
        返回值：
            Optional[Submission]: 返回最新提交记录；未命中时返回 None。
        """
        query = select(Submission).where(
            Submission.assignment_id == assignment_id,
            Submission.student_id == student_id,
        ).options(joinedload(Submission.attachments))
        result = await self.db.execute(
            query.order_by(desc(Submission.submitted_at), desc(Submission.id)).limit(1)
        )
        return result.scalars().first()

    async def create(self, assignment_id: str, submission_in: SubmissionCreate) -> Submission:
        """
        功能描述：
            创建SubmissionRepository。

        参数：
            assignment_id (str): 作业ID。
            submission_in (SubmissionCreate): 提交记录输入对象。
        返回值：
            Submission: 返回Submission类型的处理结果。
        """
        submission = self.build_submission(assignment_id, submission_in)
        self.db.add(submission)
        await self.db.commit()
        await self.db.refresh(submission)
        return submission

    def build_submission(self, assignment_id: str, submission_in: SubmissionCreate) -> Submission:
        """
        功能描述：
            构建提交记录。

        参数：
            assignment_id (str): 作业ID。
            submission_in (SubmissionCreate): 提交记录输入对象。
        返回值：
            Submission: 返回构建后的结果对象。
        """
        submission = Submission(
            assignment_id=assignment_id,
            student_id=submission_in.student_id,
            content=submission_in.content,
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

    async def get_all_by_teacher(
        self,
        teacher_id: str,
        skip: int = 0,
        limit: int = 20,
        status: Optional[str] = None,
        assignment_id: Optional[str] = None,
    ) -> List[Submission]:
        """
        功能描述：
            获取教师所有提交记录。

        参数：
            teacher_id (str): 教师ID。
            skip (int): 分页偏移量。
            limit (int): 单次查询的最大返回数量。
            status (Optional[str]): 提交状态筛选。
            assignment_id (Optional[str]): 作业ID筛选。

        返回值：
            List[Submission]: 返回查询到的结果对象。
        """
        from app.models.assignment import Assignment

        query = (
            select(Submission)
            .join(Assignment, Submission.assignment_id == Assignment.id)
            .where(Assignment.teacher_id == teacher_id)
            .options(
                joinedload(Submission.student),
                joinedload(Submission.assignment),
                joinedload(Submission.attachments),
            )
        )
        if status:
            query = query.where(Submission.status == status)
        if assignment_id:
            query = query.where(Submission.assignment_id == assignment_id)
        result = await self.db.execute(
            query.order_by(desc(Submission.submitted_at)).offset(skip).limit(limit)
        )
        return result.scalars().unique().all()

    async def count_by_teacher(
        self,
        teacher_id: str,
        status: Optional[str] = None,
        assignment_id: Optional[str] = None,
    ) -> int:
        """
        功能描述：
            统计教师提交数量。

        参数：
            teacher_id (str): 教师ID。
            status (Optional[str]): 提交状态筛选。
            assignment_id (Optional[str]): 作业ID筛选。

        返回值：
            int: 返回统计结果。
        """
        from app.models.assignment import Assignment

        query = (
            select(func.count())
            .select_from(Submission)
            .join(Assignment, Submission.assignment_id == Assignment.id)
            .where(Assignment.teacher_id == teacher_id)
        )
        if status:
            query = query.where(Submission.status == status)
        if assignment_id:
            query = query.where(Submission.assignment_id == assignment_id)
        result = await self.db.execute(query)
        return result.scalar()
