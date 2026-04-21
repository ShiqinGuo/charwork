from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import SessionUser
from app.models.assignment import Assignment
from app.models.student import Student
from app.models.submission import Submission
from app.models.user import UserRole


class AIToolsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def search_resources(
        self,
        keyword: str,
        teacher_user_id: str,
        modules: list[str] | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        """调用 ES 跨模块搜索，返回结果列表（含跳转 URL）。"""
        from app.services.cross_search_service import CrossSearchService

        # 教师角色在 CrossSearchService 中不做额外权限裁剪
        teacher_session = SessionUser(
            id=teacher_user_id,
            email="",
            username="",
            role=UserRole.TEACHER,
            is_active=True,
        )
        service = CrossSearchService(self.db)
        result = await service.search(
            keyword=keyword,
            current_user=teacher_session,
            modules=modules,
            limit=limit,
        )
        items = [
            {
                "module": hit.module,
                "id": hit.id,
                "title": hit.title,
                "content": hit.content[:200],
                "target_type": hit.target_type,
                "url": hit.url,
            }
            for hit in result.items
        ]
        return {"keyword": keyword, "total": result.total, "items": items}

    async def get_student_recent_assignments(
        self,
        student_id: str,
        limit: int = 5,
    ) -> dict[str, Any]:
        student = await self._get_student(student_id)
        if not student:
            raise ValueError("学生不存在")
        stmt = (
            select(Submission, Assignment)
            .join(Assignment, Submission.assignment_id == Assignment.id)
            .where(
                and_(
                    Submission.student_id == student_id,
                )
            )
            .order_by(Submission.submitted_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        rows = result.all()
        items = [
            {
                "submission_id": submission.id,
                "assignment_id": assignment.id,
                "assignment_title": assignment.title,
                "submitted_at": submission.submitted_at.isoformat() if submission.submitted_at else None,
                "status": str(submission.status),
                "score": submission.score,
            }
            for submission, assignment in rows
        ]
        return {
            "student_id": student.id,
            "student_name": student.name,
            "count": len(items),
            "items": items,
        }

    async def get_student_handwriting_quality(
        self,
        student_id: str,
        recent_days: int = 30,
    ) -> dict[str, Any]:
        student = await self._get_student(student_id)
        if not student:
            raise ValueError("学生不存在")
        time_start = datetime.now() - timedelta(days=recent_days)
        stmt = (
            select(
                func.count(Submission.id),
                func.avg(Submission.score),
                func.max(Submission.score),
                func.min(Submission.score),
            )
            .where(
                and_(
                    Submission.student_id == student_id,
                    Submission.submitted_at >= time_start,
                    Submission.score.is_not(None),
                )
            )
        )
        result = await self.db.execute(stmt)
        row = result.one()
        graded_count = int(row[0] or 0)
        average_score = float(row[1]) if row[1] is not None else None
        quality_level = self._resolve_quality_level(average_score)
        return {
            "student_id": student.id,
            "student_name": student.name,
            "recent_days": recent_days,
            "graded_count": graded_count,
            "average_score": average_score,
            "max_score": int(row[2]) if row[2] is not None else None,
            "min_score": int(row[3]) if row[3] is not None else None,
            "quality_level": quality_level,
        }

    async def _get_student(self, student_id: str) -> Student | None:
        result = await self.db.execute(select(Student).where(Student.id == student_id))
        return result.scalars().first()

    @staticmethod
    def _resolve_quality_level(average_score: float | None) -> str:
        if average_score is None:
            return "暂无评分数据"
        if average_score >= 90:
            return "优秀"
        if average_score >= 75:
            return "良好"
        if average_score >= 60:
            return "及格"
        return "待提升"
