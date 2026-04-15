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

        async def test_list_student_classes(self):
            """测试查看学生加入的班级列表"""
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

            # 设置 mock
            service.student_class_repo.list_by_student = AsyncMock(
                return_value=([student_class], 1)
            )

            result = await service.list_student_classes("stu-1", skip=0, limit=20)

            self.assertEqual(result.total, 1)
            self.assertEqual(len(result.items), 1)
            self.assertEqual(result.items[0].id, "sc-1")
            self.assertEqual(result.items[0].teaching_class_id, "class-1")

        async def test_get_class_detail(self):
            """测试查看班级详情"""
            from types import SimpleNamespace

            db_mock = AsyncMock()
            service = StudentClassService(db_mock)

            # 模拟学生班级关系
            student_class = SimpleNamespace(
                id="sc-1",
                student_id="stu-1",
                teaching_class_id="class-1",
                status="active",
                joined_at=datetime(2026, 4, 15, 10, 0, 0),
            )

            # 模拟班级信息
            teaching_class = SimpleNamespace(
                id="class-1",
                name="一年级一班",
                description="一年级一班的班级",
                teacher_id="teacher-1",
            )

            # 模拟教师信息
            teacher = SimpleNamespace(
                id="teacher-1",
                name="张老师",
            )

            # 设置 mock
            service.student_class_repo.get_by_student_and_class = AsyncMock(
                return_value=student_class
            )
            service.teaching_class_repo.get = AsyncMock(return_value=teaching_class)

            # 模拟 TeacherRepository
            with patch("app.services.student_class_service.TeacherRepository") as mock_teacher_repo_class:
                mock_teacher_repo = AsyncMock()
                mock_teacher_repo.get = AsyncMock(return_value=teacher)
                mock_teacher_repo_class.return_value = mock_teacher_repo

                result = await service.get_class_detail("stu-1", "class-1")

                self.assertEqual(result["id"], "class-1")
                self.assertEqual(result["name"], "一年级一班")
                self.assertEqual(result["description"], "一年级一班的班级")
                self.assertEqual(result["teacher_id"], "teacher-1")
                self.assertEqual(result["teacher_name"], "张老师")
                self.assertEqual(result["member_count"], 0)
                self.assertEqual(result["assignment_count"], 0)
                self.assertEqual(result["status"], "active")

        async def test_get_class_detail_not_joined(self):
            """测试查看未加入班级的详情"""
            from types import SimpleNamespace

            db_mock = AsyncMock()
            service = StudentClassService(db_mock)

            # 设置 mock - 学生未加入班级
            service.student_class_repo.get_by_student_and_class = AsyncMock(
                return_value=None
            )

            with self.assertRaises(ValueError) as exc:
                await service.get_class_detail("stu-1", "class-1")

            self.assertIn("学生未加入该班级", str(exc.exception))

        async def test_get_class_members(self):
            """测试查看班级成员列表"""
            from types import SimpleNamespace

            db_mock = AsyncMock()
            service = StudentClassService(db_mock)

            # 模拟学生班级关系
            student_class = SimpleNamespace(
                id="sc-1",
                student_id="stu-1",
                teaching_class_id="class-1",
                status="active",
                joined_at=datetime(2026, 4, 15, 10, 0, 0),
            )

            # 模拟班级成员
            member_items = [
                {
                    "id": "stu-1",
                    "name": "学生1",
                    "joined_at": datetime(2026, 4, 15, 10, 0, 0),
                },
                {
                    "id": "stu-2",
                    "name": "学生2",
                    "joined_at": datetime(2026, 4, 15, 11, 0, 0),
                },
            ]

            # 设置 mock
            service.student_class_repo.get_by_student_and_class = AsyncMock(
                return_value=student_class
            )
            service.student_class_repo.list_class_members = AsyncMock(
                return_value=(member_items, 2)
            )

            result = await service.get_class_members("stu-1", "class-1", skip=0, limit=20)

            self.assertEqual(result["total"], 2)
            self.assertEqual(len(result["items"]), 2)
            self.assertEqual(result["items"][0]["id"], "stu-1")
            self.assertEqual(result["items"][0]["name"], "学生1")
            self.assertEqual(result["items"][1]["id"], "stu-2")
            self.assertEqual(result["items"][1]["name"], "学生2")

        async def test_get_class_members_not_joined(self):
            """测试查看未加入班级的成员列表"""
            from types import SimpleNamespace

            db_mock = AsyncMock()
            service = StudentClassService(db_mock)

            # 设置 mock - 学生未加入班级
            service.student_class_repo.get_by_student_and_class = AsyncMock(
                return_value=None
            )

            with self.assertRaises(ValueError) as exc:
                await service.get_class_members("stu-1", "class-1")

            self.assertIn("学生未加入该班级", str(exc.exception))

        async def test_get_class_assignments(self):
            """测试查看班级作业列表"""
            from types import SimpleNamespace

            db_mock = AsyncMock()
            service = StudentClassService(db_mock)

            # 模拟学生班级关系
            student_class = SimpleNamespace(
                id="sc-1",
                student_id="stu-1",
                teaching_class_id="class-1",
                status="active",
                joined_at=datetime(2026, 4, 15, 10, 0, 0),
            )

            # 模拟课程
            course = SimpleNamespace(
                id="course-1",
                name="语文",
                teaching_class_id="class-1",
            )

            # 模拟作业
            assignment = SimpleNamespace(
                id="assign-1",
                title="第一课作业",
                description="完成第一课的练习",
                due_date=datetime(2026, 4, 20, 23, 59, 59),
                created_at=datetime(2026, 4, 15, 10, 0, 0),
                course_id="course-1",
            )

            # 模拟提交
            submission = SimpleNamespace(
                id="sub-1",
                assignment_id="assign-1",
                student_id="stu-1",
                status="submitted",
                submitted_at=datetime(2026, 4, 18, 10, 0, 0),
            )

            # 设置 mock
            service.student_class_repo.get_by_student_and_class = AsyncMock(
                return_value=student_class
            )

            # 模拟 CourseRepository
            with patch("app.services.student_class_service.CourseRepository") as mock_course_repo_class:
                mock_course_repo = AsyncMock()
                mock_course_repo.list_by_teaching_class = AsyncMock(return_value=[course])
                mock_course_repo_class.return_value = mock_course_repo

                # 模拟 AssignmentRepository
                with patch("app.services.student_class_service.AssignmentRepository") as mock_assign_repo_class:
                    mock_assign_repo = AsyncMock()
                    mock_assign_repo.get_all = AsyncMock(return_value=[assignment])
                    mock_assign_repo.count = AsyncMock(return_value=1)
                    mock_assign_repo_class.return_value = mock_assign_repo

                    # 模拟 SubmissionRepository
                    with patch("app.services.student_class_service.SubmissionRepository") as mock_sub_repo_class:
                        mock_sub_repo = AsyncMock()
                        mock_sub_repo.get_all_by_assignment = AsyncMock(return_value=[submission])
                        mock_sub_repo_class.return_value = mock_sub_repo

                        result = await service.get_class_assignments("stu-1", "class-1", skip=0, limit=20)

                        self.assertEqual(result["total"], 1)
                        self.assertEqual(len(result["items"]), 1)
                        self.assertEqual(result["items"][0]["id"], "assign-1")
                        self.assertEqual(result["items"][0]["title"], "第一课作业")
                        self.assertEqual(result["items"][0]["submission_status"], "submitted")
                        self.assertEqual(result["items"][0]["submission_id"], "sub-1")

        async def test_get_class_assignments_not_joined(self):
            """测试查看未加入班级的作业列表"""
            from types import SimpleNamespace

            db_mock = AsyncMock()
            service = StudentClassService(db_mock)

            # 设置 mock - 学生未加入班级
            service.student_class_repo.get_by_student_and_class = AsyncMock(
                return_value=None
            )

            with self.assertRaises(ValueError) as exc:
                await service.get_class_assignments("stu-1", "class-1")

            self.assertIn("学生未加入该班级", str(exc.exception))

else:
    @unittest.skip("当前环境缺少 sqlalchemy，跳过学生班级测试")
    class StudentClassServiceTests(unittest.TestCase):
        def test_skip_when_sqlalchemy_unavailable(self):
            self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
