"""
为什么这样做：课程查询把“权限过滤、分页、自定义字段补齐”集中处理，确保不同入口返回口径一致。
特殊逻辑：学生视角先算可访问课程集合，再重算 total，避免跨班课程被误计入分页边界。
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Course, CourseStatus
from app.models.teaching_class import TeachingClass, TeachingClassStatus
from app.repositories.course_repo import CourseRepository
from app.repositories.teaching_class_repo import TeachingClassRepository
from app.schemas.course import CourseCreate, CourseListResponse, CourseResponse, CourseUpdate
from app.services.custom_field_service import CustomFieldService
from app.utils.pagination import build_paged_response


class CourseService:
    def __init__(self, db: AsyncSession):
        """
        功能描述：
            初始化CourseService并准备运行所需的依赖对象。

        参数：
            db (AsyncSession): 数据库会话，用于执行持久化操作。

        返回值：
            None: 无返回值。
        """
        self.repo = CourseRepository(db)
        self.teaching_class_repo = TeachingClassRepository(db)

    async def get_course(
        self,
        id: str,
        management_system_id: str,
        current_user_role: str | None = None,
    ) -> CourseResponse | None:
        """
        功能描述：
            按条件获取课程。

        参数：
            id (str): 目标记录ID。
            management_system_id (str): 管理系统ID，用于限制数据作用域。
            current_user_role (str | None): 当前用户角色，用于控制权限或字段可见性。

        返回值：
            CourseResponse | None: 返回查询到的结果对象；未命中时返回 None。
        """
        item = await self.repo.get(id, management_system_id)
        if not item:
            return None
        custom_field_values = await CustomFieldService(self.repo.db).list_value_map(
            management_system_id,
            "course",
            item.id,
            viewer_role=current_user_role,
        )
        return self._to_response(item, custom_field_values=custom_field_values)

    async def list_courses(
        self,
        skip: int = 0,
        limit: int = 20,
        management_system_id: str | None = None,
        teaching_class_id: str | None = None,
        teacher_id: str | None = None,
        current_student_id: str | None = None,
        current_user_role: str | None = None,
        status: str | None = None,
        page: int | None = None,
        size: int | None = None,
    ) -> CourseListResponse:
        """
        功能描述：
            按条件查询课程列表。

        参数：
            skip (int): 分页偏移量。
            limit (int): 单次查询的最大返回数量。
            management_system_id (str | None): 管理系统ID，用于限制数据作用域。
            teaching_class_id (str | None): 教学班级ID。
            teacher_id (str | None): 教师ID。
            current_student_id (str | None): 当前学生ID。
            current_user_role (str | None): 当前用户角色，用于控制权限或字段可见性。
            status (str | None): 状态筛选条件或目标状态。
            page (int | None): 当前页码。
            size (int | None): 每页条数。

        返回值：
            CourseListResponse: 返回列表或分页查询结果。
        """
        if current_student_id and management_system_id and not teaching_class_id and not teacher_id:
            # 学生从“我的课程”入口访问时，先预判是否存在可访问课程，避免后续分页查询返回空页但 total 仍显示全量课程数。
            course_ids = await self.repo.list_ids_for_student(current_student_id, management_system_id)
            if not course_ids:
                payload = build_paged_response(
                    items=[],
                    total=0,
                    pagination={"page": page, "size": size, "skip": skip, "limit": limit},
                )
                return CourseListResponse(**payload)
        items = await self.repo.get_all(
            skip=skip,
            limit=limit,
            management_system_id=management_system_id,
            teaching_class_id=teaching_class_id,
            teacher_id=teacher_id,
            status=status,
        )
        if current_student_id and management_system_id:
            # 学生只能看到自己所在教学班关联的课程，这里在仓储查询结果上做二次过滤，保证不同筛选入口口径一致。
            accessible_course_ids = set(await self.repo.list_ids_for_student(current_student_id, management_system_id))
            items = [item for item in items if item.id in accessible_course_ids]
        total = await self.repo.count(
            management_system_id=management_system_id,
            teaching_class_id=teaching_class_id,
            teacher_id=teacher_id,
            status=status,
        )
        if current_student_id and management_system_id:
            # total 需要基于学生最终可访问的课程集合重算，否则会把无权限课程计入分页总数。
            total = len(set(await self.repo.list_ids_for_student(current_student_id, management_system_id)))
        custom_field_values_by_target = await CustomFieldService(self.repo.db).list_value_map_for_targets(
            management_system_id,
            "course",
            [item.id for item in items],
            viewer_role=current_user_role,
        ) if management_system_id else {}
        payload = build_paged_response(
            items=[
                self._to_response(item, custom_field_values=custom_field_values_by_target.get(item.id, {}))
                for item in items
            ],
            total=total,
            pagination={"page": page, "size": size, "skip": skip, "limit": limit},
        )
        return CourseListResponse(**payload)

    async def create_course(
        self,
        course_in: CourseCreate,
        teacher_id: str,
        management_system_id: str,
    ) -> CourseResponse:
        """
        功能描述：
            创建课程并返回结果。

        参数：
            course_in (CourseCreate): 课程输入对象。
            teacher_id (str): 教师ID。
            management_system_id (str): 管理系统ID，用于限制数据作用域。

        返回值：
            CourseResponse: 返回创建后的结果对象。
        """
        teaching_class = await self.teaching_class_repo.get(course_in.teaching_class_id, management_system_id)
        if not teaching_class:
            raise ValueError("教学班级不存在")
        item = await self.repo.create(course_in, teacher_id, management_system_id)
        await CustomFieldService(self.repo.db).upsert_value_map(
            management_system_id,
            "course",
            item.id,
            teacher_id,
            course_in.custom_field_values,
        )
        return await self.get_course(item.id, management_system_id)

    async def update_course(
        self,
        id: str,
        course_in: CourseUpdate,
        management_system_id: str,
    ) -> CourseResponse | None:
        """
        功能描述：
            更新课程并返回最新结果。

        参数：
            id (str): 目标记录ID。
            course_in (CourseUpdate): 课程输入对象。
            management_system_id (str): 管理系统ID，用于限制数据作用域。

        返回值：
            CourseResponse | None: 返回更新后的结果对象；未命中时返回 None。
        """
        item = await self.repo.get(id, management_system_id)
        if not item:
            return None
        if course_in.teaching_class_id:
            teaching_class = await self.teaching_class_repo.get(course_in.teaching_class_id, management_system_id)
            if not teaching_class:
                raise ValueError("教学班级不存在")
        updated = await self.repo.update(item, course_in)
        if course_in.custom_field_values is not None:
            await CustomFieldService(self.repo.db).upsert_value_map(
                management_system_id,
                "course",
                updated.id,
                updated.teacher_id,
                course_in.custom_field_values,
            )
        return await self.get_course(updated.id, management_system_id)

    async def ensure_default_course(self, management_system_id: str, teacher_id: str) -> Course:
        """
        功能描述：
            确保默认课程存在，必要时自动补齐。

        参数：
            management_system_id (str): 管理系统ID，用于限制数据作用域。
            teacher_id (str): 教师ID。

        返回值：
            Course: 返回Course类型的处理结果。
        """
        existing = await self.repo.get_default(management_system_id)
        if existing:
            return existing

        default_teaching_class = await self.teaching_class_repo.get_default(management_system_id)
        if not default_teaching_class:
            # 默认课程依赖默认教学班级，先补齐教学班级可以避免课程落在不存在的班级上。
            default_teaching_class = TeachingClass(
                management_system_id=management_system_id,
                teacher_id=teacher_id,
                name="默认教学班级",
                description="系统自动补建的默认教学班级",
                status=TeachingClassStatus.ACTIVE,
                is_default=True,
            )
            await self.teaching_class_repo.add(default_teaching_class)

        # 只有在确认默认教学班级可用后才创建默认课程，确保系统初始化后的课程链路完整可用。
        default_course = Course(
            management_system_id=management_system_id,
            teaching_class_id=default_teaching_class.id,
            teacher_id=teacher_id,
            name="默认课程",
            description="系统自动补建的默认课程",
            status=CourseStatus.ACTIVE,
            is_default=True,
        )
        await self.repo.add(default_course)
        await self.repo.save()
        await self.repo.refresh(default_course)
        return default_course

    @staticmethod
    def _to_response(item: Course, custom_field_values: dict | None = None) -> CourseResponse:
        """
        功能描述：
            将输入数据转换为响应。

        参数：
            item (Course): 当前处理的实体对象。
            custom_field_values (dict | None): 字典形式的结果数据。

        返回值：
            CourseResponse: 返回CourseResponse类型的处理结果。
        """
        return CourseResponse(
            id=item.id,
            management_system_id=item.management_system_id,
            teaching_class_id=item.teaching_class_id,
            teacher_id=item.teacher_id,
            name=item.name,
            code=item.code,
            description=item.description,
            status=item.status,
            custom_field_values=custom_field_values or {},
            is_default=item.is_default,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
