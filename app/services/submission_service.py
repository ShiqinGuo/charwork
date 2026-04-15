"""
为什么这样做：提交服务采用 outbox + 异步任务解耦通知发送，避免主事务被外部通道稳定性拖慢。
特殊逻辑：评分消息在写入前补查学生与作业，缺失时静默返回，保证边界数据下主流程可完成。
"""

from datetime import datetime
import json
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assignment import Assignment
from app.models.message import Message
from app.models.student import Student
from app.repositories.event_outbox_repo import EventOutboxRepository
from app.repositories.submission_repo import SubmissionRepository
from app.schemas.submission import SubmissionCreate, SubmissionGrade, SubmissionListResponse, SubmissionResponse
from app.tasks.notification_tasks import send_grade_notification, send_submission_notification, publish_outbox_events
from app.tasks.ai_feedback_tasks import generate_ai_feedback
from app.utils.pagination import build_paged_response


class SubmissionService:
    def __init__(self, db: AsyncSession):
        """
        功能描述：
            初始化SubmissionService并准备运行所需的依赖对象。

        参数：
            db (AsyncSession): 数据库会话，用于执行持久化操作。

        返回值：
            None: 无返回值。
        """
        self.repo = SubmissionRepository(db)
        self.outbox_repo = EventOutboxRepository(db)

    async def get_submission(self, id: str, management_system_id: str) -> Optional[SubmissionResponse]:
        """
        功能描述：
            按条件获取提交记录。

        参数：
            id (str): 目标记录ID。
            management_system_id (str): 管理系统ID，用于限制数据作用域。

        返回值：
            Optional[SubmissionResponse]: 返回查询到的结果对象；未命中时返回 None。
        """
        submission = await self.repo.get(id, management_system_id)
        return SubmissionResponse.model_validate(submission) if submission else None

    async def list_submissions_by_assignment(
        self,
        assignment_id: str,
        management_system_id: str,
        student_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
        page: Optional[int] = None,
        size: Optional[int] = None,
    ) -> SubmissionListResponse:
        """
        功能描述：
            按条件查询提交记录by作业列表。

        参数：
            assignment_id (str): 作业ID。
            management_system_id (str): 管理系统ID，用于限制数据作用域。
            student_id (Optional[str]): 学生ID。
            skip (int): 分页偏移量。
            limit (int): 单次查询的最大返回数量。
            page (Optional[int]): 当前页码。
            size (Optional[int]): 每页条数。

        返回值：
            SubmissionListResponse: 返回列表或分页查询结果。
        """
        items = await self.repo.get_all_by_assignment(assignment_id, skip, limit, management_system_id, student_id)
        total = await self.repo.count_by_assignment(assignment_id, management_system_id, student_id)
        payload = build_paged_response(
            items=[SubmissionResponse.model_validate(i) for i in items],
            total=total,
            pagination={"page": page, "size": size, "skip": skip, "limit": limit},
        )
        return SubmissionListResponse(**payload)

    async def create_submission(
        self,
        assignment_id: str,
        submission_in: SubmissionCreate,
        management_system_id: str,
    ) -> SubmissionResponse:
        """
        功能描述：
            创建提交记录并返回结果。

        参数：
            assignment_id (str): 作业ID。
            submission_in (SubmissionCreate): 提交记录输入对象。
            management_system_id (str): 管理系统ID，用于限制数据作用域。

        返回值：
            SubmissionResponse: 返回创建后的结果对象。
        """
        submission = self.repo.build_submission(assignment_id, submission_in, management_system_id)
        self.repo.db.add(submission)
        await self.repo.db.flush()
        payload = json.dumps(
            {
                "submission_id": submission.id,
                "assignment_id": assignment_id,
                "student_id": submission_in.student_id,
            },
            ensure_ascii=False,
        )
        await self.outbox_repo.add_event(
            aggregate_type="submission",
            aggregate_id=submission.id,
            event_type="submission.created",
            payload=payload,
        )
        await self.repo.commit()
        await self.repo.refresh(submission)
        send_submission_notification.delay(submission.id)
        generate_ai_feedback.delay(submission.id)
        publish_outbox_events.delay()
        return SubmissionResponse.model_validate(submission)

    async def grade_submission(
        self,
        id: str,
        body: SubmissionGrade,
        management_system_id: str,
        sender_user_id: str,
    ) -> Optional[SubmissionResponse]:
        """
        功能描述：
            处理提交记录。

        参数：
            id (str): 目标记录ID。
            body (SubmissionGrade): 接口请求体对象。
            management_system_id (str): 管理系统ID，用于限制数据作用域。
            sender_user_id (str): 发送者用户ID。

        返回值：
            Optional[SubmissionResponse]: 返回处理结果对象；无可用结果时返回 None。
        """
        submission = await self.repo.get(id, management_system_id)
        if not submission:
            return None
        update_data = {
            "score": body.score,
            "teacher_feedback": body.feedback,
            "status": "graded",
            "graded_at": datetime.now(),
        }
        submission = await self.repo.update(submission, update_data)
        await self._write_grade_result_message(
            submission.assignment_id,
            submission.student_id,
            sender_user_id,
            body,
            management_system_id,
        )
        send_grade_notification.delay(submission.id)
        return SubmissionResponse.model_validate(submission)

    async def _write_grade_result_message(
        self,
        assignment_id: str,
        student_id: str,
        sender_user_id: str,
        body: SubmissionGrade,
        management_system_id: str,
    ) -> None:
        """
        功能描述：
            写入评分结果消息。

        参数：
            assignment_id (str): 作业ID。
            student_id (str): 学生ID。
            sender_user_id (str): 发送者用户ID。
            body (SubmissionGrade): 接口请求体对象。
            management_system_id (str): 管理系统ID，用于限制数据作用域。

        返回值：
            None: 无返回值。
        """
        student_result = await self.repo.db.execute(select(Student).where(Student.id == student_id))
        student = student_result.scalars().first()
        if not student:
            return
        assignment_result = await self.repo.db.execute(
            select(Assignment).where(
                Assignment.id == assignment_id,
                Assignment.management_system_id == management_system_id,
            )
        )
        assignment = assignment_result.scalars().first()
        assignment_title = assignment.title if assignment else "当前作业"
        feedback_text = body.feedback.strip() if body.feedback else "暂无评语"
        self.repo.db.add(
            Message(
                sender_id=sender_user_id,
                receiver_id=student.user_id,
                management_system_id=management_system_id,
                title="作业批改结果",
                content=f"《{assignment_title}》已完成批改，得分 {body.score} 分。评语：{feedback_text}",
            )
        )
        await self.repo.commit()

    async def get_ai_feedback(self, id: str, management_system_id: str) -> Optional[dict]:
        """
        功能描述：
            获取 AI 生成的评语数据。

        参数：
            id (str): 目标记录ID。
            management_system_id (str): 管理系统ID，用于限制数据作用域。

        返回值：
            Optional[dict]: 返回 ai_feedback 字典；提交不存在时返回 None。
        """
        submission = await self.repo.get(id, management_system_id)
        if not submission:
            return None
        return submission.ai_feedback

    async def save_teacher_feedback(
        self,
        id: str,
        teacher_feedback: Optional[str],
        score: int,
        management_system_id: str,
    ) -> Optional[SubmissionResponse]:
        """
        功能描述：
            保存教师独立评语，不覆盖 ai_feedback。

        参数：
            id (str): 目标记录ID。
            teacher_feedback (Optional[str]): 教师评语文本。
            score (int): 教师打分。
            management_system_id (str): 管理系统ID，用于限制数据作用域。

        返回值：
            Optional[SubmissionResponse]: 返回更新后的结果对象；不存在时返回 None。
        """
        submission = await self.repo.get(id, management_system_id)
        if not submission:
            return None
        # graded_at 只在首次批改时写入，避免教师多次修改评语时时间戳被刷新
        update_payload: dict = {
            "teacher_feedback": teacher_feedback,
            "score": score,
            "status": "graded",
        }
        if not submission.graded_at:
            update_payload["graded_at"] = datetime.now()
        updated = await self.repo.update(submission, update_payload)
        return SubmissionResponse.model_validate(updated)
