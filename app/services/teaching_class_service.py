"""
为什么这样做：教学班服务把“班级、成员、扫码入班”收敛在一个事务边界内，保证加入动作与权限链接一致。
特殊逻辑：令牌状态按过期/次数/禁用顺序判定，先处理边界态再执行入班，避免重复或越权加入。
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.teaching_class import (
    TeachingClass,
    TeachingClassJoinToken,
    TeachingClassJoinTokenStatus,
    TeachingClassMember,
    TeachingClassMemberStatus,
)
from app.models.user import User
from app.repositories.course_repo import CourseRepository
from app.repositories.student_class_repo import StudentClassRepository
from app.repositories.teaching_class_repo import TeachingClassRepository
from app.schemas.course import CourseSummary
from app.schemas.teaching_class import (
    TeachingClassCreate,
    TeachingClassJoinConfirmResponse,
    TeachingClassJoinPreviewResponse,
    TeachingClassJoinTokenCreate,
    TeachingClassJoinTokenResponse,
    TeachingClassListResponse,
    TeachingClassMemberListResponse,
    TeachingClassMemberResponse,
    TeachingClassResponse,
)
from app.utils.pagination import build_paged_response


class TeachingClassService:
    def __init__(self, db: AsyncSession):
        """
        功能描述：
            初始化TeachingClassService并准备运行所需的依赖对象。

        参数：
            db (AsyncSession): 数据库会话，用于执行持久化操作。

        返回值：
            None: 无返回值。
        """
        self.db = db
        self.repo = TeachingClassRepository(db)
        self.course_repo = CourseRepository(db)
        self.student_class_repo = StudentClassRepository(db)

    async def get_teaching_class(self, id: str) -> TeachingClassResponse | None:
        """
        功能描述：
            按条件获取教学班级。

        参数：
            id (str): 目标记录ID。
        返回值：
            TeachingClassResponse | None: 返回查询到的结果对象；未命中时返回 None。
        """
        item = await self.repo.get(id)
        if not item:
            return None
        return self._to_response(item)

    async def list_teaching_classes(
        self,
        skip: int = 0,
        limit: int = 20,
        teacher_id: str | None = None,
        status: str | None = None,
        page: int | None = None,
        size: int | None = None,
    ) -> TeachingClassListResponse:
        """
        功能描述：
            按条件查询教学班级列表。

        参数：
            skip (int): 分页偏移量。
            limit (int): 单次查询的最大返回数量。
            teacher_id (str | None): 教师ID。
            status (str | None): 状态筛选条件或目标状态。
            page (int | None): 当前页码。
            size (int | None): 每页条数。

        返回值：
            TeachingClassListResponse: 返回列表或分页查询结果。
        """
        items = await self.repo.get_all(
            skip=skip,
            limit=limit,
            teacher_id=teacher_id,
            status=status,
        )
        total = await self.repo.count(
            teacher_id=teacher_id,
            status=status,
        )
        payload = build_paged_response(
            items=[self._to_response(item) for item in items],
            total=total,
            pagination={"page": page, "size": size, "skip": skip, "limit": limit},
        )
        return TeachingClassListResponse(**payload)

    async def create_teaching_class(
        self,
        body: TeachingClassCreate,
        teacher_id: str,
    ) -> TeachingClassResponse:
        """
        功能描述：
            创建教学班级并返回结果。

        参数：
            body (TeachingClassCreate): 接口请求体对象。
            teacher_id (str): 教师ID。
        返回值：
            TeachingClassResponse: 返回创建后的结果对象。
        """
        item = TeachingClass(
            teacher_id=teacher_id,
            name=body.name,
            description=body.description,
            status=body.status,
            is_default=False,
        )
        created = await self.repo.create(item)
        # repo.create 不 eager load 关系，需重新查询以避免 async lazy load 报错
        reloaded = await self.repo.get(created.id)
        return self._to_response(reloaded)

    async def list_members(self, teaching_class_id: str) -> TeachingClassMemberListResponse:
        """
        功能描述：
            按条件查询members列表。

        参数：
            teaching_class_id (str): 教学班级ID。
        返回值：
            TeachingClassMemberListResponse: 返回列表或分页查询结果。
        """
        teaching_class = await self.repo.get(teaching_class_id)
        if not teaching_class:
            raise ValueError("教学班级不存在")
        items = await self.repo.list_members(teaching_class_id)
        return TeachingClassMemberListResponse(
            total=len(items),
            items=[self._to_member_response(item) for item in items],
        )

    async def create_join_token(
        self,
        teaching_class_id: str,
        teacher_id: str,
        body: TeachingClassJoinTokenCreate,
    ) -> TeachingClassJoinTokenResponse:
        """
        功能描述：
            创建加入令牌并返回结果。

        参数：
            teaching_class_id (str): 教学班级ID。
            teacher_id (str): 教师ID。
            body (TeachingClassJoinTokenCreate): 接口请求体对象。

        返回值：
            TeachingClassJoinTokenResponse: 返回创建后的结果对象。
        """
        teaching_class = await self.repo.get(teaching_class_id)
        if not teaching_class:
            raise ValueError("教学班级不存在")
        if teaching_class.teacher_id != teacher_id:
            raise ValueError("仅可为本人教学班级创建加入令牌")
        item = TeachingClassJoinToken(
            teaching_class_id=teaching_class_id,
            created_by_teacher_id=teacher_id,
            token=uuid4().hex,
            title=body.title,
            expires_at=body.expires_at,
            max_uses=body.max_uses,
        )
        await self.repo.add(item)
        await self.repo.save()
        await self.repo.refresh(item)
        return TeachingClassJoinTokenResponse.model_validate(item)

    async def preview_join(self, token: str, current_user: User,
                           current_student_id: str) -> TeachingClassJoinPreviewResponse:
        """
        功能描述：
            处理加入。

        参数：
            token (str): 令牌字符串。
            current_user (User): 当前登录用户对象。
            current_student_id (str): 当前学生ID。

        返回值：
            TeachingClassJoinPreviewResponse: 返回TeachingClassJoinPreviewResponse类型的处理结果。
        """
        token_item = await self.repo.get_join_token_by_value(token)
        if not token_item:
            raise ValueError("二维码令牌不存在")
        teaching_class = await self.repo.get(token_item.teaching_class_id)
        existing_member = await self.repo.get_member(token_item.teaching_class_id, current_student_id)
        courses = await self.course_repo.list_by_teaching_class(token_item.teaching_class_id)
        token_status = self._resolve_token_status(token_item)
        # 预览接口同时返回“能否加入”和“为何不能加入”的组合信息，前端据此决定展示加入按钮还是状态提示。
        can_join = token_status == TeachingClassJoinTokenStatus.ACTIVE and existing_member is None
        if teaching_class is None:
            raise ValueError("教学班级不存在")
        teaching_class_response = self._to_response(teaching_class)
        return TeachingClassJoinPreviewResponse(
            token_status=token_status,
            can_join=can_join,
            already_joined=existing_member is not None,
            expires_at=token_item.expires_at,
            teaching_class=teaching_class_response,
            courses=[self._to_course_summary(item) for item in courses],
            member=self._to_member_response(existing_member) if existing_member else None,
        )

    async def confirm_join(self, token: str, current_user: User,
                           current_student_id: str) -> TeachingClassJoinConfirmResponse:
        """
        功能描述：
            确认加入。

        参数：
            token (str): 令牌字符串。
            current_user (User): 当前登录用户对象。
            current_student_id (str): 当前学生ID。

        返回值：
            TeachingClassJoinConfirmResponse: 返回TeachingClassJoinConfirmResponse类型的处理结果。
        """
        token_item = await self.repo.get_join_token_by_value(token)
        if not token_item:
            raise ValueError("二维码令牌不存在")
        teaching_class = await self.repo.get(token_item.teaching_class_id)
        if teaching_class is None:
            raise ValueError("教学班级不存在")

        existing_member = await self.repo.get_member(token_item.teaching_class_id, current_student_id)
        if existing_member:
            courses = await self.course_repo.list_by_teaching_class(token_item.teaching_class_id)
            # 已经加入过同一教学班时直接返回现有成员关系，保证重复扫码是幂等操作。
            return TeachingClassJoinConfirmResponse(
                joined=False,
                teaching_class=self._to_response(teaching_class),
                courses=[self._to_course_summary(item) for item in courses],
                member=self._to_member_response(existing_member),
            )

        token_status = self._resolve_token_status(token_item)
        if token_status == TeachingClassJoinTokenStatus.EXPIRED:
            raise ValueError("二维码令牌已过期")
        if token_status == TeachingClassJoinTokenStatus.USED_UP:
            raise ValueError("二维码令牌已达到使用上限")
        if token_status != TeachingClassJoinTokenStatus.ACTIVE:
            raise ValueError("二维码令牌不可用")

        # 通过二维码加入时会显式记录来源令牌，方便后续追踪使用次数与学生加入来源。
        member = TeachingClassMember(
            teaching_class_id=token_item.teaching_class_id,
            student_id=current_student_id,
            joined_by_token_id=token_item.id,
            status=TeachingClassMemberStatus.ACTIVE,
        )
        await self.repo.add(member)

        token_item.used_count += 1
        token_item.last_used_at = datetime.now()
        await self.repo.save()
        await self.repo.refresh(member)

        # 同步写入 StudentClass，保证学生端"我的班级"列表能查到该班级。
        # 用 get_by_student_and_class 做幂等检查，避免唯一约束冲突。
        existing_sc = await self.student_class_repo.get_by_student_and_class(
            current_student_id, token_item.teaching_class_id
        )
        if not existing_sc:
            await self.student_class_repo.create(current_student_id, token_item.teaching_class_id)

        courses = await self.course_repo.list_by_teaching_class(token_item.teaching_class_id)
        return TeachingClassJoinConfirmResponse(
            joined=True,
            teaching_class=self._to_response(teaching_class),
            courses=[self._to_course_summary(item) for item in courses],
            member=self._to_member_response(member),
        )

    @staticmethod
    def _resolve_token_status(token_item: TeachingClassJoinToken) -> TeachingClassJoinTokenStatus:
        """
        功能描述：
            解析令牌状态。

        参数：
            token_item (TeachingClassJoinToken): 令牌字符串。

        返回值：
            TeachingClassJoinTokenStatus: 返回TeachingClassJoinTokenStatus类型的处理结果。
        """
        if token_item.status != TeachingClassJoinTokenStatus.ACTIVE:
            return TeachingClassJoinTokenStatus.DISABLED
        if token_item.expires_at and token_item.expires_at < datetime.now():
            return TeachingClassJoinTokenStatus.EXPIRED
        if token_item.max_uses is not None and token_item.used_count >= token_item.max_uses:
            return TeachingClassJoinTokenStatus.USED_UP
        return TeachingClassJoinTokenStatus.ACTIVE

    @staticmethod
    def _to_course_summary(item) -> CourseSummary:
        """
        功能描述：
            将输入数据转换为课程summary。

        参数：
            item (Any): 当前处理的实体对象。

        返回值：
            CourseSummary: 返回CourseSummary类型的处理结果。
        """
        return CourseSummary(
            id=item.id,
            name=item.name,
            code=item.code,
            status=item.status,
            is_default=item.is_default,
        )

    @staticmethod
    def _to_member_response(item: TeachingClassMember) -> TeachingClassMemberResponse:
        """
        功能描述：
            将输入数据转换为member响应。

        参数：
            item (TeachingClassMember): 当前处理的实体对象。

        返回值：
            TeachingClassMemberResponse: 返回TeachingClassMemberResponse类型的处理结果。
        """
        return TeachingClassMemberResponse(
            id=item.id,
            teaching_class_id=item.teaching_class_id,
            student_id=item.student_id,
            student_name=item.student.name if getattr(item, "student", None) else None,
            joined_by_token_id=item.joined_by_token_id,
            status=item.status,
            joined_at=item.joined_at,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )

    @staticmethod
    def _to_response(item: TeachingClass) -> TeachingClassResponse:
        """
        功能描述：
            将输入数据转换为响应。

        参数：
            item (TeachingClass): 当前处理的实体对象。

        返回值：
            TeachingClassResponse: 返回TeachingClassResponse类型的处理结果。
        """
        return TeachingClassResponse(
            id=item.id,
            teacher_id=item.teacher_id,
            name=item.name,
            description=item.description,
            status=item.status,
            is_default=item.is_default,
            member_count=len(item.members or []),
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
