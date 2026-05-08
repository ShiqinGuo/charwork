import unittest
from unittest.mock import AsyncMock, MagicMock

from app.services.search_registry import (
    SearchModuleConfig,
    SearchDocument,
    _preload_teacher_user_ids,
    _preload_student_teacher_user_ids,
)


class TestPreloadFunctions(unittest.IsolatedAsyncioTestCase):

    async def test_preload_teacher_user_ids(self):
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = [("t1", "u1"), ("t2", "u2")]
        mock_db.execute.return_value = mock_result
        result = await _preload_teacher_user_ids(mock_db)
        self.assertEqual(result, {"t1": "u1", "t2": "u2"})

    async def test_preload_student_teacher_user_ids(self):
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = [("s1", "u1"), ("s1", "u2"), ("s2", "u3")]
        mock_db.execute.return_value = mock_result
        result = await _preload_student_teacher_user_ids(mock_db)
        self.assertEqual(result, {"s1": ["u1", "u2"], "s2": ["u3"]})


class TestBuildDocumentWithContext(unittest.IsolatedAsyncioTestCase):

    async def test_build_assignment_document_uses_context(self):
        from app.models.assignment import Assignment
        from app.services.search_registry import _build_assignment_document

        item = Assignment()
        item.id = "a1"
        item.title = "Test Assignment"
        item.description = "Desc"
        item.teacher_id = "t1"
        item.course_id = "c1"

        context = {"teacher_user_ids": {"t1": "user-t1"}}
        doc = await _build_assignment_document(AsyncMock(), item, context)
        self.assertIsNotNone(doc)
        self.assertEqual(doc.extra_fields["teacher_user_id"], "user-t1")

    async def test_build_assignment_document_returns_none_without_teacher(self):
        from app.models.assignment import Assignment
        from app.services.search_registry import _build_assignment_document

        item = Assignment()
        item.id = "a1"
        item.title = "Test"
        item.description = ""
        item.teacher_id = "t_missing"
        item.course_id = "c1"

        context = {"teacher_user_ids": {}}  # t_missing 不在映射中
        doc = await _build_assignment_document(AsyncMock(), item, context)
        self.assertIsNone(doc)

    async def test_build_assignment_document_cdc_fallback(self):
        from app.models.assignment import Assignment
        from app.services.search_registry import _build_assignment_document, _get_teacher_user_id_fallback

        item = Assignment()
        item.id = "a1"
        item.title = "Test"
        item.description = ""
        item.teacher_id = "t1"
        item.course_id = "c1"

        mock_db = AsyncMock()
        # 空上下文触发 CDC 回退
        with unittest.mock.patch.object(
            _get_teacher_user_id_fallback.__wrapped__ if hasattr(_get_teacher_user_id_fallback, '__wrapped__') else _get_teacher_user_id_fallback,
            '__call__',
            return_value="fallback-user",
        ):
            # 直接 mock 模块级函数
            pass

        # 简化：mock _get_teacher_user_id_fallback
        import app.services.search_registry as registry
        original = registry._get_teacher_user_id_fallback
        registry._get_teacher_user_id_fallback = AsyncMock(return_value="fallback-user")
        try:
            doc = await _build_assignment_document(mock_db, item, {})
        finally:
            registry._get_teacher_user_id_fallback = original
        self.assertIsNotNone(doc)
        self.assertEqual(doc.extra_fields["teacher_user_id"], "fallback-user")


if __name__ == "__main__":
    unittest.main()
