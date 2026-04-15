import os
import unittest
from datetime import datetime
from unittest.mock import AsyncMock, patch

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("MYSQL_HOST", "localhost")
os.environ.setdefault("MYSQL_PORT", "3306")
os.environ.setdefault("MYSQL_USER", "root")
os.environ.setdefault("MYSQL_PASSWORD", "root")
os.environ.setdefault("MYSQL_DB", "charwork")

SQLALCHEMY_READY = True

try:
    from app.schemas.student_class import StudentClassJoinResponse
    from app.services.student_class_service import StudentClassService
except ModuleNotFoundError:
    SQLALCHEMY_READY = False


if SQLALCHEMY_READY:

    class StudentClassServiceTests(unittest.IsolatedAsyncioTestCase):
        async def test_join_class_success(self):
            """测试学生成功加入班级"""
            from types import SimpleNamespace

            service = StudentClassService(AsyncMock())

            # 模拟学生班级关系
            student_class = SimpleNamespace(
                id="sc-1",
                student_id="stu-1",
                teaching_class_id="class-1",
                status="active",
                joined_at=datetime(2026, 4, 15, 10, 0, 0),
                created_at=datetime(2026, 4, 15, 10, 0, 0),
                updated_at=datetime(2026, 4, 15, 10, 0, 0),
            )

            # 模拟班级信息
            teaching_class = SimpleNamespace(
                id="class-1",
                name="一年级一班",
            )

            # 模拟教师信息
            teacher = SimpleNamespace(
                id="teacher-1",
                name="张老师",
            )

            # 设置 mock
            service.student_class_repo.get_by_student_and_class = AsyncMock(return_value=None)
            service.teaching_class_repo.get = AsyncMock(return_value=teaching_class)
            service.student_class_repo.create = AsyncMock(return_value=student_class)
            service.student_class_repo.get_class_info_with_teacher = AsyncMock(
                return_value={
                    "teaching_class": teaching_class,
                    "teacher_name": "张老师",
                }
            )

            result = await service.join_class("stu-1", "class-1")

            self.assertIsInstance(result, StudentClassJoinResponse)
            self.assertEqual(result.id, "sc-1")
            self.assertEqual(result.teaching_class_id, "class-1")
            self.assertEqual(result.class_name, "一年级一班")
            self.assertEqual(result.teacher_name, "张老师")
            self.assertEqual(result.status, "active")

        async def test_join_class_duplicate(self):
            """测试学生重复加入班级应该失败"""
            from types import SimpleNamespace

            service = StudentClassService(AsyncMock())

            # 模拟已存在的学生班级关系
            existing = SimpleNamespace(
                id="sc-1",
                student_id="stu-1",
                teaching_class_id="class-1",
            )

            service.student_class_repo.get_by_student_and_class = AsyncMock(return_value=existing)

            with self.assertRaises(ValueError) as exc:
                await service.join_class("stu-1", "class-1")

            self.assertIn("学生已加入该班级", str(exc.exception))

        async def test_join_class_not_found(self):
            """测试班级不存在时应该失败"""
            service = StudentClassService(AsyncMock())

            service.student_class_repo.get_by_student_and_class = AsyncMock(return_value=None)
            service.teaching_class_repo.get = AsyncMock(return_value=None)

            with self.assertRaises(ValueError) as exc:
                await service.join_class("stu-1", "class-1")

            self.assertIn("班级不存在", str(exc.exception))

else:
    @unittest.skip("当前环境缺少 sqlalchemy，跳过学生班级测试")
    class StudentClassServiceTests(unittest.TestCase):
        def test_skip_when_sqlalchemy_unavailable(self):
            self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
