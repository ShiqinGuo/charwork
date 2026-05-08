import asyncio
from unittest.mock import AsyncMock
from app.schemas.submission import BatchGradeRequest, BatchGradeItem


class TestBatchGrade:
    """测试 batch_grade 方法"""

    def test_batch_grade_all_success(self):
        """全部成功场景"""
        from app.services.submission_service import SubmissionService
        mock_db = AsyncMock()
        service = SubmissionService(mock_db)

        service.grade_submission = AsyncMock(return_value={"id": "sub_1", "status": "graded"})

        request = BatchGradeRequest(grades=[
            BatchGradeItem(submission_id="sub_1", score=85, feedback="good"),
            BatchGradeItem(submission_id="sub_2", score=90, feedback="excellent"),
        ])
        result = asyncio.run(service.batch_grade(request, sender_user_id="teacher_1"))
        assert result.total == 2
        assert result.success == 2
        assert len(result.failed) == 0

    def test_batch_grade_partial_failure(self):
        """部分失败场景"""
        from app.services.submission_service import SubmissionService
        mock_db = AsyncMock()
        service = SubmissionService(mock_db)

        async def grade_side_effect(id, body, sender_user_id):
            if id == "sub_2":
                raise ValueError("已批改，无法重复批改")
            return {"id": id, "status": "graded"}

        service.grade_submission = AsyncMock(side_effect=grade_side_effect)

        request = BatchGradeRequest(grades=[
            BatchGradeItem(submission_id="sub_1", score=85, feedback="good"),
            BatchGradeItem(submission_id="sub_2", score=90, feedback="excellent"),
        ])
        result = asyncio.run(service.batch_grade(request, sender_user_id="teacher_1"))
        assert result.total == 2
        assert result.success == 1
        assert len(result.failed) == 1
        assert result.failed[0].submission_id == "sub_2"
