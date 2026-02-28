from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.submission_repo import SubmissionRepository
from app.schemas.submission import SubmissionCreate, SubmissionGrade, SubmissionResponse
from app.tasks.notification_tasks import send_grade_notification, send_submission_notification


class SubmissionService:
    def __init__(self, db: AsyncSession):
        self.repo = SubmissionRepository(db)

    async def get_submission(self, id: str) -> Optional[SubmissionResponse]:
        submission = await self.repo.get(id)
        return SubmissionResponse.model_validate(submission) if submission else None

    async def list_submissions_by_assignment(self, assignment_id: str, skip: int = 0, limit: int = 20) -> dict:
        items = await self.repo.get_all_by_assignment(assignment_id, skip, limit)
        total = await self.repo.count_by_assignment(assignment_id)
        return {"total": total, "items": [SubmissionResponse.model_validate(i) for i in items]}

    async def create_submission(self, assignment_id: str, submission_in: SubmissionCreate) -> SubmissionResponse:
        submission = await self.repo.create(assignment_id, submission_in)
        send_submission_notification.delay(submission.id)
        return SubmissionResponse.model_validate(submission)

    async def grade_submission(self, id: str, body: SubmissionGrade) -> Optional[SubmissionResponse]:
        submission = await self.repo.get(id)
        if not submission:
            return None
        update_data = {
            "score": body.score,
            "feedback": body.feedback,
            "status": "graded",
            "graded_at": datetime.now(),
        }
        submission = await self.repo.update(submission, update_data)
        send_grade_notification.delay(submission.id)
        return SubmissionResponse.model_validate(submission)
