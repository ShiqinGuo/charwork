from datetime import datetime
from typing import Optional

from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_chat import AIChatConversation, AIChatMemoryFact, AIChatMessage


class AIChatRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_conversation(self, conversation_id: str) -> Optional[AIChatConversation]:
        result = await self.db.execute(
            select(AIChatConversation).where(AIChatConversation.id == conversation_id)
        )
        return result.scalars().first()

    async def list_conversations(
        self,
        teacher_user_id: str,
        management_system_id: str,
        limit: int = 30,
        offset: int = 0,
    ) -> list[AIChatConversation]:
        result = await self.db.execute(
            select(AIChatConversation)
            .where(
                and_(
                    AIChatConversation.teacher_user_id == teacher_user_id,
                    AIChatConversation.management_system_id == management_system_id,
                    AIChatConversation.is_deleted.is_(False),
                )
            )
            .order_by(desc(AIChatConversation.updated_at))
            .offset(offset)
            .limit(limit)
        )
        return result.scalars().all()

    async def count_conversations(self, teacher_user_id: str, management_system_id: str) -> int:
        result = await self.db.execute(
            select(AIChatConversation)
            .where(
                and_(
                    AIChatConversation.teacher_user_id == teacher_user_id,
                    AIChatConversation.management_system_id == management_system_id,
                    AIChatConversation.is_deleted.is_(False),
                )
            )
        )
        return len(result.scalars().all())

    async def create_conversation(
        self,
        conversation_id: str,
        teacher_user_id: str,
        management_system_id: str,
        title: str,
    ) -> AIChatConversation:
        item = AIChatConversation(
            id=conversation_id,
            teacher_user_id=teacher_user_id,
            management_system_id=management_system_id,
            title=title,
        )
        self.db.add(item)
        await self.db.flush()
        return item

    async def touch_conversation(self, conversation: AIChatConversation) -> None:
        conversation.updated_at = datetime.now()
        await self.db.flush()

    async def rename_conversation(self, conversation: AIChatConversation, title: str) -> AIChatConversation:
        conversation.title = title
        conversation.updated_at = datetime.now()
        await self.db.flush()
        return conversation

    async def soft_delete_conversation(self, conversation: AIChatConversation) -> None:
        now = datetime.now()
        conversation.is_deleted = True
        conversation.deleted_at = now
        conversation.updated_at = now
        messages_result = await self.db.execute(
            select(AIChatMessage).where(AIChatMessage.conversation_id == conversation.id)
        )
        messages = messages_result.scalars().all()
        for message in messages:
            message.is_deleted = True
            message.deleted_at = now
        await self.db.flush()

    async def create_message(
        self,
        message_id: str,
        conversation_id: str,
        role: str,
        content: str,
        tool_calls_json: Optional[list[dict]] = None,
    ) -> AIChatMessage:
        item = AIChatMessage(
            id=message_id,
            conversation_id=conversation_id,
            role=role,
            content=content,
            tool_calls_json=tool_calls_json,
        )
        self.db.add(item)
        await self.db.flush()
        return item

    async def list_messages(
        self,
        conversation_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AIChatMessage]:
        result = await self.db.execute(
            select(AIChatMessage)
            .where(
                and_(
                    AIChatMessage.conversation_id == conversation_id,
                    AIChatMessage.is_deleted.is_(False),
                )
            )
            .order_by(AIChatMessage.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
        return result.scalars().all()

    async def list_recent_messages(self, conversation_id: str, limit: int) -> list[AIChatMessage]:
        result = await self.db.execute(
            select(AIChatMessage)
            .where(
                and_(
                    AIChatMessage.conversation_id == conversation_id,
                    AIChatMessage.is_deleted.is_(False),
                )
            )
            .order_by(desc(AIChatMessage.created_at))
            .limit(limit)
        )
        items = result.scalars().all()
        return list(reversed(items))

    async def count_messages(self, conversation_id: str) -> int:
        result = await self.db.execute(
            select(AIChatMessage)
            .where(
                and_(
                    AIChatMessage.conversation_id == conversation_id,
                    AIChatMessage.is_deleted.is_(False),
                )
            )
        )
        return len(result.scalars().all())

    async def create_memory_facts(
        self,
        conversation_id: str,
        message_id: str,
        teacher_user_id: str,
        management_system_id: str,
        student_id: Optional[str],
        facts: list[dict],
    ) -> None:
        for fact in facts:
            self.db.add(
                AIChatMemoryFact(
                    conversation_id=conversation_id,
                    message_id=message_id,
                    teacher_user_id=teacher_user_id,
                    management_system_id=management_system_id,
                    student_id=student_id,
                    fact_type=str(fact.get("fact_type") or "tool_result"),
                    fact_key=str(fact.get("fact_key") or ""),
                    fact_value_json=fact.get("fact_value") or {},
                )
            )
        await self.db.flush()

    async def list_latest_memory_facts(
        self,
        teacher_user_id: str,
        management_system_id: str,
        limit: int,
    ) -> list[AIChatMemoryFact]:
        result = await self.db.execute(
            select(AIChatMemoryFact)
            .where(
                and_(
                    AIChatMemoryFact.teacher_user_id == teacher_user_id,
                    AIChatMemoryFact.management_system_id == management_system_id,
                )
            )
            .order_by(desc(AIChatMemoryFact.created_at))
            .limit(limit)
        )
        return result.scalars().all()

    async def commit(self) -> None:
        await self.db.commit()
