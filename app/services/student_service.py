"""
为什么这样做：学生服务保持最小职责，仅做仓储调用与响应转换，便于后续按域扩展校验逻辑。
特殊逻辑：删除接口改为移除学生与教学班的关联，而非物理删除学生记录。
"""

from app.core.redis_client import get_redis
from app.repositories.student_repo import StudentRepository
from app.repositories.teaching_class_repo import TeachingClassRepository
from app.schemas.student import StudentCreate, StudentUpdate, StudentResponse
from app.utils.redis_cache import build_cache_key, cache_delete


class StudentService:
    def __init__(self, db):
        """
        功能描述：
            初始化StudentService并准备运行所需的依赖对象。
        """
        self.db = db
        self.repo = StudentRepository(db)
        self.teaching_class_repo = TeachingClassRepository(db)

    async def get_student(self, id: str) -> StudentResponse | None:
        """按 ID 获取学生。"""
        student = await self.repo.get(id)
        return StudentResponse.model_validate(student) if student else None

    async def list_students(self, skip: int = 0, limit: int = 20) -> dict:
        """查询全部学生列表（管理员接口，保留兼容）。"""
        items = await self.repo.get_all(skip, limit)
        total = await self.repo.count()
        return {
            "total": total,
            "items": [StudentResponse.model_validate(i) for i in items],
        }

    async def list_students_by_teacher(
        self, teacher_id: str, skip: int = 0, limit: int = 20
    ) -> dict:
        """
        只返回当前教师教学班中的学生。
        """
        student_ids = await self.teaching_class_repo.list_student_ids_for_teacher(teacher_id)
        if not student_ids:
            return {"total": 0, "items": []}
        items = await self.repo.get_by_ids(student_ids, skip, limit)
        total = len(student_ids)
        return {
            "total": total,
            "items": [StudentResponse.model_validate(i) for i in items],
        }

    async def is_student_in_teacher_class(
        self, student_id: str, teacher_id: str
    ) -> bool:
        """校验学生是否属于当前教师的教学班。"""
        class_student_ids = await self.teaching_class_repo.list_student_ids_for_teacher(teacher_id)
        return student_id in class_student_ids

    async def create_student(self, student_in: StudentCreate) -> StudentResponse:
        """创建学生并加入指定教学班。"""
        student = await self.repo.create(student_in)
        return StudentResponse.model_validate(student)

    async def update_student(
        self, id: str, student_in: StudentUpdate
    ) -> StudentResponse | None:
        """更新学生资料。"""
        student = await self.repo.get(id)
        if not student:
            return None
        student = await self.repo.update(student, student_in)
        await cache_delete(get_redis(), build_cache_key("profile:student", student.user_id))
        return StudentResponse.model_validate(student)

    async def remove_student_from_class(
        self, student_id: str, teacher_id: str
    ) -> bool:
        """
        将学生从教师的所有教学班中移除（解除关联，不删除学生记录）。
        返回是否至少从某个班级中成功移除。
        """
        class_student_ids = await self.teaching_class_repo.list_student_ids_for_teacher(teacher_id)
        if student_id not in class_student_ids:
            return False
        teaching_classes = await self.teaching_class_repo.get_all(teacher_id=teacher_id)
        removed = False
        for tc in teaching_classes:
            if await self.teaching_class_repo.remove_member(tc.id, student_id):
                removed = True
        return removed
