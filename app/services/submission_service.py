from datetime import datetime
import json
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.event_outbox_repo import EventOutboxRepository
from app.repositories.submission_repo import SubmissionRepository
from app.schemas.submission import SubmissionCreate, SubmissionGrade, SubmissionResponse
from app.tasks.notification_tasks import send_grade_notification, send_submission_notification, publish_outbox_events


class SubmissionService:
    def __init__(self, db: AsyncSession):
        self.repo = SubmissionRepository(db)
        self.outbox_repo = EventOutboxRepository(db)

    async def get_submission(self, id: str) -> Optional[SubmissionResponse]:
        submission = await self.repo.get(id)
        return SubmissionResponse.model_validate(submission) if submission else None

    async def list_submissions_by_assignment(self, assignment_id: str, skip: int = 0, limit: int = 20) -> dict:
        items = await self.repo.get_all_by_assignment(assignment_id, skip, limit)
        total = await self.repo.count_by_assignment(assignment_id)
        return {"total": total, "items": [SubmissionResponse.model_validate(i) for i in items]}

    async def create_submission(self, assignment_id: str, submission_in: SubmissionCreate) -> SubmissionResponse:
        submission = self.repo.build_submission(assignment_id, submission_in)
        self.repo.db.add(submission)
        await self.repo.db.flush()
        payload = json.dumps(
            {
                "submission_id": submission.id,
                "assignment_id": assignment_id,
                "student_id": submission_in.student_id,
            },
            ensure_ascii=False,
        )
        await self.outbox_repo.add_event(
            aggregate_type="submission",
            aggregate_id=submission.id,
            event_type="submission.created",
            payload=payload,
        )
        await self.repo.commit()
        await self.repo.refresh(submission)
        send_submission_notification.delay(submission.id)
        publish_outbox_events.delay()
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
