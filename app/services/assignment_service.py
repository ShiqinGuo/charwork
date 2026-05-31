"""
为什么这样做：作业服务聚合状态机、通知、附件与字段值写入，确保一次业务动作后的数据一致性。
特殊逻辑：通知目标按"全局/课程/仅未提交"三层边界过滤，附件 file_key 兼容对象与字典输入，支持动态来源数据。
"""

from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assignment import AssignmentStatus
from app.repositories.assignment_repo import AssignmentRepository
from app.repositories.course_repo import CourseRepository
from app.schemas.assignment import (
    AssignmentActionResponse,
    AssignmentCreate,
    AssignmentDelayRequest,
    AssignmentUpdate,
    AssignmentResponse,
    AssignmentListResponse,
    AssignmentReminderRequest,
    AssignmentTransitionEvent,
    AssignmentTransitionResponse,
)
from app.services.assignment_notification_service import AssignmentNotificationService
from app.services.assignment_state_machine import AssignmentStateMachine
from app.services.attachment_service import AttachmentService
from app.utils.pagination import build_paged_response


class AssignmentService:
    def __init__(self, db: AsyncSession):
        """
        功能描述：
            初始化AssignmentService并准备运行所需的依赖对象。

        参数：
            db (AsyncSession): 数据库会话，用于执行持久化操作。

        返回值：
            None: 无返回值。
        """
        self.repo = AssignmentRepository(db)
        self.course_repo = CourseRepository(db)
        self.state_machine = AssignmentStateMachine()
        self.notification = AssignmentNotificationService(db)

    async def get_assignment(
        self,
        id: str,
        current_user_role: Optional[str] = None,
    ) -> Optional[AssignmentResponse]:
        """
        功能描述：
            按条件获取作业。

        参数：
            id (str): 目标记录ID。
            current_user_role (Optional[str]): 当前用户角色，用于控制权限或字段可见性。

        返回值：
            Optional[AssignmentResponse]: 返回查询到的结果对象；未命中时返回 None。
        """
        assignment = await self.repo.get(id)
        if assignment:
            return self._to_response(assignment)
        return None

    async def list_assignments(
        self,
        skip: int = 0,
        limit: int = 20,
        teacher_id: Optional[str] = None,
        status: Optional[str] = None,
        course_id: Optional[str] = None,
        current_student_id: Optional[str] = None,
        current_user_role: Optional[str] = None,
        page: Optional[int] = None,
        size: Optional[int] = None,
    ) -> AssignmentListResponse:
        """
        功能描述：
            按条件查询作业列表。

        参数：
            skip (int): 分页偏移量。
            limit (int): 单次查询的最大返回数量。
            teacher_id (Optional[str]): 教师ID。
            status (Optional[str]): 状态筛选条件或目标状态。
            course_id (Optional[str]): 课程ID。
            current_student_id (Optional[str]): 当前学生ID。
            current_user_role (Optional[str]): 当前用户角色，用于控制权限或字段可见性。
            page (Optional[int]): 当前页码。
            size (Optional[int]): 每页条数。

        返回值：
            AssignmentListResponse: 返回列表或分页查询结果。
        """
        course_id, course_ids = await self._resolve_assignment_filters(
            current_student_id=current_student_id,
            course_id=course_id,
        )
        items = await self.repo.get_all(
            skip,
            limit,
            teacher_id,
            status,
            course_id,
            course_ids,
        )
        total = await self.repo.count(
            teacher_id,
            status,
            course_id,
            course_ids,
        )
        custom_field_values_by_target: dict[str, dict] = {}
        payload = build_paged_response(
            items=[
                self._to_response(
                    item,
                    custom_field_values=custom_field_values_by_target.get(item.id, {}),
                )
                for item in items
            ],
            total=total,
            pagination={"page": page, "size": size, "skip": skip, "limit": limit},
        )
        return AssignmentListResponse(**payload)

    async def create_assignment(
        self,
        assignment_in: AssignmentCreate,
        teacher_id: str,
    ) -> AssignmentResponse:
        """
        功能描述：
            创建作业并返回结果。

        参数：
            assignment_in (AssignmentCreate): 作业输入对象。
            teacher_id (str): 教师ID。
        返回值：
            AssignmentResponse: 返回创建后的结果对象。
        """
        # 发布前必须先把课程关系解析成当前教师可维护的合法课程，避免作业落到越权课程上。
        course_id = await self._resolve_course_id(assignment_in.course_id, teacher_id)
        # 作业与步骤中的附件在入库前先校验上传记录，避免保存后再出现"附件不存在"的脏数据。
        await self._ensure_attachment_uploads_exist(
            attachments=assignment_in.attachments,
            instruction_steps=assignment_in.instruction_steps,
        )
        assignment = await self.repo.create(
            assignment_in,
            teacher_id,
            course_id=course_id,
        )
        # 作业创建成功后立即回写附件归属，确保附件后续可随作业一起查询、删除和导出。
        await self._sync_attachment_uploads(
            assignment.id,
            attachments=assignment_in.attachments,
            instruction_steps=assignment_in.instruction_steps,
        )
        await self._sync_reminder_plans(assignment.id)
        return await self.get_assignment(assignment.id)

    async def update_assignment(
        self,
        id: str,
        assignment_in: AssignmentUpdate,
    ) -> Optional[AssignmentResponse]:
        """
        功能描述：
            更新作业并返回最新结果。

        参数：
            id (str): 目标记录ID。
            assignment_in (AssignmentUpdate): 作业输入对象。
        返回值：
            Optional[AssignmentResponse]: 返回更新后的结果对象；未命中时返回 None。
        """
        assignment = await self.repo.get(id)
        if not assignment:
            return None

        if "course_id" in assignment_in.model_fields_set:
            # 显式传入 course_id 代表调用方要改绑课程，此时必须重新做课程合法性校验。
            if assignment_in.course_id is None:
                raise ValueError("course_id 不能为空")
            assignment_in = assignment_in.model_copy(
                update={
                    "course_id": await self._resolve_course_id(
                        assignment_in.course_id,
                        assignment.teacher_id,
                    )
                }
            )
        # 更新接口支持局部字段变更，因此附件与步骤需要基于"新值优先、旧值兜底"的规则计算最终状态。
        next_attachments = (
            assignment_in.attachments
            if assignment_in.attachments is not None
            else assignment.attachments
        )
        next_instruction_steps = (
            assignment_in.instruction_steps
            if assignment_in.instruction_steps is not None
            else assignment.instruction_steps
        )
        await self._ensure_attachment_uploads_exist(
            attachments=next_attachments,
            instruction_steps=next_instruction_steps,
        )
        updated_assignment = await self.repo.update(assignment, assignment_in)
        # 仓储更新后再同步附件归属，避免旧附件关联未清理或新增附件未归档。
        await self._sync_attachment_uploads(
            updated_assignment.id,
            attachments=updated_assignment.attachments,
            instruction_steps=updated_assignment.instruction_steps,
        )
        await self._sync_reminder_plans(updated_assignment.id)
        return await self.get_assignment(updated_assignment.id)

    async def delete_assignment(self, id: str) -> bool:
        """
        功能描述：
            删除作业。

        参数：
            id (str): 目标记录ID。
        返回值：
            bool: 返回操作是否成功。
        """
        assignment = await self.repo.get(id)
        if not assignment:
            return False

        await self.repo.delete(assignment)
        return True

    async def transition_assignment(
        self,
        id: str,
        event: AssignmentTransitionEvent,
    ) -> Optional[AssignmentTransitionResponse]:
        """
        功能描述：
            流转作业。

        参数：
            id (str): 目标记录ID。
            event (AssignmentTransitionEvent): AssignmentTransitionEvent 类型的数据。
        返回值：
            Optional[AssignmentTransitionResponse]: 返回流转后的结果对象；未命中时返回 None。
        """
        assignment = await self.repo.get(id)
        if not assignment:
            return None
        from_status = AssignmentStatus(assignment.status)
        transition_result = self.state_machine.transition(from_status, event)
        assignment.status = transition_result.to_status
        await self.repo.commit_and_refresh(assignment)
        return AssignmentTransitionResponse(
            assignment=await self.get_assignment(assignment.id),
            from_status=transition_result.from_status,
            to_status=transition_result.to_status,
            event=transition_result.event,
        )

    async def reach_deadline_assignments(
        self,
        now: Optional[datetime] = None,
    ) -> int:
        """
        功能描述：
            触发截止时间作业。

        参数：
            now (Optional[datetime]): Optional[datetime] 类型的数据。
        返回值：
            int: 返回int类型的处理结果。
        """
        now = now or datetime.now()
        items = await self.repo.list_published_due(now)
        affected = 0
        for assignment in items:
            transition_result = self.state_machine.transition(
                AssignmentStatus(assignment.status),
                AssignmentTransitionEvent.REACH_DEADLINE,
            )
            assignment.status = transition_result.to_status
            affected += 1
        if affected:
            await self.repo.commit()
        return affected

    async def publish_assignment(
        self,
        id: str,
        sender_user_id: str,
    ) -> Optional[AssignmentActionResponse]:
        """
        功能描述：
            发布作业。

        参数：
            id (str): 目标记录ID。
            sender_user_id (str): 发送者用户ID。

        返回值：
            Optional[AssignmentActionResponse]: 返回处理结果对象；无可用结果时返回 None。
        """
        assignment = await self.repo.get(id)
        if not assignment:
            return None
        if not assignment.course_id:
            raise ValueError("作业必须绑定课程后才能发布")
        from_status = AssignmentStatus(assignment.status)
        if from_status != AssignmentStatus.PUBLISHED:
            # 已发布作业重复点击发布时不再重复流转状态，但仍会继续执行通知补发逻辑。
            transition_result = self.state_machine.transition(from_status, AssignmentTransitionEvent.PUBLISH)
            assignment.status = transition_result.to_status
            await self.repo.commit_and_refresh(assignment)
        notification = self.notification._build_publish_notification(assignment)
        # 通知人数需要按课程实际在班学生动态计算，不能直接用静态班级人数替代。
        affected = await self.notification.notify_students(
            sender_user_id=sender_user_id,
            payload=notification,
            assignment=assignment,
        )
        return AssignmentActionResponse(
            assignment=await self.get_assignment(assignment.id),
            action="publish",
            affected_students=affected,
        )

    async def delay_assignment(
        self,
        id: str,
        body: AssignmentDelayRequest,
        sender_user_id: str,
    ) -> Optional[AssignmentActionResponse]:
        """
        功能描述：
            延期处理作业。

        参数：
            id (str): 目标记录ID。
            body (AssignmentDelayRequest): 接口请求体对象。
            sender_user_id (str): 发送者用户ID。

        返回值：
            Optional[AssignmentActionResponse]: 返回处理结果对象；无可用结果时返回 None。
        """
        assignment = await self.repo.get(id)
        if not assignment:
            return None
        assignment.due_date = body.due_date
        if AssignmentStatus(assignment.status) in (AssignmentStatus.DEADLINE, AssignmentStatus.CLOSED):
            assignment.status = AssignmentStatus.PUBLISHED
        await self.repo.commit_and_refresh(assignment)
        await self._sync_reminder_plans(assignment.id)
        affected = 0
        if body.notify_students:
            notification = self.notification._build_delay_notification(assignment, body.reason)
            affected = await self.notification.notify_students(
                sender_user_id=sender_user_id,
                payload=notification,
                assignment=assignment,
            )
        return AssignmentActionResponse(
            assignment=await self.get_assignment(assignment.id),
            action="delay",
            affected_students=affected,
        )

    async def remind_assignment(
        self,
        id: str,
        body: AssignmentReminderRequest,
        sender_user_id: str,
    ) -> Optional[AssignmentActionResponse]:
        """
        功能描述：
            处理作业。

        参数：
            id (str): 目标记录ID。
            body (AssignmentReminderRequest): 接口请求体对象。
            sender_user_id (str): 发送者用户ID。

        返回值：
            Optional[AssignmentActionResponse]: 返回处理结果对象；无可用结果时返回 None。
        """
        assignment = await self.repo.get(id)
        if not assignment:
            return None
        notification = self.notification._build_reminder_notification(assignment, body)
        affected = await self.notification.notify_students(
            sender_user_id=sender_user_id,
            payload=notification,
            assignment=assignment,
        )
        return AssignmentActionResponse(
            assignment=await self.get_assignment(assignment.id),
            action="remind",
            affected_students=affected,
        )

    async def _resolve_assignment_filters(
        self,
        current_student_id: Optional[str],
        course_id: Optional[str],
    ) -> tuple[Optional[str], Optional[list[str]]]:
        if not current_student_id:
            return course_id, None
        accessible_course_ids = await self.course_repo.list_ids_for_student(current_student_id)
        if course_id:
            if course_id in accessible_course_ids:
                return course_id, None
            return None, []
        return course_id, accessible_course_ids

    async def _resolve_course_id(
        self,
        requested_course_id: Optional[str],
        teacher_id: str,
    ) -> str:
        if not requested_course_id:
            raise ValueError("course_id 为必填")
        course = await self.course_repo.get(requested_course_id)
        if not course or course.teacher_id != teacher_id:
            raise ValueError("课程不存在")
        return course.id

    async def _sync_reminder_plans(self, assignment_id: str) -> None:
        from app.services.assignment_reminder_service import AssignmentReminderService
        await AssignmentReminderService(self.repo.db).sync_plans_for_assignment(assignment_id)

    async def _ensure_attachment_uploads_exist(
        self,
        attachments: Optional[list] = None,
        instruction_steps: Optional[list] = None,
    ) -> None:
        attachment_ids = self._collect_attachment_ids(attachments, instruction_steps)
        if attachment_ids:
            service = AttachmentService(self.repo.db)
            for attachment_id in attachment_ids:
                attachment = await service.repo.get(attachment_id)
                if not attachment:
                    raise ValueError(f"附件不存在: {attachment_id}")

    async def _sync_attachment_uploads(
        self,
        assignment_id: str,
        attachments: Optional[list] = None,
        instruction_steps: Optional[list] = None,
    ) -> None:
        attachment_ids = self._collect_attachment_ids(attachments, instruction_steps)
        if attachment_ids:
            service = AttachmentService(self.repo.db)
            for attachment_id in attachment_ids:
                attachment = await service.repo.get(attachment_id)
                if attachment:
                    attachment.owner_id = assignment_id
                    await service.repo.save()

    @staticmethod
    def _collect_attachment_ids(
        attachments: Optional[list] = None,
        instruction_steps: Optional[list] = None,
    ) -> list[str]:
        attachment_ids: list[str] = []
        for item in attachments or []:
            attachment_id = item.id if hasattr(item, "id") else item.get("id")
            if attachment_id:
                attachment_ids.append(attachment_id)
        for step in instruction_steps or []:
            step_attachments = step.attachments if hasattr(step, "attachments") else step.get("attachments", [])
            for item in step_attachments or []:
                attachment_id = item.id if hasattr(item, "id") else item.get("id")
                if attachment_id:
                    attachment_ids.append(attachment_id)
        return attachment_ids

    @staticmethod
    def _to_response(item, custom_field_values: Optional[dict] = None) -> AssignmentResponse:
        character_ids = list(item.hanzi_ids or [])
        return AssignmentResponse(
            id=item.id,
            teacher_id=item.teacher_id,
            course_id=item.course_id,
            course_name=getattr(getattr(item, "course", None), "name", None),
            teaching_class_id=getattr(getattr(item, "course", None), "teaching_class_id", None),
            title=item.title,
            description=item.description,
            character_ids=character_ids,
            hanzi_ids=character_ids,
            instruction_steps=list(getattr(item, "instruction_steps", None) or []),
            attachments=list(getattr(item, "attachments", None) or []),
            due_date=item.due_date,
            status=item.status,
            custom_field_values=custom_field_values or {},
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
