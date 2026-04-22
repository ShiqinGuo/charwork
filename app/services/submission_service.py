"""
为什么这样做：提交服务采用 outbox + 异步任务解耦通知发送，避免主事务被外部通道稳定性拖慢。
特殊逻辑：评分消息在写入前补查学生与作业，缺失时静默返回，保证边界数据下主流程可完成。
"""

from datetime import datetime
import json
from typing import Optional

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_feedback import (
    AIFeedbackGeneratedBy,
    AIFeedbackScope,
    AIFeedbackStatus,
    AIFeedbackTargetType,
    AIFeedbackVisibility,
)
from app.models.assignment import Assignment
from app.models.message import Message
from app.models.student import Student
from app.models.submission import SubmissionStatus
from app.repositories.ai_feedback_repo import AIFeedbackRepository
from app.repositories.attachment_repo import AttachmentRepository
from app.repositories.event_outbox_repo import EventOutboxRepository
from app.repositories.submission_repo import SubmissionRepository
from app.schemas.submission import (
    SubmissionCreate,
    SubmissionGrade,
    SubmissionListResponse,
    SubmissionResponse,
    SubmissionTransitionEvent,
)
from app.services.submission_state_machine import SubmissionStateMachine
from app.tasks.notification_tasks import send_grade_notification, send_submission_notification, publish_outbox_events
from app.tasks.ai_feedback_tasks import generate_ai_feedback, generate_submission_ai_summary
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
        self.state_machine = SubmissionStateMachine()

    async def upload_submission_images(
        self,
        files: list[UploadFile],
    ) -> list[str]:
        """
        功能描述：
            上传作业图片并返回附件ID列表。

        参数：
            files (list[UploadFile]): 学生提交的图片文件列表。
        返回值：
            list[str]: 返回上传成功后的附件ID列表。
        """
        if not files:
            return []

        from app.services.attachment_service import AttachmentService
        attachment_service = AttachmentService(self.repo.db)

        attachment_ids: list[str] = []
        for upload_file in files:
            if not upload_file.filename:
                raise ValueError("上传图片缺少文件名")
            try:
                attachment = await attachment_service.upload_attachment(
                    file=upload_file,
                    owner_type="submission",
                    owner_id="temp",
                )
                attachment_ids.append(attachment.id)
            except Exception as e:
                raise ValueError(f"上传图片失败: {str(e)}")
        return attachment_ids

    async def get_submission(self, id: str) -> Optional[SubmissionResponse]:
        """
        功能描述：
            按条件获取提交记录。

        参数：
            id (str): 目标记录ID。
        返回值：
            Optional[SubmissionResponse]: 返回查询到的结果对象；未命中时返回 None。
        """
        submission = await self.repo.get(id)
        return SubmissionResponse.model_validate(submission) if submission else None

    async def get_latest_submission_for_student(
        self,
        assignment_id: str,
        student_id: str,
    ) -> Optional[SubmissionResponse]:
        """
        功能描述：
            获取学生在指定作业下的最新提交记录。

        参数：
            assignment_id (str): 作业ID。
            student_id (str): 学生ID。
        返回值：
            Optional[SubmissionResponse]: 返回最新提交记录；未命中时返回 None。
        """
        submission = await self.repo.get_latest_by_assignment_student(
            assignment_id=assignment_id,
            student_id=student_id,
        )
        return SubmissionResponse.model_validate(submission) if submission else None

    async def list_submissions_by_assignment(
        self,
        assignment_id: str,
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
            student_id (Optional[str]): 学生ID。
            skip (int): 分页偏移量。
            limit (int): 单次查询的最大返回数量。
            page (Optional[int]): 当前页码。
            size (Optional[int]): 每页条数。

        返回值：
            SubmissionListResponse: 返回列表或分页查询结果。
        """
        items = await self.repo.get_all_by_assignment(assignment_id, skip, limit, student_id)
        total = await self.repo.count_by_assignment(assignment_id, student_id)
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
    ) -> SubmissionResponse:
        """
        功能描述：
            创建提交记录并返回结果。

        参数：
            assignment_id (str): 作业ID。
            submission_in (SubmissionCreate): 提交记录输入对象。
        返回值：
            SubmissionResponse: 返回创建后的结果对象。
        """
        submission = self.repo.build_submission(assignment_id, submission_in)
        self.repo.db.add(submission)
        await self.repo.db.flush()

        # 关联附件
        new_attachment_ids = list(submission_in.attachment_ids or [])
        if new_attachment_ids:
            attachment_repo = AttachmentRepository(self.repo.db)
            for attachment_id in new_attachment_ids:
                attachment = await attachment_repo.get(attachment_id)
                if not attachment:
                    raise ValueError(f"Attachment not found: {attachment_id}")
                attachment.owner_id = submission.id
                self.repo.db.add(attachment)

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
        self._schedule_submission_followups(
            submission.id,
            new_attachment_ids=new_attachment_ids,
            publish_outbox=True,
        )
        # refresh 不 eager load 关系，需重新查询以避免 async lazy load 报错
        reloaded = await self.repo.get(submission.id)
        return SubmissionResponse.model_validate(reloaded)

    async def update_submission(
        self,
        id: str,
        submission_in: SubmissionCreate,
    ) -> Optional[SubmissionResponse]:
        """
        功能描述：
            更新提交记录并重置为重新提交状态。

        参数：
            id (str): 目标记录ID。
            submission_in (SubmissionCreate): 提交记录输入对象。
        返回值：
            Optional[SubmissionResponse]: 返回更新后的结果对象；未命中时返回 None。
        """
        submission = await self.repo.get(id)
        if not submission:
            return None
        transition_result = self.state_machine.transition(
            SubmissionStatus(submission.status),
            SubmissionTransitionEvent.RESUBMIT,
        )
        update_data = self._build_resubmission_payload(
            submission_in=submission_in,
            next_status=transition_result.to_status,
        )

        # 处理附件
        added_attachment_ids: list[str] = []
        if submission_in.attachment_ids:
            attachment_repo = AttachmentRepository(self.repo.db)

            # 获取当前附件
            current_attachments = await attachment_repo.get_by_owner(
                owner_type="submission",
                owner_id=id,
            )
            current_ids = {a.id for a in current_attachments}
            new_ids = set(submission_in.attachment_ids)

            # 删除不在新列表中的附件
            for attachment in current_attachments:
                if attachment.id not in new_ids:
                    await attachment_repo.soft_delete(attachment)

            # 添加新附件
            for attachment_id in new_ids:
                if attachment_id not in current_ids:
                    attachment = await attachment_repo.get(attachment_id)
                    if not attachment:
                        raise ValueError(f"Attachment not found: {attachment_id}")
                    attachment.owner_id = id
                    self.repo.db.add(attachment)
                    added_attachment_ids.append(attachment_id)

        updated_submission = await self.repo.update(submission, update_data)
        self._schedule_submission_followups(
            updated_submission.id,
            new_attachment_ids=added_attachment_ids,
        )
        # refresh 不 eager load 关系，需重新查询以避免 async lazy load 报错
        reloaded = await self.repo.get(updated_submission.id)
        return SubmissionResponse.model_validate(reloaded)

    async def grade_submission(
        self,
        id: str,
        body: SubmissionGrade,
        sender_user_id: str,
    ) -> Optional[SubmissionResponse]:
        """
        功能描述：
            处理提交记录。

        参数：
            id (str): 目标记录ID。
            body (SubmissionGrade): 接口请求体对象。
            sender_user_id (str): 发送者用户ID。

        返回值：
            Optional[SubmissionResponse]: 返回处理结果对象；无可用结果时返回 None。
        """
        submission = await self.repo.get(id)
        if not submission:
            return None
        transition_result = self.state_machine.transition(
            SubmissionStatus(submission.status),
            SubmissionTransitionEvent.GRADE,
        )
        update_data = {
            "score": body.score,
            "teacher_feedback": body.feedback,
            "status": transition_result.to_status,
            "graded_at": datetime.now(),
        }
        submission = await self.repo.update(submission, update_data)
        await self._write_grade_result_message(
            submission.assignment_id,
            submission.student_id,
            sender_user_id,
            body,
        )
        send_grade_notification.delay(submission.id)
        return SubmissionResponse.model_validate(submission)

    async def _write_grade_result_message(
        self,
        assignment_id: str,
        student_id: str,
        sender_user_id: str,
        body: SubmissionGrade,
    ) -> None:
        """
        功能描述：
            写入评分结果消息。

        参数：
            assignment_id (str): 作业ID。
            student_id (str): 学生ID。
            sender_user_id (str): 发送者用户ID。
            body (SubmissionGrade): 接口请求体对象。
        返回值：
            None: 无返回值。
        """
        student_result = await self.repo.db.execute(select(Student).where(Student.id == student_id))
        student = student_result.scalars().first()
        if not student:
            return
        assignment_result = await self.repo.db.execute(
            select(Assignment).where(Assignment.id == assignment_id)
        )
        assignment = assignment_result.scalars().first()
        assignment_title = assignment.title if assignment else "当前作业"
        feedback_text = body.feedback.strip() if body.feedback else "暂无评语"
        self.repo.db.add(
            Message(
                sender_id=sender_user_id,
                receiver_id=student.user_id,
                title="作业批改结果",
                content=f"《{assignment_title}》已完成批改，得分 {body.score} 分。评语：{feedback_text}",
            )
        )
        await self.repo.commit()

    async def list_attachment_ai_feedbacks(self, id: str) -> Optional[list[dict]]:
        submission = await self.repo.get(id)
        if not submission:
            return None

        attachment_repo = AttachmentRepository(self.repo.db)
        feedback_repo = AIFeedbackRepository(self.repo.db)
        attachments = await attachment_repo.get_by_owner(
            owner_type="submission",
            owner_id=id,
        )
        feedbacks = await feedback_repo.list_by_targets(
            target_type=AIFeedbackTargetType.SUBMISSION_ATTACHMENT.value,
            target_ids=[attachment.id for attachment in attachments],
            feedback_scope=AIFeedbackScope.ATTACHMENT_ITEM.value,
            visibility_scopes=[AIFeedbackVisibility.SHARED_TEACHER_STUDENT.value],
        )
        feedback_map = {feedback.target_id: feedback for feedback in feedbacks}

        items: list[dict] = []
        for attachment in attachments:
            feedback = feedback_map.get(attachment.id)
            if feedback is None:
                items.append(
                    {
                        "id": None,
                        "attachment_id": attachment.id,
                        "status": AIFeedbackStatus.PENDING.value,
                        "visibility_scope": AIFeedbackVisibility.SHARED_TEACHER_STUDENT.value,
                        "payload": None,
                        "created_at": attachment.created_at,
                        "updated_at": attachment.created_at,
                    }
                )
                continue
            items.append(
                {
                    "id": feedback.id,
                    "attachment_id": attachment.id,
                    "status": feedback.status,
                    "visibility_scope": feedback.visibility_scope,
                    "payload": feedback.result_payload,
                    "created_at": feedback.created_at,
                    "updated_at": feedback.updated_at,
                }
            )
        return items

    async def queue_student_ai_summary(
        self,
        id: str,
        student_user_id: str,
    ) -> Optional[dict]:
        submission = await self.repo.get(id)
        if not submission:
            return None

        attachments = await AttachmentRepository(self.repo.db).get_by_owner(
            owner_type="submission",
            owner_id=id,
        )
        payload = {
            "submission_id": id,
            "attachment_count": len(attachments),
            "summary": "",
            "strengths": [],
            "improvements": [],
            "overall_level": None,
        }
        feedback = await AIFeedbackRepository(self.repo.db).upsert_feedback(
            target_type=AIFeedbackTargetType.SUBMISSION.value,
            target_id=id,
            feedback_scope=AIFeedbackScope.STUDENT_SUMMARY.value,
            visibility_scope=AIFeedbackVisibility.STUDENT_ONLY.value,
            status=AIFeedbackStatus.PENDING.value,
            generated_by=AIFeedbackGeneratedBy.STUDENT.value,
            result_payload=payload,
        )
        generate_submission_ai_summary.delay(id, student_user_id)
        return {"status": feedback.status, "submission_id": id}

    async def get_student_ai_summary(self, id: str) -> Optional[dict]:
        submission = await self.repo.get(id)
        if not submission:
            return None
        feedback = await AIFeedbackRepository(self.repo.db).get_by_slot(
            target_type=AIFeedbackTargetType.SUBMISSION.value,
            target_id=id,
            feedback_scope=AIFeedbackScope.STUDENT_SUMMARY.value,
        )
        if feedback is None:
            return {
                "id": None,
                "status": AIFeedbackStatus.PENDING.value,
                "visibility_scope": AIFeedbackVisibility.STUDENT_ONLY.value,
                "payload": None,
                "created_at": submission.submitted_at,
                "updated_at": submission.submitted_at,
            }
        return {
            "id": feedback.id,
            "status": feedback.status,
            "visibility_scope": feedback.visibility_scope,
            "payload": feedback.result_payload,
            "created_at": feedback.created_at,
            "updated_at": feedback.updated_at,
        }

    async def save_teacher_feedback(
        self,
        id: str,
        teacher_feedback: Optional[str],
        score: int,
    ) -> Optional[SubmissionResponse]:
        """
        功能描述：
            保存教师独立评语，不覆盖 ai_feedback。

        参数：
            id (str): 目标记录ID。
            teacher_feedback (Optional[str]): 教师评语文本。
            score (int): 教师打分。
        返回值：
            Optional[SubmissionResponse]: 返回更新后的结果对象；不存在时返回 None。
        """
        submission = await self.repo.get(id)
        if not submission:
            return None
        transition_result = self.state_machine.transition(
            SubmissionStatus(submission.status),
            SubmissionTransitionEvent.GRADE,
        )
        # graded_at 只在首次批改时写入，避免教师多次修改评语时时间戳被刷新
        update_payload: dict = {
            "teacher_feedback": teacher_feedback,
            "score": score,
            "status": transition_result.to_status,
        }
        if not submission.graded_at:
            update_payload["graded_at"] = datetime.now()
        updated = await self.repo.update(submission, update_payload)
        return SubmissionResponse.model_validate(updated)

    @staticmethod
    def _build_resubmission_payload(
        submission_in: SubmissionCreate,
        next_status: SubmissionStatus,
    ) -> dict:
        """
        功能描述：
            构建学生修改提交后的更新载荷。

        参数：
            submission_in (SubmissionCreate): 提交记录输入对象。
            next_status (SubmissionStatus): 重新提交后的目标状态。

        返回值：
            dict: 返回更新字段字典。
        """
        return {
            "content": submission_in.content,
            "status": next_status,
            "score": None,
            "teacher_feedback": None,
            "graded_at": None,
            "submitted_at": datetime.now(),
        }

    @staticmethod
    def _schedule_submission_followups(
        submission_id: str,
        new_attachment_ids: list[str],
        publish_outbox: bool = False,
    ) -> None:
        """
        功能描述：
            统一调度提交后的通知与 AI 异步任务。

        参数：
            submission_id (str): 提交记录ID。
            new_attachment_ids (list[str]): 本次新增并完成关联的附件ID列表。
            publish_outbox (bool): 是否触发 outbox 发布任务。

        返回值：
            None: 无返回值。
        """
        send_submission_notification.delay(submission_id)
        for attachment_id in new_attachment_ids:
            generate_ai_feedback.delay(attachment_id)
        if publish_outbox:
            publish_outbox_events.delay()

    async def list_submissions_by_teacher(
        self,
        teacher_id: str,
        status: Optional[str] = None,
        assignment_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
        page: Optional[int] = None,
        size: Optional[int] = None,
    ) -> SubmissionListResponse:
        """
        功能描述：
            获取教师所有提交记录列表。

        参数：
            teacher_id (str): 教师ID。
            status (Optional[str]): 提交状态筛选。
            assignment_id (Optional[str]): 作业ID筛选。
            skip (int): 分页偏移量。
            limit (int): 单次查询的最大返回数量。
            page (Optional[int]): 当前页码。
            size (Optional[int]): 每页条数。

        返回值：
            SubmissionListResponse: 返回列表或分页查询结果。
        """
        items = await self.repo.get_all_by_teacher(
            teacher_id=teacher_id,
            skip=skip,
            limit=limit,
            status=status,
            assignment_id=assignment_id,
        )
        total = await self.repo.count_by_teacher(
            teacher_id=teacher_id,
            status=status,
            assignment_id=assignment_id,
        )
        payload = build_paged_response(
            items=[SubmissionResponse.model_validate(i) for i in items],
            total=total,
            pagination={"page": page, "size": size, "skip": skip, "limit": limit},
        )
        return SubmissionListResponse(**payload)
