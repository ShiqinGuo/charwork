"""
为什么这样做：学生班级服务处理学生与班级的关系业务逻辑，包括加入班级、查询班级列表等。
特殊逻辑：加入班级时需要检查学生是否已加入和班级是否存在，确保数据一致性。
"""

from typing import Optional
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.submission import Submission
from app.repositories.student_class_repo import StudentClassRepository
from app.repositories.teaching_class_repo import TeachingClassRepository
from app.repositories.teacher_repo import TeacherRepository
from app.repositories.course_repo import CourseRepository
from app.repositories.assignment_repo import AssignmentRepository
from app.repositories.submission_repo import SubmissionRepository
from app.schemas.student_class import (
    StudentClassResponse,
    StudentClassListResponse,
    StudentClassJoinResponse,
)


class StudentClassService:
    def __init__(self, db: AsyncSession):
        """
        功能描述：
            初始化StudentClassService并准备运行所需的依赖对象。

        参数：
            db (AsyncSession): 数据库会话，用于执行持久化操作。

        返回值：
            None: 无返回值。
        """
        self.db = db
        self.student_class_repo = StudentClassRepository(db)
        self.teaching_class_repo = TeachingClassRepository(db)

    async def join_class(
        self, student_id: str, teaching_class_id: str
    ) -> StudentClassJoinResponse:
        """
        功能描述：
            学生加入班级。

        参数：
            student_id (str): 学生ID。
            teaching_class_id (str): 班级ID。

        返回值：
            StudentClassJoinResponse: 返回加入班级的响应对象。

        异常：
            ValueError: 学生已加入该班级或班级不存在时抛出。
        """
        # 检查学生是否已加入
        existing = await self.student_class_repo.get_by_student_and_class(
            student_id, teaching_class_id
        )
        if existing:
            raise ValueError("学生已加入该班级")

        # 检查班级是否存在
        teaching_class = await self.teaching_class_repo.get(teaching_class_id)
        if not teaching_class:
            raise ValueError("班级不存在")

        # 创建关系
        student_class = await self.student_class_repo.create(student_id, teaching_class_id)

        # 获取完整信息
        class_info = await self.student_class_repo.get_class_info_with_teacher(
            student_class.id
        )

        return StudentClassJoinResponse(
            id=student_class.id,
            teaching_class_id=class_info["teaching_class"].id,
            class_name=class_info["teaching_class"].name,
            teacher_name=class_info["teacher_name"],
            joined_at=student_class.joined_at,
            status=student_class.status,
        )

    async def list_student_classes(
        self, student_id: str, skip: int = 0, limit: int = 20
    ) -> StudentClassListResponse:
        """
        功能描述：
            获取学生加入的班级列表。

        参数：
            student_id (str): 学生ID。
            skip (int): 分页偏移量。
            limit (int): 单次查询的最大返回数量。

        返回值：
            StudentClassListResponse: 返回班级列表响应对象。
        """
        items, total = await self.student_class_repo.list_by_student(
            student_id, skip, limit
        )
        return StudentClassListResponse(
            total=total,
            items=[StudentClassResponse.model_validate(item) for item in items],
        )

    async def get_student_class(
        self, student_class_id: str
    ) -> Optional[StudentClassResponse]:
        """
        功能描述：
            获取学生班级关系详情。

        参数：
            student_class_id (str): 学生班级关系ID。

        返回值：
            Optional[StudentClassResponse]: 返回学生班级关系响应对象；未找到时返回 None。
        """
        student_class = await self.student_class_repo.get(student_class_id)
        return (
            StudentClassResponse.model_validate(student_class)
            if student_class
            else None
        )

    async def get_class_detail(
        self, student_id: str, teaching_class_id: str
    ) -> dict:
        """
        功能描述：
            获取班级详情。

        参数：
            student_id (str): 学生ID。
            teaching_class_id (str): 班级ID。

        返回值：
            dict: 返回包含班级详情的字典。

        异常：
            ValueError: 学生未加入该班级时抛出。
        """
        # 验证学生已加入班级
        student_class = await self.student_class_repo.get_by_student_and_class(
            student_id, teaching_class_id
        )
        if not student_class:
            raise ValueError("学生未加入该班级")

        # 获取班级信息
        teaching_class = await self.teaching_class_repo.get(teaching_class_id)
        if not teaching_class:
            raise ValueError("班级不存在")

        # 获取教师信息
        teacher_repo = TeacherRepository(self.db)
        teacher = await teacher_repo.get(teaching_class.teacher_id)
        if not teacher:
            raise ValueError("教师不存在")

        return {
            "id": teaching_class.id,
            "name": teaching_class.name,
            "description": teaching_class.description,
            "teacher_id": teacher.id,
            "teacher_name": teacher.name,
            "member_count": 0,  # TODO: 实现成员计数
            "assignment_count": 0,  # TODO: 实现作业计数
            "joined_at": student_class.joined_at,
            "status": student_class.status,
        }

    async def get_class_members(
        self, student_id: str, teaching_class_id: str, skip: int = 0, limit: int = 20
    ) -> dict:
        """
        功能描述：
            获取班级成员列表。

        参数：
            student_id (str): 学生ID。
            teaching_class_id (str): 班级ID。
            skip (int): 分页偏移量。
            limit (int): 单次查询的最大返回数量。

        返回值：
            dict: 返回包含成员列表的字典。

        异常：
            ValueError: 学生未加入该班级时抛出。
        """
        # 验证学生已加入班级
        student_class = await self.student_class_repo.get_by_student_and_class(
            student_id, teaching_class_id
        )
        if not student_class:
            raise ValueError("学生未加入该班级")

        # 查询班级成员
        items, total = await self.student_class_repo.list_class_members(
            teaching_class_id, skip, limit
        )

        return {
            "total": total,
            "items": items,
        }

    async def get_class_assignments(
        self, student_id: str, teaching_class_id: str, status: Optional[str] = None, skip: int = 0, limit: int = 20
    ) -> dict:
        """
        功能描述：
            获取班级作业列表。

        参数：
            student_id (str): 学生ID。
            teaching_class_id (str): 班级ID。
            status (Optional[str]): 作业状态筛选。
            skip (int): 分页偏移量。
            limit (int): 单次查询的最大返回数量。

        返回值：
            dict: 返回包含作业列表的字典。

        异常：
            ValueError: 学生未加入该班级时抛出。
        """
        # 验证学生已加入班级
        student_class = await self.student_class_repo.get_by_student_and_class(
            student_id, teaching_class_id
        )
        if not student_class:
            raise ValueError("学生未加入该班级")

        # 获取班级的所有课程
        course_repo = CourseRepository(self.db)
        courses = await course_repo.list_by_teaching_class(teaching_class_id)
        course_ids = [course.id for course in courses]

        # 查询班级的所有作业
        assignment_repo = AssignmentRepository(self.db)
        assignments = await assignment_repo.get_all(
            skip=skip,
            limit=limit,
            course_ids=course_ids,
            status=status,
        )
        total = await assignment_repo.count(
            course_ids=course_ids,
            status=status,
        )

        # 获取学生的提交状态
        submission_repo = SubmissionRepository(self.db)
        items = []
        for assignment in assignments:
            submission = await submission_repo.get_all_by_assignment(
                assignment.id,
                student_id=student_id,
                limit=1,
            )
            submission_status = "not_submitted"
            submission_id = None
            if submission:
                submission_obj = submission[0]
                submission_id = submission_obj.id
                submission_status = submission_obj.status

            items.append({
                "id": assignment.id,
                "title": assignment.title,
                "description": assignment.description,
                "deadline": assignment.due_date,
                "created_at": assignment.created_at,
                "submission_status": submission_status,
                "submission_id": submission_id,
            })

        return {
            "total": total,
            "items": items,
        }

    async def get_assignment_detail(
        self, student_id: str, assignment_id: str
    ) -> dict:
        """
        功能描述：
            获取作业详情。

        参数：
            student_id (str): 学生ID。
            assignment_id (str): 作业ID。

        返回值：
            dict: 返回包含作业详情的字典。

        异常：
            ValueError: 作业不存在或学生未加入该班级时抛出。
        """
        # 获取作业信息
        assignment_repo = AssignmentRepository(self.db)
        assignment = await assignment_repo.get(assignment_id)
        if not assignment:
            raise ValueError("作业不存在")

        # 验证学生已加入该作业所属班级
        course = assignment.course
        if not course:
            raise ValueError("作业不存在")

        teaching_class_id = course.teaching_class_id
        student_class = await self.student_class_repo.get_by_student_and_class(
            student_id, teaching_class_id
        )
        if not student_class:
            raise ValueError("学生未加入该班级")

        # 查询学生对该作业的提交
        submission_repo = SubmissionRepository(self.db)
        submissions = await submission_repo.get_all_by_assignment(
            assignment_id,
            student_id=student_id,
            limit=1,
        )

        submission_data = None
        if submissions:
            submission = submissions[0]
            submission_data = {
                "id": submission.id,
                "status": submission.status,
                "submitted_at": submission.submitted_at,
                "content": submission.content,
                "score": submission.score,
            }

        return {
            "id": assignment.id,
            "title": assignment.title,
            "description": assignment.description,
            "requirements": assignment.instruction_steps,
            "deadline": assignment.due_date,
            "created_at": assignment.created_at,
            "attachments": [],  # TODO
            "submission": submission_data,
        }

    async def get_student_submissions(
        self, student_id: str, class_id: Optional[str] = None, skip: int = 0, limit: int = 20
    ) -> dict:
        """
        功能描述：
            查询学生的所有提交。

        参数：
            student_id (str): 学生ID。
            class_id (Optional[str]): 班级ID，如果指定则只查询该班级的提交。
            skip (int): 分页偏移量。
            limit (int): 单次查询的最大返回数量。

        返回值：
            dict: 返回包含提交列表的字典。

        异常：
            ValueError: 学生未加入指定班级时抛出。
        """
        submission_repo = SubmissionRepository(self.db)
        course_repo = CourseRepository(self.db)
        assignment_repo = AssignmentRepository(self.db)

        # 如果指定了班级，验证学生已加入该班级
        course_ids = None
        if class_id:
            student_class = await self.student_class_repo.get_by_student_and_class(
                student_id, class_id
            )
            if not student_class:
                raise ValueError("学生未加入该班级")

            # 获取该班级的所有课程
            courses = await course_repo.list_by_teaching_class(class_id)
            course_ids = [course.id for course in courses]

        # 查询学生的提交
        if course_ids:
            # 按课程ID过滤
            assignments = await assignment_repo.get_all(
                skip=skip,
                limit=limit,
                course_ids=course_ids,
            )
            total = await assignment_repo.count(course_ids=course_ids)
        else:
            # 查询所有提交
            query = select(Submission).where(Submission.student_id == student_id)
            result = await self.db.execute(
                query.order_by(desc(Submission.submitted_at)).offset(skip).limit(limit)
            )
            submissions = result.scalars().all()

            # 统计总数
            count_query = select(func.count()).select_from(Submission).where(
                Submission.student_id == student_id
            )
            count_result = await self.db.execute(count_query)
            total = count_result.scalar()

            # 构建返回数据
            items = []
            for submission in submissions:
                assignment = submission.assignment
                course = assignment.course if assignment else None
                teaching_class = course.teaching_class if course else None

                items.append({
                    "id": submission.id,
                    "assignment_id": assignment.id if assignment else None,
                    "assignment_title": assignment.title if assignment else None,
                    "class_name": teaching_class.name if teaching_class else None,
                    "submitted_at": submission.submitted_at,
                    "status": submission.status,
                    "score": submission.score,
                })

            return {
                "total": total,
                "items": items,
            }

        # 构建返回数据（当指定班级时）
        items = []
        for assignment in assignments:
            submissions = await submission_repo.get_all_by_assignment(
                assignment.id,
                student_id=student_id,
                limit=1,
            )

            if submissions:
                submission = submissions[0]
                course = assignment.course
                teaching_class = course.teaching_class if course else None

                items.append({
                    "id": submission.id,
                    "assignment_id": assignment.id,
                    "assignment_title": assignment.title,
                    "class_name": teaching_class.name if teaching_class else None,
                    "submitted_at": submission.submitted_at,
                    "status": submission.status,
                    "score": submission.score,
                })

        return {
            "total": total,
            "items": items,
        }

    async def get_submission_detail(
        self, student_id: str, submission_id: str
    ) -> dict:
        """
        功能描述：
            获取提交详情。

        参数：
            student_id (str): 学生ID。
            submission_id (str): 提交ID。

        返回值：
            dict: 返回包含提交详情的字典。

        异常：
            ValueError: 提交不存在或无权限访问时抛出。
        """
        submission_repo = SubmissionRepository(self.db)
        submission = await submission_repo.get(submission_id)

        if not submission:
            raise ValueError("提交不存在")

        # 验证是学生自己的提交
        if submission.student_id != student_id:
            raise ValueError("无权限访问")

        # 获取作业和班级信息
        assignment = submission.assignment
        course = assignment.course if assignment else None
        teaching_class = course.teaching_class if course else None

        return {
            "id": submission.id,
            "assignment_id": assignment.id if assignment else None,
            "assignment_title": assignment.title if assignment else None,
            "class_name": teaching_class.name if teaching_class else None,
            "submitted_at": submission.submitted_at,
            "status": submission.status,
            "content": submission.content,
            "attachments": [],  # TODO
            "score": submission.score,
            "graded_at": submission.graded_at,
        }

    async def get_ai_feedback(
        self, student_id: str, submission_id: str
    ) -> dict:
        """
        功能描述：
            获取 AI 反馈。

        参数：
            student_id (str): 学生ID。
            submission_id (str): 提交ID。

        返回值：
            dict: 返回包含 AI 反馈的字典。

        异常：
            ValueError: 提交不存在、无权限访问或反馈不存在时抛出。
        """
        submission_repo = SubmissionRepository(self.db)
        submission = await submission_repo.get(submission_id)

        if not submission:
            raise ValueError("提交不存在")

        # 验证是学生自己的提交
        if submission.student_id != student_id:
            raise ValueError("无权限访问")

        # 获取 AI 反馈
        if not submission.ai_feedback:
            raise ValueError("反馈不存在")

        return {
            "id": submission.id,
            "submission_id": submission_id,
            "feedback": submission.ai_feedback,
            "created_at": submission.submitted_at,
            "model": "claude",  # TODO: 从配置或反馈数据中获取
        }

    async def get_teacher_feedback(
        self, student_id: str, submission_id: str
    ) -> dict:
        """
        功能描述：
            获取教师反馈。

        参数：
            student_id (str): 学生ID。
            submission_id (str): 提交ID。

        返回值：
            dict: 返回包含教师反馈的字典。

        异常：
            ValueError: 提交不存在、无权限访问或反馈不存在时抛出。
        """
        submission_repo = SubmissionRepository(self.db)
        submission = await submission_repo.get(submission_id)

        if not submission:
            raise ValueError("提交不存在")

        # 验证是学生自己的提交
        if submission.student_id != student_id:
            raise ValueError("无权限访问")

        # 获取教师反馈
        if not submission.teacher_feedback:
            raise ValueError("反馈不存在")

        return {
            "id": submission.id,
            "submission_id": submission_id,
            "feedback": submission.teacher_feedback,
            "score": submission.score,
            "graded_at": submission.graded_at,
            "teacher_name": None,  # TODO: 从教师表中获取
        }
