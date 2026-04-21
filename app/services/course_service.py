"""
为什么这样做：课程查询把“权限过滤、分页、自定义字段补齐”集中处理，确保不同入口返回口径一致。
特殊逻辑：学生视角先算可访问课程集合，再重算 total，避免跨班课程被误计入分页边界。
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Course
from app.repositories.course_repo import CourseRepository
from app.repositories.teaching_class_repo import TeachingClassRepository
from app.schemas.course import CourseCreate, CourseListResponse, CourseResponse, CourseUpdate
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
    ) -> CourseResponse | None:
        """
        功能描述：
            按条件获取课程。

        参数：
            id (str): 目标记录ID。
        返回值：
            CourseResponse | None: 返回查询到的结果对象；未命中时返回 None。
        """
        item = await self.repo.get(id)
        if not item:
            return None
        return self._to_response(item)

    async def list_courses(
        self,
        skip: int = 0,
        limit: int = 20,
        teaching_class_id: str | None = None,
        teacher_id: str | None = None,
        current_student_id: str | None = None,
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
            teaching_class_id (str | None): 教学班级ID。
            teacher_id (str | None): 教师ID。
            current_student_id (str | None): 当前学生ID。
            status (str | None): 状态筛选条件或目标状态。
            page (int | None): 当前页码。
            size (int | None): 每页条数。

        返回值：
            CourseListResponse: 返回列表或分页查询结果。
        """
        if current_student_id and not teaching_class_id and not teacher_id:
            # 学生从“我的课程”入口访问时，先预判是否存在可访问课程，避免后续分页查询返回空页但 total 仍显示全量课程数。
            course_ids = await self.repo.list_ids_for_student(current_student_id)
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
            teaching_class_id=teaching_class_id,
            teacher_id=teacher_id,
            status=status,
        )
        if current_student_id:
            # 学生只能看到自己所在教学班关联的课程，这里在仓储查询结果上做二次过滤，保证不同筛选入口口径一致。
            accessible_course_ids = set(await self.repo.list_ids_for_student(current_student_id))
            items = [item for item in items if item.id in accessible_course_ids]
        total = await self.repo.count(
            teaching_class_id=teaching_class_id,
            teacher_id=teacher_id,
            status=status,
        )
        if current_student_id:
            # total 需要基于学生最终可访问的课程集合重算，否则会把无权限课程计入分页总数。
            total = len(set(await self.repo.list_ids_for_student(current_student_id)))
        payload = build_paged_response(
            items=[
                self._to_response(item)
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
    ) -> CourseResponse:
        """
        功能描述：
            创建课程并返回结果。

        参数：
            course_in (CourseCreate): 课程输入对象。
            teacher_id (str): 教师ID。
        返回值：
            CourseResponse: 返回创建后的结果对象。
        """
        teaching_class = await self.teaching_class_repo.get(course_in.teaching_class_id)
        if not teaching_class:
            raise ValueError("教学班级不存在")
        if teaching_class.teacher_id != teacher_id:
            raise ValueError("仅可为本人教学班级创建课程")
        item = await self.repo.create(course_in, teacher_id)
        return await self.get_course(item.id)

    async def update_course(
        self,
        id: str,
        course_in: CourseUpdate,
    ) -> CourseResponse | None:
        """
        功能描述：
            更新课程并返回最新结果。

        参数：
            id (str): 目标记录ID。
            course_in (CourseUpdate): 课程输入对象。
        返回值：
            CourseResponse | None: 返回更新后的结果对象；未命中时返回 None。
        """
        item = await self.repo.get(id)
        if not item:
            return None
        if course_in.teaching_class_id:
            teaching_class = await self.teaching_class_repo.get(course_in.teaching_class_id)
            if not teaching_class:
                raise ValueError("教学班级不存在")
            if teaching_class.teacher_id != item.teacher_id:
                raise ValueError("仅可绑定本人教学班级")
        updated = await self.repo.update(item, course_in)
        return await self.get_course(updated.id)

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
