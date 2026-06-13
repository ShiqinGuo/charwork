"""
作业通知服务：负责通知构建、目标筛选和消息写入。
"""
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Course
from app.models.message import Message
from app.models.student import Student
from app.models.submission import Submission
from app.models.teaching_class import TeachingClassMember, TeachingClassMemberStatus
from app.models.user import User, UserRole


PUBLISH_NOTIFICATION_TITLE = "新作业发布"
DELAY_NOTIFICATION_TITLE = "作业延期通知"
DEFAULT_REMINDER_TITLE = "作业提醒"
PUBLISH_NOTIFICATION_TEMPLATE = "《{assignment_title}》已发布，请按时完成。截止时间：{due_date}"
DELAY_NOTIFICATION_TEMPLATE = "《{assignment_title}》截止时间已调整为 {due_date}。{reason_text}"
REMINDER_NOTIFICATION_TEMPLATE = "请关注作业《{assignment_title}》，截止时间：{due_date}。"


@dataclass(frozen=True)
class AssignmentNotificationTarget:
    user_id: str
    student_id: str | None = None


@dataclass(frozen=True)
class AssignmentNotificationPayload:
    title: str
    content: str
    only_pending: bool = False


class AssignmentNotificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _format_due_date(due_date: datetime | None) -> str:
        if not due_date:
            return "未设置"
        return due_date.strftime("%Y-%m-%d %H:%M")

    def _build_publish_notification(self, assignment) -> AssignmentNotificationPayload:
        return AssignmentNotificationPayload(
            title=PUBLISH_NOTIFICATION_TITLE,
            content=PUBLISH_NOTIFICATION_TEMPLATE.format(
                assignment_title=assignment.title,
                due_date=self._format_due_date(assignment.due_date),
            ),
        )

    def _build_delay_notification(self, assignment, reason: str | None) -> AssignmentNotificationPayload:
        reason_text = f"延期原因：{reason}。" if reason else ""
        return AssignmentNotificationPayload(
            title=DELAY_NOTIFICATION_TITLE,
            content=DELAY_NOTIFICATION_TEMPLATE.format(
                assignment_title=assignment.title,
                due_date=self._format_due_date(assignment.due_date),
                reason_text=reason_text,
            ),
        )

    def _build_reminder_notification(self, assignment, body) -> AssignmentNotificationPayload:
        return AssignmentNotificationPayload(
            title=body.title or DEFAULT_REMINDER_TITLE,
            content=body.content or REMINDER_NOTIFICATION_TEMPLATE.format(
                assignment_title=assignment.title,
                due_date=self._format_due_date(assignment.due_date),
            ),
            only_pending=True,
        )

    async def notify_students(
        self, sender_user_id: str, assignment, *,
        payload: AssignmentNotificationPayload | None = None,
        title: str | None = None, content: str | None = None,
        only_pending: bool = False,
    ) -> int:
        resolved = payload or AssignmentNotificationPayload(
            title=title or DEFAULT_REMINDER_TITLE,
            content=content or "",
            only_pending=only_pending,
        )
        targets = await self._list_notification_targets(
            assignment=assignment,
            only_pending=resolved.only_pending,
            sender_user_id=sender_user_id,
        )
        if not targets:
            return 0
        for target in targets:
            self.db.add(Message(
                sender_id=sender_user_id, receiver_id=target["user_id"],
                title=resolved.title, content=resolved.content,
            ))
        await self.db.commit()
        return len(targets)

    async def _list_notification_targets(self, assignment, only_pending: bool, sender_user_id: str) -> list[dict]:
        if assignment is None or not assignment.course_id:
            return self._serialize_targets(await self._list_global_student_targets(sender_user_id))
        targets = await self._list_course_student_targets(assignment.course_id, sender_user_id)
        if not only_pending:
            return self._serialize_targets(targets)
        submitted_ids = await self._list_submitted_student_ids(assignment.id)
        return self._serialize_targets(self._filter_pending_targets(targets, submitted_ids))

    async def _list_global_student_targets(self, sender_user_id: str) -> list[AssignmentNotificationTarget]:
        result = await self.db.execute(
            select(Student.id, Student.user_id)
            .join(User, User.id == Student.user_id)
            .where(User.role == UserRole.STUDENT, Student.user_id != sender_user_id)
            .distinct()
        )
        return [self._build_target(row) for row in result.all()]

    async def _list_course_student_targets(
            self, course_id: str, sender_user_id: str) -> list[AssignmentNotificationTarget]:
        result = await self.db.execute(
            select(Student.id, Student.user_id)
            .join(TeachingClassMember, TeachingClassMember.student_id == Student.id)
            .join(Course, Course.teaching_class_id == TeachingClassMember.teaching_class_id)
            .join(User, User.id == Student.user_id)
            .where(Course.id == course_id, TeachingClassMember.status == TeachingClassMemberStatus.ACTIVE,
                   User.role == UserRole.STUDENT, Student.user_id != sender_user_id)
            .distinct()
        )
        return [self._build_target(row) for row in result.all()]

    async def _list_submitted_student_ids(self, assignment_id: str) -> set[str]:
        result = await self.db.execute(
            select(Submission.student_id).where(Submission.assignment_id == assignment_id).distinct()
        )
        return {row[0] for row in result.all()}

    @staticmethod
    def _filter_pending_targets(targets: list[AssignmentNotificationTarget],
                                submitted_ids: set[str]) -> list[AssignmentNotificationTarget]:
        return [t for t in targets if t.student_id not in submitted_ids]

    @staticmethod
    def _serialize_targets(targets: list[AssignmentNotificationTarget]) -> list[dict]:
        return [{"student_id": t.student_id, "user_id": t.user_id} for t in targets]

    @staticmethod
    def _build_target(row: tuple) -> AssignmentNotificationTarget:
        if len(row) > 1:
            return AssignmentNotificationTarget(student_id=row[0], user_id=row[1])
        return AssignmentNotificationTarget(student_id=None, user_id=row[-1])
