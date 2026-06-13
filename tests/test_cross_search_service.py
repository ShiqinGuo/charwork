import pytest
from app.services.cross_search_service import CrossSearchService


class TestBuildPermissionFilter:
    """测试 _build_permission_filter 方法"""

    def test_admin_returns_empty_filter(self):
        """管理员无权限过滤"""
        from app.schemas.search import PermissionContext
        ctx = PermissionContext(role="admin")
        result = CrossSearchService._build_permission_filter(ctx)
        assert result == []

    def test_teacher_builds_should_filter(self):
        """教师过滤自身可见数据"""
        from app.schemas.search import PermissionContext
        ctx = PermissionContext(role="teacher", user_id="teacher_user_1")
        result = CrossSearchService._build_permission_filter(ctx)
        assert len(result) == 1
        should_clause = result[0]
        assert "bool" in should_clause
        assert "should" in should_clause["bool"]

    def test_student_builds_should_filter(self):
        """学生过滤自身课程可见数据"""
        from app.schemas.search import PermissionContext
        ctx = PermissionContext(
            role="student",
            course_ids=["course_1", "course_2"],
            student_user_id="student_user_1",
            user_id="student_user_1",
        )
        result = CrossSearchService._build_permission_filter(ctx)
        assert len(result) == 1
        should_clause = result[0]
        assert "bool" in should_clause
        should_terms = should_clause["bool"]["should"]
        assert any("course_id" in str(term) for term in should_terms)

    def test_student_no_courses_still_has_student_filter(self):
        """学生无课程时仍可按 student_user_id 过滤"""
        from app.schemas.search import PermissionContext
        ctx = PermissionContext(
            role="student",
            course_ids=[],
            student_user_id="student_user_1",
            user_id="student_user_1",
        )
        result = CrossSearchService._build_permission_filter(ctx)
        assert len(result) == 1
