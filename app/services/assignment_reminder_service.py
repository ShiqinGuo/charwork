"""
为什么这样做：提醒计划把“配置、执行、状态流转”拆开，保证可追踪且可重放。
特殊逻辑：状态与模板均走映射表驱动，避免分支膨胀；执行时按当前版本与截止条件做边界校验，防止过期任务误触发。
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.celery_app import celery_app
from app.models.assignment import Assignment
from app.models.assignment_reminder import (
    AssignmentReminderExecution,
    AssignmentReminderExecutionStatus,
    AssignmentReminderPlan,
    AssignmentReminderPlanStatus,
)
from app.models.course import Course
from app.models.message import Message
from app.models.student import Student
from app.models.submission import Submission
from app.models.teaching_class import TeachingClassMember, TeachingClassMemberStatus
from app.repositories.assignment_reminder_repo import AssignmentReminderRepository
from app.repositories.assignment_repo import AssignmentRepository
from app.schemas.assignment_reminder import (
    AssignmentReminderExecutionCreate,
    AssignmentReminderExecutionListResponse,
    AssignmentReminderExecutionResponse,
    AssignmentReminderPlanCreate,
    AssignmentReminderPlanListResponse,
    AssignmentReminderPlanResponse,
)


REMINDER_TITLE_TEMPLATES = {
    "default": "{plan_name}",
}
REMINDER_CONTENT_TEMPLATES = {
    "pending_students": "请尽快完成作业《{assignment_title}》。截止时间：{due_date}",
    "all_students": "请尽快完成作业《{assignment_title}》。截止时间：{due_date}",
    "default": "请尽快完成作业《{assignment_title}》。截止时间：{due_date}",
}
PLAN_STATUS_BY_ENABLEMENT = {
    True: AssignmentReminderPlanStatus.PENDING,
    False: AssignmentReminderPlanStatus.DISABLED,
}
EXECUTION_STATUS_RULES = {
    "no_targets": AssignmentReminderExecutionStatus.SKIPPED,
    "all_pending": AssignmentReminderExecutionStatus.SUCCESS,
    "partial_pending": AssignmentReminderExecutionStatus.PARTIAL,
    "all_submitted": AssignmentReminderExecutionStatus.SKIPPED,
}


@dataclass(frozen=True)
class ReminderPlanTransitionRule:
    is_enabled: bool
    status: AssignmentReminderPlanStatus
    clear_scheduled_task: bool = True


PLAN_TRANSITION_RULES = {
    "missing_assignment": ReminderPlanTransitionRule(
        is_enabled=False,
        status=AssignmentReminderPlanStatus.CANCELLED,
    ),
    "missing_course": ReminderPlanTransitionRule(
        is_enabled=False,
        status=AssignmentReminderPlanStatus.CANCELLED,
    ),
    "executed": ReminderPlanTransitionRule(
        is_enabled=False,
        status=AssignmentReminderPlanStatus.EXECUTED,
    ),
}


@dataclass(frozen=True)
class ReminderTarget:
    student_id: str
    user_id: str


@dataclass(frozen=True)
class ReminderTargetSnapshot:
    targets: list[ReminderTarget]
    pending_targets: list[ReminderTarget]
    submitted_student_ids: set[str]

    @property
    def target_count(self) -> int:
        """
        功能描述：
            处理count。

        参数：
            无。

        返回值：
            int: 返回int类型的处理结果。
        """
        return len(self.targets)

    @property
    def pending_count(self) -> int:
        """
        功能描述：
            处理count。

        参数：
            无。

        返回值：
            int: 返回int类型的处理结果。
        """
        return len(self.pending_targets)

    @property
    def skipped_count(self) -> int:
        """
        功能描述：
            处理count。

        参数：
            无。

        返回值：
            int: 返回int类型的处理结果。
        """
        return max(self.target_count - self.pending_count, 0)


class AssignmentReminderService:
    def __init__(self, db: AsyncSession):
        """
        功能描述：
            初始化AssignmentReminderService并准备运行所需的依赖对象。

        参数：
            db (AsyncSession): 数据库会话，用于执行持久化操作。

        返回值：
            None: 无返回值。
        """
        self.repo = AssignmentReminderRepository(db)
        self.assignment_repo = AssignmentRepository(db)

    async def list_plans(
        self,
        assignment_id: str,
        management_system_id: str,
    ) -> AssignmentReminderPlanListResponse:
        """
        功能描述：
            按条件查询plans列表。

        参数：
            assignment_id (str): 作业ID。
            management_system_id (str): 管理系统ID，用于限制数据作用域。

        返回值：
            AssignmentReminderPlanListResponse: 返回列表或分页查询结果。
        """
        assignment = await self.assignment_repo.get(assignment_id, management_system_id)
        if not assignment:
            raise ValueError("作业不存在")
        items = await self.repo.list_plans(assignment_id)
        total = await self.repo.count_plans(assignment_id)
        return AssignmentReminderPlanListResponse(
            total=total,
            items=self._build_plan_responses(items),
        )

    async def create_plan(
        self,
        assignment_id: str,
        management_system_id: str,
        current_user_id: str,
        body: AssignmentReminderPlanCreate,
    ) -> AssignmentReminderPlanResponse:
        """
        功能描述：
            创建计划并返回结果。

        参数：
            assignment_id (str): 作业ID。
            management_system_id (str): 管理系统ID，用于限制数据作用域。
            current_user_id (str): 当前用户ID。
            body (AssignmentReminderPlanCreate): 接口请求体对象。

        返回值：
            AssignmentReminderPlanResponse: 返回创建后的结果对象。
        """
        assignment = await self.assignment_repo.get(assignment_id, management_system_id)
        if not assignment:
            raise ValueError("作业不存在")
        if not assignment.course_id:
            raise ValueError("作业必须绑定课程后才能配置提醒")
        plan = self._build_plan(
            assignment=assignment,
            management_system_id=management_system_id,
            current_user_id=current_user_id,
            body=body,
        )
        created = await self.repo.add_plan(plan)
        await self._schedule_plan(created)
        await self.repo.save()
        await self.repo.refresh(created)
        return self._to_plan_response(created)

    async def sync_plans_for_assignment(
        self,
        assignment_id: str,
        management_system_id: str,
    ) -> AssignmentReminderPlanListResponse:
        """
        功能描述：
            同步plansfor作业。

        参数：
            assignment_id (str): 作业ID。
            management_system_id (str): 管理系统ID，用于限制数据作用域。

        返回值：
            AssignmentReminderPlanListResponse: 返回AssignmentReminderPlanListResponse类型的处理结果。
        """
        assignment = await self.assignment_repo.get(assignment_id, management_system_id)
        if not assignment:
            raise ValueError("作业不存在")
        items = await self.repo.list_plans(assignment_id)
        for item in items:
            if item.status == AssignmentReminderPlanStatus.EXECUTED:
                continue
            await self._sync_single_plan(item, assignment)
        if items:
            await self.repo.save()
        return AssignmentReminderPlanListResponse(
            total=len(items),
            items=self._build_plan_responses(items),
        )

    async def list_executions(
        self,
        assignment_id: str,
        management_system_id: str,
    ) -> AssignmentReminderExecutionListResponse:
        """
        功能描述：
            按条件查询executions列表。

        参数：
            assignment_id (str): 作业ID。
            management_system_id (str): 管理系统ID，用于限制数据作用域。

        返回值：
            AssignmentReminderExecutionListResponse: 返回列表或分页查询结果。
        """
        assignment = await self.assignment_repo.get(assignment_id, management_system_id)
        if not assignment:
            raise ValueError("作业不存在")
        items = await self.repo.list_executions(assignment_id)
        total = await self.repo.count_executions(assignment_id)
        return AssignmentReminderExecutionListResponse(
            total=total,
            items=self._build_execution_responses(items),
        )

    async def create_execution(
        self,
        assignment_id: str,
        management_system_id: str,
        body: AssignmentReminderExecutionCreate,
    ) -> AssignmentReminderExecutionResponse:
        """
        功能描述：
            创建执行记录并返回结果。

        参数：
            assignment_id (str): 作业ID。
            management_system_id (str): 管理系统ID，用于限制数据作用域。
            body (AssignmentReminderExecutionCreate): 接口请求体对象。

        返回值：
            AssignmentReminderExecutionResponse: 返回创建后的结果对象。
        """
        assignment = await self.assignment_repo.get(assignment_id, management_system_id)
        if not assignment:
            raise ValueError("作业不存在")
        plan = await self.repo.get_plan(body.plan_id)
        if not plan or plan.assignment_id != assignment_id:
            raise ValueError("提醒计划不存在")
        execution = AssignmentReminderExecution(
            plan_id=body.plan_id,
            assignment_id=assignment_id,
            management_system_id=management_system_id,
            scheduled_at=body.scheduled_at,
            executed_at=body.executed_at,
            status=body.status,
            target_count=body.target_count,
            success_count=body.success_count,
            failure_count=body.failure_count,
            skipped_count=body.skipped_count,
            detail=body.detail,
        )
        created = await self.repo.add_execution(execution)
        await self.repo.save()
        await self.repo.refresh(created)
        return self._to_execution_response(created)

    async def execute_due_plans(
        self,
        assignment_id: str,
        management_system_id: str,
        sender_user_id: str,
        now: datetime | None = None,
    ) -> AssignmentReminderExecutionListResponse:
        """
        功能描述：
            执行dueplans。

        参数：
            assignment_id (str): 作业ID。
            management_system_id (str): 管理系统ID，用于限制数据作用域。
            sender_user_id (str): 发送者用户ID。
            now (datetime | None): datetime | None 类型的数据。

        返回值：
            AssignmentReminderExecutionListResponse: 返回AssignmentReminderExecutionListResponse类型的处理结果。
        """
        assignment = await self.assignment_repo.get(assignment_id, management_system_id)
        if not assignment:
            raise ValueError("作业不存在")
        execution_time = now or datetime.now()
        plans = await self.repo.list_due_pending_plans(assignment_id, management_system_id, execution_time)
        return await self._execute_plans(
            assignment=assignment,
            plans=plans,
            management_system_id=management_system_id,
            sender_user_id=sender_user_id,
            execution_time=execution_time,
        )

    async def execute_plan(
        self,
        plan_id: str,
        management_system_id: str,
        sender_user_id: str,
        expected_version: int,
        now: datetime | None = None,
    ) -> AssignmentReminderExecutionListResponse:
        """
        功能描述：
            执行计划。

        参数：
            plan_id (str): 计划ID。
            management_system_id (str): 管理系统ID，用于限制数据作用域。
            sender_user_id (str): 发送者用户ID。
            expected_version (int): 整数结果。
            now (datetime | None): datetime | None 类型的数据。

        返回值：
            AssignmentReminderExecutionListResponse: 返回AssignmentReminderExecutionListResponse类型的处理结果。
        """
        plan = await self.repo.get_plan(plan_id)
        if not plan or plan.management_system_id != management_system_id:
            return AssignmentReminderExecutionListResponse(total=0, items=[])
        assignment = await self.assignment_repo.get(plan.assignment_id, management_system_id)
        if not assignment:
            self._apply_plan_transition(plan, "missing_assignment")
            await self.repo.save()
            return AssignmentReminderExecutionListResponse(total=0, items=[])
        execution_time = now or datetime.now()
        if not self._is_current_plan(plan, expected_version, execution_time):
            return AssignmentReminderExecutionListResponse(total=0, items=[])
        return await self._execute_plans(
            assignment=assignment,
            plans=[plan],
            management_system_id=management_system_id,
            sender_user_id=sender_user_id,
            execution_time=execution_time,
        )

    def _build_plan(
        self,
        assignment: Assignment,
        management_system_id: str,
        current_user_id: str,
        body: AssignmentReminderPlanCreate,
    ) -> AssignmentReminderPlan:
        """
        功能描述：
            构建计划。

        参数：
            assignment (Assignment): Assignment 类型的数据。
            management_system_id (str): 管理系统ID，用于限制数据作用域。
            current_user_id (str): 当前用户ID。
            body (AssignmentReminderPlanCreate): 接口请求体对象。

        返回值：
            AssignmentReminderPlan: 返回AssignmentReminderPlan类型的处理结果。
        """
        return AssignmentReminderPlan(
            assignment_id=assignment.id,
            course_id=assignment.course_id,
            management_system_id=management_system_id,
            created_by_user_id=current_user_id,
            name=body.name,
            version=body.version,
            sequence_no=body.sequence_no,
            remind_at=self._resolve_remind_at(assignment.due_date, body.lead_minutes, body.remind_at),
            lead_minutes=body.lead_minutes,
            target_filter=body.target_filter,
            is_enabled=body.is_enabled,
            status=self._resolve_enabled_plan_status(body.is_enabled),
            payload=body.payload,
        )

    async def _sync_single_plan(
        self,
        plan: AssignmentReminderPlan,
        assignment: Assignment,
    ) -> None:
        """
        功能描述：
            同步single计划。

        参数：
            plan (AssignmentReminderPlan): AssignmentReminderPlan 类型的数据。
            assignment (Assignment): Assignment 类型的数据。

        返回值：
            None: 无返回值。
        """
        await self._cleanup_scheduled_task(plan)
        plan.course_id = assignment.course_id
        plan.remind_at = self._resolve_remind_at(assignment.due_date, plan.lead_minutes, plan.remind_at)
        plan.version += 1
        plan.is_enabled, plan.status = self._resolve_synced_plan_state(
            has_course=bool(assignment.course_id),
            is_enabled=plan.is_enabled,
        )
        if plan.status == AssignmentReminderPlanStatus.PENDING:
            await self._schedule_plan(plan)

    async def _execute_plans(
        self,
        assignment: Assignment,
        plans: list[AssignmentReminderPlan],
        management_system_id: str,
        sender_user_id: str,
        execution_time: datetime,
    ) -> AssignmentReminderExecutionListResponse:
        """
        功能描述：
            执行plans。

        参数：
            assignment (Assignment): Assignment 类型的数据。
            plans (list[AssignmentReminderPlan]): 列表结果。
            management_system_id (str): 管理系统ID，用于限制数据作用域。
            sender_user_id (str): 发送者用户ID。
            execution_time (datetime): datetime 类型的数据。

        返回值：
            AssignmentReminderExecutionListResponse: 返回AssignmentReminderExecutionListResponse类型的处理结果。
        """
        if not plans:
            return AssignmentReminderExecutionListResponse(total=0, items=[])
        snapshot = await self._build_target_snapshot(assignment.id, assignment.course_id, management_system_id)
        execution_items: list[AssignmentReminderExecution] = []
        for plan in plans:
            execution = await self._execute_single_plan(
                assignment=assignment,
                plan=plan,
                snapshot=snapshot,
                management_system_id=management_system_id,
                sender_user_id=sender_user_id,
                execution_time=execution_time,
            )
            execution_items.append(execution)
        await self.repo.save()
        for item in execution_items:
            await self.repo.refresh(item)
        return AssignmentReminderExecutionListResponse(
            total=len(execution_items),
            items=self._build_execution_responses(execution_items),
        )

    async def _build_target_snapshot(
        self,
        assignment_id: str,
        course_id: str | None,
        management_system_id: str,
    ) -> ReminderTargetSnapshot:
        """
        功能描述：
            构建targetsnapshot。

        参数：
            assignment_id (str): 作业ID。
            course_id (str | None): 课程ID。
            management_system_id (str): 管理系统ID，用于限制数据作用域。

        返回值：
            ReminderTargetSnapshot: 返回ReminderTargetSnapshot类型的处理结果。
        """
        targets = await self._list_target_students(course_id)
        submitted_student_ids = await self._list_submitted_student_ids(assignment_id, management_system_id)
        pending_targets = self._filter_pending_targets(targets, submitted_student_ids)
        return ReminderTargetSnapshot(
            targets=targets,
            pending_targets=pending_targets,
            submitted_student_ids=submitted_student_ids,
        )

    async def _execute_single_plan(
        self,
        assignment: Assignment,
        plan: AssignmentReminderPlan,
        snapshot: ReminderTargetSnapshot,
        management_system_id: str,
        sender_user_id: str,
        execution_time: datetime,
    ) -> AssignmentReminderExecution:
        """
        功能描述：
            执行single计划。

        参数：
            assignment (Assignment): Assignment 类型的数据。
            plan (AssignmentReminderPlan): AssignmentReminderPlan 类型的数据。
            snapshot (ReminderTargetSnapshot): ReminderTargetSnapshot 类型的数据。
            management_system_id (str): 管理系统ID，用于限制数据作用域。
            sender_user_id (str): 发送者用户ID。
            execution_time (datetime): datetime 类型的数据。

        返回值：
            AssignmentReminderExecution: 返回AssignmentReminderExecution类型的处理结果。
        """
        messages = self._build_messages(
            plan,
            assignment,
            snapshot.pending_targets,
            management_system_id,
            sender_user_id,
        )
        self._persist_messages(messages)
        execution = self._build_execution_record(
            assignment=assignment,
            plan=plan,
            snapshot=snapshot,
            management_system_id=management_system_id,
            execution_time=execution_time,
        )
        await self.repo.add_execution(execution)
        self._apply_plan_transition(plan, "executed")
        return execution

    @staticmethod
    def _build_plan_responses(items: list[AssignmentReminderPlan]) -> list[AssignmentReminderPlanResponse]:
        """
        功能描述：
            构建计划responses。

        参数：
            items (list[AssignmentReminderPlan]): 当前处理的实体对象列表。

        返回值：
            list[AssignmentReminderPlanResponse]: 返回列表形式的结果数据。
        """
        return [AssignmentReminderService._to_plan_response(item) for item in items]

    @staticmethod
    def _build_execution_responses(
        items: list[AssignmentReminderExecution],
    ) -> list[AssignmentReminderExecutionResponse]:
        """
        功能描述：
            构建执行记录responses。

        参数：
            items (list[AssignmentReminderExecution]): 当前处理的实体对象列表。

        返回值：
            list[AssignmentReminderExecutionResponse]: 返回列表形式的结果数据。
        """
        return [AssignmentReminderService._to_execution_response(item) for item in items]

    @staticmethod
    def _filter_pending_targets(
        targets: list[ReminderTarget],
        submitted_student_ids: set[str],
    ) -> list[ReminderTarget]:
        """
        功能描述：
            过滤pendingtargets。

        参数：
            targets (list[ReminderTarget]): 列表结果。
            submitted_student_ids (set[str]): submitted学生ID列表。

        返回值：
            list[ReminderTarget]: 返回列表形式的结果数据。
        """
        return [
            target
            for target in targets
            if target.student_id not in submitted_student_ids
        ]

    def _persist_messages(self, messages: list[Message]) -> None:
        """
        功能描述：
            持久化消息。

        参数：
            messages (list[Message]): 列表结果。

        返回值：
            None: 无返回值。
        """
        for message in messages:
            self.repo.db.add(message)

    def _build_messages(
        self,
        plan: AssignmentReminderPlan,
        assignment: Assignment,
        targets: list[ReminderTarget],
        management_system_id: str,
        sender_user_id: str,
    ) -> list[Message]:
        """
        功能描述：
            构建消息。

        参数：
            plan (AssignmentReminderPlan): AssignmentReminderPlan 类型的数据。
            assignment (Assignment): Assignment 类型的数据。
            targets (list[ReminderTarget]): 列表结果。
            management_system_id (str): 管理系统ID，用于限制数据作用域。
            sender_user_id (str): 发送者用户ID。

        返回值：
            list[Message]: 返回列表形式的结果数据。
        """
        title = self._build_message_title(plan.name, plan.target_filter)
        content = self._build_message_content(assignment.title, assignment.due_date, plan.target_filter)
        return [
            Message(
                sender_id=sender_user_id,
                receiver_id=target.user_id,
                management_system_id=management_system_id,
                title=title,
                content=content,
            )
            for target in targets
        ]

    def _build_execution_record(
        self,
        assignment: Assignment,
        plan: AssignmentReminderPlan,
        snapshot: ReminderTargetSnapshot,
        management_system_id: str,
        execution_time: datetime,
    ) -> AssignmentReminderExecution:
        """
        功能描述：
            构建执行记录记录。

        参数：
            assignment (Assignment): Assignment 类型的数据。
            plan (AssignmentReminderPlan): AssignmentReminderPlan 类型的数据。
            snapshot (ReminderTargetSnapshot): ReminderTargetSnapshot 类型的数据。
            management_system_id (str): 管理系统ID，用于限制数据作用域。
            execution_time (datetime): datetime 类型的数据。

        返回值：
            AssignmentReminderExecution: 返回AssignmentReminderExecution类型的处理结果。
        """
        return AssignmentReminderExecution(
            plan_id=plan.id,
            assignment_id=assignment.id,
            management_system_id=management_system_id,
            scheduled_at=plan.remind_at,
            executed_at=execution_time,
            status=self._resolve_execution_status(snapshot),
            target_count=snapshot.target_count,
            success_count=snapshot.pending_count,
            failure_count=0,
            skipped_count=snapshot.skipped_count,
            detail=self._build_execution_detail(plan, snapshot),
        )

    @staticmethod
    def _build_execution_detail(
        plan: AssignmentReminderPlan,
        snapshot: ReminderTargetSnapshot,
    ) -> dict[str, int | str | list[str]]:
        """
        功能描述：
            构建执行记录detail。

        参数：
            plan (AssignmentReminderPlan): AssignmentReminderPlan 类型的数据。
            snapshot (ReminderTargetSnapshot): ReminderTargetSnapshot 类型的数据。

        返回值：
            dict[str, int | str | list[str]]: 返回字典形式的结果数据。
        """
        return {
            "plan_version": plan.version,
            "target_filter": plan.target_filter,
            "pending_student_ids": [target.student_id for target in snapshot.pending_targets],
            "submitted_student_ids": sorted(snapshot.submitted_student_ids),
        }

    async def _cleanup_scheduled_task(self, plan: AssignmentReminderPlan) -> None:
        """
        功能描述：
            处理scheduled任务。

        参数：
            plan (AssignmentReminderPlan): AssignmentReminderPlan 类型的数据。

        返回值：
            None: 无返回值。
        """
        if not plan.scheduled_task_id:
            return
        celery_app.control.revoke(plan.scheduled_task_id, terminate=False)
        plan.scheduled_task_id = None

    async def _schedule_plan(self, plan: AssignmentReminderPlan) -> None:
        """
        功能描述：
            处理计划。

        参数：
            plan (AssignmentReminderPlan): AssignmentReminderPlan 类型的数据。

        返回值：
            None: 无返回值。
        """
        if (
            not plan.is_enabled
            or plan.status != AssignmentReminderPlanStatus.PENDING
            or not plan.course_id
        ):
            plan.scheduled_task_id = None
            return
        from app.tasks.notification_tasks import batch_send_reminder

        async_result = batch_send_reminder.apply_async(
            args=[plan.id, plan.management_system_id, plan.created_by_user_id, plan.version],
            eta=plan.remind_at,
        )
        plan.scheduled_task_id = async_result.id

    @staticmethod
    def _resolve_enabled_plan_status(is_enabled: bool) -> AssignmentReminderPlanStatus:
        """
        功能描述：
            解析enabled计划状态。

        参数：
            is_enabled (bool): 标识是否enabled。

        返回值：
            AssignmentReminderPlanStatus: 返回AssignmentReminderPlanStatus类型的处理结果。
        """
        return PLAN_STATUS_BY_ENABLEMENT[is_enabled]

    @staticmethod
    def _resolve_synced_plan_state(
        has_course: bool,
        is_enabled: bool,
    ) -> tuple[bool, AssignmentReminderPlanStatus]:
        """
        功能描述：
            解析synced计划状态。

        参数：
            has_course (bool): 标识是否具备课程。
            is_enabled (bool): 标识是否enabled。

        返回值：
            tuple[bool, AssignmentReminderPlanStatus]: 返回tuple[bool, AssignmentReminderPlanStatus]类型的处理结果。
        """
        if not has_course:
            rule = PLAN_TRANSITION_RULES["missing_course"]
            return rule.is_enabled, rule.status
        return is_enabled, PLAN_STATUS_BY_ENABLEMENT[is_enabled]

    @staticmethod
    def _resolve_execution_status(snapshot: ReminderTargetSnapshot) -> AssignmentReminderExecutionStatus:
        """
        功能描述：
            解析执行记录状态。

        参数：
            snapshot (ReminderTargetSnapshot): ReminderTargetSnapshot 类型的数据。

        返回值：
            AssignmentReminderExecutionStatus: 返回AssignmentReminderExecutionStatus类型的处理结果。
        """
        if snapshot.target_count == 0:
            return EXECUTION_STATUS_RULES["no_targets"]
        if snapshot.pending_count == snapshot.target_count:
            return EXECUTION_STATUS_RULES["all_pending"]
        if snapshot.pending_count == 0:
            return EXECUTION_STATUS_RULES["all_submitted"]
        return EXECUTION_STATUS_RULES["partial_pending"]

    @staticmethod
    def _apply_plan_transition(plan: AssignmentReminderPlan, transition_key: str) -> None:
        """
        功能描述：
            处理计划流转。

        参数：
            plan (AssignmentReminderPlan): AssignmentReminderPlan 类型的数据。
            transition_key (str): 字符串结果。

        返回值：
            None: 无返回值。
        """
        rule = PLAN_TRANSITION_RULES[transition_key]
        plan.is_enabled = rule.is_enabled
        plan.status = rule.status
        if rule.clear_scheduled_task:
            plan.scheduled_task_id = None

    @staticmethod
    def _build_message_title(plan_name: str, target_filter: str) -> str:
        """
        功能描述：
            构建消息title。

        参数：
            plan_name (str): 字符串结果。
            target_filter (str): 字符串结果。

        返回值：
            str: 返回str类型的处理结果。
        """
        template = REMINDER_TITLE_TEMPLATES.get(target_filter, REMINDER_TITLE_TEMPLATES["default"])
        return template.format(plan_name=plan_name)

    @staticmethod
    def _build_message_content(
        assignment_title: str,
        due_date: datetime | None,
        target_filter: str,
    ) -> str:
        """
        功能描述：
            构建消息content。

        参数：
            assignment_title (str): 字符串结果。
            due_date (datetime | None): datetime | None 类型的数据。
            target_filter (str): 字符串结果。

        返回值：
            str: 返回str类型的处理结果。
        """
        template = REMINDER_CONTENT_TEMPLATES.get(target_filter, REMINDER_CONTENT_TEMPLATES["default"])
        return template.format(
            assignment_title=assignment_title,
            due_date=AssignmentReminderService._format_due_date(due_date),
        )

    @staticmethod
    def _is_current_plan(
        plan: AssignmentReminderPlan,
        expected_version: int,
        execution_time: datetime,
    ) -> bool:
        """
        功能描述：
            处理当前计划。

        参数：
            plan (AssignmentReminderPlan): AssignmentReminderPlan 类型的数据。
            expected_version (int): 整数结果。
            execution_time (datetime): datetime 类型的数据。

        返回值：
            bool: 返回操作是否成功。
        """
        return (
            plan.version == expected_version
            and plan.is_enabled
            and plan.status == AssignmentReminderPlanStatus.PENDING
            and plan.remind_at <= execution_time
            and bool(plan.course_id)
        )

    async def _list_target_students(self, course_id: str | None) -> list[ReminderTarget]:
        """
        功能描述：
            按条件查询target学生列表。

        参数：
            course_id (str | None): 课程ID。

        返回值：
            list[ReminderTarget]: 返回列表形式的结果数据。
        """
        if not course_id:
            return []
        result = await self.repo.db.execute(
            select(Student.id, Student.user_id)
            .join(TeachingClassMember, TeachingClassMember.student_id == Student.id)
            .join(
                Course,
                Course.teaching_class_id == TeachingClassMember.teaching_class_id,
            )
            .where(
                Course.id == course_id,
                TeachingClassMember.status == TeachingClassMemberStatus.ACTIVE,
            )
            .distinct()
        )
        return [
            ReminderTarget(student_id=row[0], user_id=row[1])
            for row in result.all()
        ]

    async def _list_submitted_student_ids(
        self,
        assignment_id: str,
        management_system_id: str,
    ) -> set[str]:
        """
        功能描述：
            按条件查询submitted学生标识列表列表。

        参数：
            assignment_id (str): 作业ID。
            management_system_id (str): 管理系统ID，用于限制数据作用域。

        返回值：
            set[str]: 返回set[str]类型的处理结果。
        """
        result = await self.repo.db.execute(
            select(Submission.student_id)
            .where(
                Submission.assignment_id == assignment_id,
                Submission.management_system_id == management_system_id,
            )
            .distinct()
        )
        return {row[0] for row in result.all()}

    @staticmethod
    def _resolve_remind_at(
        due_date: datetime | None,
        lead_minutes: int,
        fallback: datetime,
    ) -> datetime:
        """
        功能描述：
            解析remindat。

        参数：
            due_date (datetime | None): datetime | None 类型的数据。
            lead_minutes (int): 整数结果。
            fallback (datetime): datetime 类型的数据。

        返回值：
            datetime: 返回datetime类型的处理结果。
        """
        if due_date:
            return due_date - timedelta(minutes=lead_minutes)
        return fallback

    @staticmethod
    def _format_due_date(due_date: datetime | None) -> str:
        """
        功能描述：
            格式化duedate。

        参数：
            due_date (datetime | None): datetime | None 类型的数据。

        返回值：
            str: 返回str类型的处理结果。
        """
        if not due_date:
            return "未设置"
        return due_date.strftime("%Y-%m-%d %H:%M")

    @staticmethod
    def _to_plan_response(item: AssignmentReminderPlan) -> AssignmentReminderPlanResponse:
        """
        功能描述：
            将输入数据转换为计划响应。

        参数：
            item (AssignmentReminderPlan): 当前处理的实体对象。

        返回值：
            AssignmentReminderPlanResponse: 返回AssignmentReminderPlanResponse类型的处理结果。
        """
        return AssignmentReminderPlanResponse(
            id=item.id,
            assignment_id=item.assignment_id,
            course_id=item.course_id,
            management_system_id=item.management_system_id,
            created_by_user_id=item.created_by_user_id,
            name=item.name,
            remind_at=item.remind_at,
            version=item.version,
            sequence_no=item.sequence_no,
            lead_minutes=item.lead_minutes,
            target_filter=item.target_filter,
            is_enabled=item.is_enabled,
            status=item.status,
            payload=item.payload or {},
            created_at=item.created_at,
            updated_at=item.updated_at,
        )

    @staticmethod
    def _to_execution_response(item: AssignmentReminderExecution) -> AssignmentReminderExecutionResponse:
        """
        功能描述：
            将输入数据转换为执行记录响应。

        参数：
            item (AssignmentReminderExecution): 当前处理的实体对象。

        返回值：
            AssignmentReminderExecutionResponse: 返回AssignmentReminderExecutionResponse类型的处理结果。
        """
        return AssignmentReminderExecutionResponse(
            id=item.id,
            plan_id=item.plan_id,
            assignment_id=item.assignment_id,
            management_system_id=item.management_system_id,
            scheduled_at=item.scheduled_at,
            executed_at=item.executed_at,
            status=item.status,
            target_count=item.target_count,
            success_count=item.success_count,
            failure_count=item.failure_count,
            skipped_count=item.skipped_count,
            detail=item.detail or {},
            created_at=item.created_at,
        )
