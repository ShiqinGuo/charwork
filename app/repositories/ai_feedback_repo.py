from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_feedback import AIFeedback


class AIFeedbackRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_slot(
        self,
        target_type: str,
        target_id: str,
        feedback_scope: str,
    ) -> Optional[AIFeedback]:
        query = select(AIFeedback).where(
            AIFeedback.target_type == target_type,
            AIFeedback.target_id == target_id,
            AIFeedback.feedback_scope == feedback_scope,
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def list_by_targets(
        self,
        target_type: str,
        target_ids: list[str],
        feedback_scope: str,
        visibility_scopes: list[str] | None = None,
    ) -> list[AIFeedback]:
        if not target_ids:
            return []
        query = select(AIFeedback).where(
            AIFeedback.target_type == target_type,
            AIFeedback.target_id.in_(target_ids),
            AIFeedback.feedback_scope == feedback_scope,
        )
        if visibility_scopes:
            query = query.where(AIFeedback.visibility_scope.in_(visibility_scopes))
        result = await self.db.execute(query)
        return result.scalars().all()

    async def upsert_feedback(
        self,
        *,
        target_type: str,
        target_id: str,
        feedback_scope: str,
        visibility_scope: str,
        status: str,
        generated_by: str,
        result_payload: Optional[dict],
    ) -> AIFeedback:
        feedback = await self.get_by_slot(
            target_type=target_type,
            target_id=target_id,
            feedback_scope=feedback_scope,
        )
        if feedback is None:
            feedback = AIFeedback(
                target_type=target_type,
                target_id=target_id,
                feedback_scope=feedback_scope,
                visibility_scope=visibility_scope,
                status=status,
                generated_by=generated_by,
                result_payload=result_payload,
            )
            self.db.add(feedback)
        else:
            feedback.visibility_scope = visibility_scope
            feedback.status = status
            feedback.generated_by = generated_by
            feedback.result_payload = result_payload
        await self.db.commit()
        await self.db.refresh(feedback)
        return feedback
