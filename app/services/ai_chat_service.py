import asyncio
import json
import re
from datetime import datetime
from typing import Any, AsyncIterator

import requests
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis_client import get_redis
from app.models.ai_chat import AIChatConversation as AIChatConversationModel
from app.models.ai_chat import AIChatMessage as AIChatMessageModel
from app.repositories.ai_chat_repo import AIChatRepository
from app.schemas.ai_chat import (
    AIChatConversation,
    AIChatConversationListResponse,
    AIChatConversationRenameRequest,
    AIChatMessage,
    AIChatMessageListResponse,
    AIChatRequest,
    AIChatStreamEvent,
    AIChatToolCall,
)
from app.services.ai_tools_service import AIToolsService
from app.utils.id_generator import generate_id
from app.utils.pagination import build_paged_response


STUDENT_ID_PATTERN = re.compile(r"(stu_[a-zA-Z0-9]+|[a-zA-Z0-9]{10,50})")


class AIChatService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AIChatRepository(db)
        self.tools_service = AIToolsService(db)

    async def stream_chat(self, body: AIChatRequest, management_system_id: str, teacher_user_id: str) -> AsyncIterator[str]:
        conversation = await self._ensure_conversation(
            conversation_id=body.conversation_id or generate_id(),
            first_message=body.message,
            management_system_id=management_system_id,
            teacher_user_id=teacher_user_id,
        )
        user_message = await self.repo.create_message(
            message_id=generate_id(),
            conversation_id=conversation.id,
            role="user",
            content=body.message,
            tool_calls_json=[],
        )
        tool_calls = await self._collect_tool_calls(body, management_system_id)
        for call in tool_calls:
            yield self._to_sse(
                AIChatStreamEvent(
                    event="tool_call_start",
                    data={"name": call.name, "args": call.args},
                )
            )
            yield self._to_sse(
                AIChatStreamEvent(
                    event="tool_call_result",
                    data={"name": call.name, "result": call.result},
                )
            )
        short_messages = await self._load_short_memory_window(conversation.id)
        long_memory = await self._load_long_memory_facts(teacher_user_id, management_system_id)
        answer = await self._call_model(
            user_message=body.message,
            tool_calls=tool_calls,
            short_messages=short_messages,
            long_memory_facts=long_memory,
        )
        assistant_message = await self.repo.create_message(
            message_id=generate_id(),
            conversation_id=conversation.id,
            role="assistant",
            content=answer,
            tool_calls_json=[item.model_dump() for item in tool_calls],
        )
        await self.repo.touch_conversation(conversation)
        await self._persist_long_memory_facts(
            conversation_id=conversation.id,
            message_id=assistant_message.id,
            teacher_user_id=teacher_user_id,
            management_system_id=management_system_id,
            student_id=body.student_id or self._extract_student_id(body.message),
            tool_calls=tool_calls,
        )
        await self.repo.commit()
        await self._refresh_short_memory_cache(conversation.id)
        for chunk in self._chunk_text(answer, 40):
            yield self._to_sse(AIChatStreamEvent(event="message_chunk", data={"content": chunk}))
            await asyncio.sleep(0.02)
        yield self._to_sse(
            AIChatStreamEvent(
                event="done",
                data={
                    "conversation_id": conversation.id,
                    "message_id": assistant_message.id,
                    "tool_calls": [call.model_dump() for call in tool_calls],
                    "answer": answer,
                },
            )
        )

    async def list_conversations(
        self,
        teacher_user_id: str,
        management_system_id: str,
        limit: int = 30,
        offset: int = 0,
        page: int | None = None,
        size: int | None = None,
    ) -> AIChatConversationListResponse:
        items = await self.repo.list_conversations(
            teacher_user_id=teacher_user_id,
            management_system_id=management_system_id,
            limit=limit,
            offset=offset,
        )
        total = await self.repo.count_conversations(teacher_user_id, management_system_id)
        payload = build_paged_response(
            items=[self._to_conversation_response(item) for item in items],
            total=total,
            pagination={"page": page, "size": size, "skip": offset, "limit": limit},
        )
        return AIChatConversationListResponse(**payload)

    async def list_messages(
        self,
        conversation_id: str,
        teacher_user_id: str,
        management_system_id: str,
        limit: int = 100,
        offset: int = 0,
        page: int | None = None,
        size: int | None = None,
    ) -> AIChatMessageListResponse:
        conversation = await self._load_accessible_conversation(conversation_id, teacher_user_id, management_system_id)
        items = await self.repo.list_messages(conversation.id, limit=limit, offset=offset)
        total = await self.repo.count_messages(conversation.id)
        payload = build_paged_response(
            items=[self._to_message_response(item) for item in items],
            total=total,
            pagination={"page": page, "size": size, "skip": offset, "limit": limit},
        )
        return AIChatMessageListResponse(**payload)

    async def rename_conversation(
        self,
        conversation_id: str,
        teacher_user_id: str,
        management_system_id: str,
        body: AIChatConversationRenameRequest,
    ) -> AIChatConversation:
        conversation = await self._load_accessible_conversation(conversation_id, teacher_user_id, management_system_id)
        item = await self.repo.rename_conversation(conversation, body.title.strip())
        await self.repo.commit()
        return self._to_conversation_response(item)

    async def delete_conversation(
        self,
        conversation_id: str,
        teacher_user_id: str,
        management_system_id: str,
    ) -> None:
        conversation = await self._load_accessible_conversation(conversation_id, teacher_user_id, management_system_id)
        await self.repo.soft_delete_conversation(conversation)
        await self.repo.commit()
        redis = get_redis()
        await redis.delete(self._short_memory_cache_key(conversation_id))

    async def _collect_tool_calls(self, body: AIChatRequest, management_system_id: str) -> list[AIChatToolCall]:
        student_id = body.student_id or self._extract_student_id(body.message)
        if not student_id:
            return []
        recent_assignments = await self.tools_service.get_student_recent_assignments(
            student_id=student_id,
            management_system_id=management_system_id,
            limit=body.assignment_limit,
        )
        quality = await self.tools_service.get_student_handwriting_quality(
            student_id=student_id,
            management_system_id=management_system_id,
            recent_days=body.recent_days,
        )
        return [
            AIChatToolCall(
                name="get_student_recent_assignments",
                args={
                    "student_id": student_id,
                    "limit": body.assignment_limit,
                    "management_system_id": management_system_id,
                },
                result=recent_assignments,
            ),
            AIChatToolCall(
                name="get_student_handwriting_quality",
                args={
                    "student_id": student_id,
                    "recent_days": body.recent_days,
                    "management_system_id": management_system_id,
                },
                result=quality,
            ),
        ]

    async def _call_model(
        self,
        user_message: str,
        tool_calls: list[AIChatToolCall],
        short_messages: list[AIChatMessageModel],
        long_memory_facts: list[dict[str, Any]],
    ) -> str:
        model_input = self._build_messages(user_message, tool_calls, short_messages, long_memory_facts)
        payload = {
            "model": self._get_model(),
            "messages": model_input,
            "temperature": 0.2,
        }
        headers = {
            "Authorization": f"Bearer {self._get_api_key()}",
            "Content-Type": "application/json",
        }
        url = self._build_chat_url()
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if isinstance(content, list):
                text_chunks = [item.get("text", "") for item in content if isinstance(item, dict)]
                return "".join(text_chunks).strip()
            return str(content).strip() or "我已经读取上下文，但当前无法生成回答。"
        except Exception:
            return "当前 AI 服务不可用，请稍后重试。"

    def _build_messages(
        self,
        user_message: str,
        tool_calls: list[AIChatToolCall],
        short_messages: list[AIChatMessageModel],
        long_memory_facts: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        tool_context = "\n".join(
            [
                f"工具：{call.name}\n参数：{json.dumps(call.args, ensure_ascii=False)}\n结果：{json.dumps(call.result, ensure_ascii=False)}"
                for call in tool_calls
            ]
        )
        short_context = "\n".join([f"{item.role}: {item.content}" for item in short_messages])
        long_context = "\n".join([json.dumps(item, ensure_ascii=False) for item in long_memory_facts])
        system_prompt = (
            "你是教师工作台中的教学助手。"
            "优先依据工具结果回答，结论要简洁，给出可执行建议。"
            "如缺少学生标识或上下文不足，要明确指出。"
        )
        return [
            {"role": "system", "content": system_prompt},
            {"role": "system", "content": f"短期记忆（会话窗口）：\n{short_context or '无'}"},
            {"role": "system", "content": f"长期记忆（工具事实）：\n{long_context or '无'}"},
            {"role": "system", "content": f"当前工具上下文：\n{tool_context or '无'}"},
            {"role": "user", "content": user_message},
        ]

    def _build_chat_url(self) -> str:
        base = (settings.ARK_BASE_URL or settings.AI_BASE_URL or "").rstrip("/")
        if not base:
            raise ValueError("缺少 AI 服务地址配置")
        return f"{base}/chat/completions"

    def _get_api_key(self) -> str:
        key = settings.ARK_API_KEY or settings.AI_API_KEY or ""
        if not key:
            raise ValueError("缺少 AI API Key")
        return key

    def _get_model(self) -> str:
        model = settings.ARK_MODEL or settings.AI_MODEL or ""
        if not model:
            raise ValueError("缺少 AI 模型配置")
        return model

    async def _ensure_conversation(
        self,
        conversation_id: str,
        first_message: str,
        management_system_id: str,
        teacher_user_id: str,
    ) -> AIChatConversationModel:
        item = await self.repo.get_conversation(conversation_id)
        if item:
            if item.teacher_user_id != teacher_user_id or item.management_system_id != management_system_id:
                raise ValueError("无权访问该对话")
            if item.is_deleted:
                raise ValueError("对话已删除")
            return item
        title = first_message.strip()[:20] or "新对话"
        return await self.repo.create_conversation(
            conversation_id=conversation_id,
            teacher_user_id=teacher_user_id,
            management_system_id=management_system_id,
            title=title,
        )

    async def _load_accessible_conversation(
        self,
        conversation_id: str,
        teacher_user_id: str,
        management_system_id: str,
    ) -> AIChatConversationModel:
        item = await self.repo.get_conversation(conversation_id)
        if not item or item.is_deleted:
            raise ValueError("对话不存在")
        if item.teacher_user_id != teacher_user_id or item.management_system_id != management_system_id:
            raise ValueError("无权访问该对话")
        return item

    async def _refresh_short_memory_cache(self, conversation_id: str) -> None:
        message_limit = max(settings.AI_SHORT_MEMORY_TURNS * 2, 2)
        messages = await self.repo.list_recent_messages(conversation_id, message_limit)
        payload = [
            {
                "id": item.id,
                "role": item.role,
                "content": item.content,
                "created_at": item.created_at.isoformat() if item.created_at else "",
            }
            for item in messages
        ]
        redis = get_redis()
        await redis.set(self._short_memory_cache_key(conversation_id), json.dumps(payload, ensure_ascii=False), ex=3600)

    async def _load_short_memory_window(self, conversation_id: str) -> list[AIChatMessageModel]:
        redis = get_redis()
        cached = await redis.get(self._short_memory_cache_key(conversation_id))
        if cached:
            rows = json.loads(cached)
            messages: list[AIChatMessageModel] = []
            for row in rows:
                messages.append(
                    AIChatMessageModel(
                        id=row.get("id"),
                        conversation_id=conversation_id,
                        role=row.get("role"),
                        content=row.get("content"),
                        created_at=datetime.fromisoformat(row.get("created_at")) if row.get("created_at") else datetime.now(),
                    )
                )
            return messages
        message_limit = max(settings.AI_SHORT_MEMORY_TURNS * 2, 2)
        rows = await self.repo.list_recent_messages(conversation_id, message_limit)
        await self._refresh_short_memory_cache(conversation_id)
        return rows

    async def _persist_long_memory_facts(
        self,
        conversation_id: str,
        message_id: str,
        teacher_user_id: str,
        management_system_id: str,
        student_id: str | None,
        tool_calls: list[AIChatToolCall],
    ) -> None:
        facts = self._extract_facts_from_tool_calls(tool_calls)
        if not facts:
            return
        await self.repo.create_memory_facts(
            conversation_id=conversation_id,
            message_id=message_id,
            teacher_user_id=teacher_user_id,
            management_system_id=management_system_id,
            student_id=student_id,
            facts=facts,
        )

    async def _load_long_memory_facts(self, teacher_user_id: str, management_system_id: str) -> list[dict[str, Any]]:
        items = await self.repo.list_latest_memory_facts(
            teacher_user_id=teacher_user_id,
            management_system_id=management_system_id,
            limit=settings.AI_LONG_MEMORY_FACT_LIMIT,
        )
        return [
            {
                "fact_type": item.fact_type,
                "fact_key": item.fact_key,
                "fact_value": item.fact_value_json,
                "student_id": item.student_id,
                "created_at": item.created_at.isoformat() if item.created_at else "",
            }
            for item in items
        ]

    @staticmethod
    def _extract_facts_from_tool_calls(tool_calls: list[AIChatToolCall]) -> list[dict[str, Any]]:
        facts: list[dict[str, Any]] = []
        for call in tool_calls:
            name = call.name
            if name == "get_student_recent_assignments":
                for item in call.result.get("items", []):
                    assignment_id = str(item.get("assignment_id") or "")
                    if not assignment_id:
                        continue
                    facts.append(
                        {
                            "fact_type": "assignment_submission",
                            "fact_key": f"assignment:{assignment_id}",
                            "fact_value": item,
                        }
                    )
            if name == "get_student_handwriting_quality":
                student_id = str(call.args.get("student_id") or "")
                if student_id:
                    facts.append(
                        {
                            "fact_type": "handwriting_quality",
                            "fact_key": f"quality:{student_id}",
                            "fact_value": call.result,
                        }
                    )
        return facts

    @staticmethod
    def _to_conversation_response(item: AIChatConversationModel) -> AIChatConversation:
        return AIChatConversation(
            conversation_id=item.id,
            title=item.title,
            management_system_id=item.management_system_id,
            created_at=item.created_at.isoformat() if item.created_at else "",
            updated_at=item.updated_at.isoformat() if item.updated_at else "",
        )

    @staticmethod
    def _to_message_response(item: AIChatMessageModel) -> AIChatMessage:
        return AIChatMessage(
            message_id=item.id,
            conversation_id=item.conversation_id,
            role=item.role,
            content=item.content,
            tool_calls=[AIChatToolCall(**entry) for entry in (item.tool_calls_json or [])],
            created_at=item.created_at.isoformat() if item.created_at else "",
        )

    @staticmethod
    def _extract_student_id(message: str) -> str | None:
        matched = STUDENT_ID_PATTERN.search(message)
        return matched.group(1) if matched else None

    @staticmethod
    def _to_sse(event: AIChatStreamEvent) -> str:
        return f"event: {event.event}\ndata: {json.dumps(event.data, ensure_ascii=False)}\n\n"

    @staticmethod
    def _chunk_text(text: str, chunk_size: int) -> list[str]:
        if chunk_size <= 0 or not text:
            return [text]
        return [text[index:index + chunk_size] for index in range(0, len(text), chunk_size)]

    @staticmethod
    def _short_memory_cache_key(conversation_id: str) -> str:
        return f"ai_chat:short_memory:{conversation_id}"
