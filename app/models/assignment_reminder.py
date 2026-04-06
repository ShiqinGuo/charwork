from typing import Optional
from enum import Enum as PyEnum

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.utils.id_generator import generate_id


class AssignmentReminderPlanStatus(str, PyEnum):
    PENDING = "pending"
    DISABLED = "disabled"
    CANCELLED = "cancelled"
    EXECUTED = "executed"


class AssignmentReminderExecutionStatus(str, PyEnum):
    PENDING = "pending"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


class AssignmentReminderPlan(Base):
    __tablename__ = "assignment_reminder_plan"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=generate_id)
    assignment_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("assignment.id"),
        nullable=False,
        index=True,
    )
    course_id: Mapped[Optional[str]] = mapped_column(String(50), ForeignKey("course.id"), nullable=True, index=True)
    management_system_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("management_system.id"),
        nullable=False,
        index=True,
    )
    created_by_user_id: Mapped[str] = mapped_column(String(50), ForeignKey("user.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    remind_at: Mapped[DateTime] = mapped_column(DateTime, nullable=False)
    lead_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    target_filter: Mapped[str] = mapped_column(String(50), nullable=False, default="pending_students")
    status: Mapped[AssignmentReminderPlanStatus] = mapped_column(
        String(20),
        nullable=False,
        default=AssignmentReminderPlanStatus.PENDING,
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    scheduled_task_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    assignment: Mapped["Assignment"] = relationship("Assignment")  # noqa
    executions: Mapped[list["AssignmentReminderExecution"]] = relationship(
        "AssignmentReminderExecution",
        back_populates="plan",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        """
        功能描述：
            处理AssignmentReminderPlan。

        参数：
            无。

        返回值：
            None: 无返回值。
        """
        return f"<AssignmentReminderPlan(assignment_id='{self.assignment_id}', remind_at='{self.remind_at}')>"


class AssignmentReminderExecution(Base):
    __tablename__ = "assignment_reminder_execution"

    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=generate_id)
    plan_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("assignment_reminder_plan.id"),
        nullable=False,
        index=True,
    )
    assignment_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("assignment.id"),
        nullable=False,
        index=True,
    )
    management_system_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("management_system.id"),
        nullable=False,
        index=True,
    )
    status: Mapped[AssignmentReminderExecutionStatus] = mapped_column(
        String(20),
        nullable=False,
        default=AssignmentReminderExecutionStatus.PENDING,
    )
    scheduled_at: Mapped[DateTime] = mapped_column(DateTime, nullable=False)
    executed_at: Mapped[Optional[DateTime]] = mapped_column(DateTime, nullable=True)
    target_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    detail: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now())

    plan: Mapped["AssignmentReminderPlan"] = relationship("AssignmentReminderPlan", back_populates="executions")  # noqa
    assignment: Mapped["Assignment"] = relationship("Assignment")  # noqa

    def __repr__(self):
        """
        功能描述：
            处理AssignmentReminderExecution。

        参数：
            无。

        返回值：
            None: 无返回值。
        """
        return f"<AssignmentReminderExecution(plan_id='{self.plan_id}', status='{self.status}')>"
