import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Any, AsyncIterator

from volcenginesdkarkruntime import AsyncArk
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
from app.utils.redis_cache import CACHE_TTL_LONG, cache_delete, cache_get, cache_set

logger = logging.getLogger(__name__)

STUDENT_ID_PATTERN = re.compile(r"(stu_[a-zA-Z0-9]+|[a-zA-Z0-9]{10,50})")

SYSTEM_PROMPT = (
    "你是教师工作台中的教学助手。\n"
    "你可以使用 search_resources 工具搜索课程、作业、学生、教学班级、汉字、讨论等资源。\n"
    "当用户要求查找或筛选资源时，主动调用搜索工具，将结果以列表形式呈现，每条结果附带可点击的链接。\n"
    "优先依据工具结果回答，结论要简洁，给出可执行建议。\n"
    "如缺少必要上下文，要明确指出。"
)

# LLM function calling 工具定义
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_resources",
            "description": (
                "在教师工作台中搜索课程、作业、学生、教学班级、汉字、讨论等资源。"
                "当用户想查找、搜索、筛选任何教学资源时调用此工具。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": "搜索关键词",
                    },
                    "modules": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": [
                                "course", "assignment", "student",
                                "teaching_class", "hanzi", "discussion",
                            ],
                        },
                        "description": "限定搜索的模块范围，不传则搜索全部模块",
                    },
                },
                "required": ["keyword"],
            },
        },
    },
]


class AIChatService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AIChatRepository(db)
        self.tools_service = AIToolsService(db)
        self.ark_client = AsyncArk(
            base_url=self._get_base_url(),
            api_key=self._get_api_key(),
        )

    async def stream_chat(self, body: AIChatRequest, teacher_user_id: str) -> AsyncIterator[str]:
        conversation = await self._ensure_conversation(
            conversation_id=body.conversation_id or generate_id(),
            first_message=body.message,
            teacher_user_id=teacher_user_id,
        )
        await self.repo.create_message(
            message_id=generate_id(),
            conversation_id=conversation.id,
            role="user",
            content=body.message,
            tool_calls_json=[],
        )

        short_messages, long_memory = await asyncio.gather(
            self._load_short_memory_window(conversation.id),
            self._load_long_memory_facts(teacher_user_id),
        )
        messages = self._build_messages(body.message, short_messages, long_memory)
        yield self._to_sse(AIChatStreamEvent(event="status", data={"phase": "analysis", "message": "正在分析问题"}))

        # 第一轮调用 LLM（流式），检查是否需要 function calling
        tool_calls_record: list[AIChatToolCall] = []
        first_stream = None
        try:
            first_stream = await self.ark_client.chat.completions.create(
                model=self._get_model(),
                messages=messages,
                tools=TOOL_DEFINITIONS,
                tool_choice="auto",
                stream=True,
            )
        except Exception as exc:
            logger.error("调用 AI 模型失败: %s", exc)
            error_answer = "当前 AI 服务不可用，请稍后重试。"
            yield self._to_sse(AIChatStreamEvent(event="message_chunk", data={"content": error_answer}))
            yield self._to_sse(AIChatStreamEvent(event="done", data={
                "conversation_id": conversation.id, "message_id": "", "tool_calls": [], "answer": error_answer,
            }))
            return

        # 收集第一轮流式响应
        first_response_content = ""
        first_response_thinking = ""
        first_tool_call_id = ""
        first_tool_call_name = ""
        first_tool_call_args = ""
        finish_reason = None

        async for chunk in first_stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            finish_reason = chunk.choices[0].finish_reason

            # 流式输出思考过程
            reasoning_content = getattr(delta, "reasoning_content", None)
            if reasoning_content:
                first_response_thinking += str(reasoning_content)
                yield self._to_sse(
                    AIChatStreamEvent(event="thinking_chunk", data={"content": str(reasoning_content)})
                )

            # 收集内容（如果有）
            if delta.content:
                first_response_content += delta.content

            # 收集工具调用信息
            if delta.tool_calls:
                for tool_call_delta in delta.tool_calls:
                    if tool_call_delta.id:
                        first_tool_call_id = tool_call_delta.id
                    if tool_call_delta.function:
                        if tool_call_delta.function.name:
                            first_tool_call_name = tool_call_delta.function.name
                        if tool_call_delta.function.arguments:
                            first_tool_call_args += tool_call_delta.function.arguments

        # 如果 LLM 决定调用工具
        if finish_reason == "tool_calls" and first_tool_call_name:
            # 构建 assistant 消息
            assistant_message = {
                "role": "assistant",
                "content": first_response_content or None,
                "tool_calls": [{
                    "id": first_tool_call_id,
                    "type": "function",
                    "function": {
                        "name": first_tool_call_name,
                        "arguments": first_tool_call_args,
                    },
                }],
            }
            messages.append(assistant_message)

            fn_name = first_tool_call_name
            fn_args = json.loads(first_tool_call_args) if first_tool_call_args else {}

            yield self._to_sse(AIChatStreamEvent(
                event="tool_call_start",
                data={"name": fn_name, "args": fn_args},
            ))

            tool_result = await self._execute_tool(
                fn_name, fn_args, teacher_user_id,
            )
            tool_calls_record.append(AIChatToolCall(
                name=fn_name, args=fn_args, result=tool_result,
            ))

            yield self._to_sse(AIChatStreamEvent(
                event="tool_call_result",
                data={"name": fn_name, "result": tool_result},
            ))

            # 将工具结果作为 tool message 追加
            messages.append({
                "role": "tool",
                "tool_call_id": first_tool_call_id,
                "content": json.dumps(tool_result, ensure_ascii=False),
            })

        # 流式调用 LLM 生成最终回答（无论是否经过工具调用）
        yield self._to_sse(AIChatStreamEvent(event="status", data={"phase": "answer", "message": "正在生成回复"}))
        collector = await self._stream_model_response(messages)
        async for sse_line in collector:
            if sse_line:
                yield sse_line
        final_answer = self._normalize_message_content(collector.collected_text)

        assistant_message = await self.repo.create_message(
            message_id=generate_id(),
            conversation_id=conversation.id,
            role="assistant",
            content=final_answer,
            tool_calls_json=[item.model_dump() for item in tool_calls_record],
        )
        await self.repo.touch_conversation(conversation)
        await self._persist_long_memory_facts(
            conversation_id=conversation.id,
            message_id=assistant_message.id,
            teacher_user_id=teacher_user_id,
            student_id=body.student_id or self._extract_student_id(body.message),
            tool_calls=tool_calls_record,
        )
        await self.repo.commit()
        await self._refresh_short_memory_cache(conversation.id)

        yield self._to_sse(
            AIChatStreamEvent(
                event="done",
                data={
                    "conversation_id": conversation.id,
                    "message_id": assistant_message.id,
                    "tool_calls": [call.model_dump() for call in tool_calls_record],
                    "answer": final_answer,
                },
            )
        )

    async def _execute_tool(
        self,
        name: str,
        args: dict[str, Any],
        teacher_user_id: str,
    ) -> dict[str, Any]:
        """根据工具名称分派执行，返回结果字典。"""
        if name == "search_resources":
            return await self.tools_service.search_resources(
                keyword=args.get("keyword", ""),
                teacher_user_id=teacher_user_id,
                modules=args.get("modules"),
                limit=args.get("limit", 10),
            )
        return {"error": f"未知工具: {name}"}

    async def _stream_model_response(
        self,
        messages: list[dict[str, Any]],
    ) -> "_StreamCollector":
        """流式调用 LLM 并返回一个可迭代的收集器，同时收集完整文本。"""
        stream = await self.ark_client.chat.completions.create(
            model=self._get_model(),
            messages=messages,
            stream=True,
        )
        return _StreamCollector(stream)

    def _build_messages(
        self,
        user_message: str,
        short_messages: list[AIChatMessageModel],
        long_memory_facts: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        short_context = "\n".join(
            [f"{item.role}: {self._normalize_message_content(item.content)}" for item in short_messages]
        )
        long_context = "\n".join([json.dumps(item, ensure_ascii=False) for item in long_memory_facts])
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
        ]
        if short_context:
            messages.append({"role": "system", "content": f"短期记忆（会话窗口）：\n{short_context}"})
        if long_context:
            messages.append({"role": "system", "content": f"长期记忆（工具事实）：\n{long_context}"})
        messages.append({"role": "user", "content": user_message})
        return messages

    async def list_conversations(
        self,
        teacher_user_id: str,
        limit: int = 30,
        offset: int = 0,
        page: int | None = None,
        size: int | None = None,
    ) -> AIChatConversationListResponse:
        items = await self.repo.list_conversations(
            teacher_user_id=teacher_user_id,
            limit=limit,
            offset=offset,
        )
        total = await self.repo.count_conversations(teacher_user_id)
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
        limit: int = 100,
        offset: int = 0,
        page: int | None = None,
        size: int | None = None,
    ) -> AIChatMessageListResponse:
        conversation = await self._load_accessible_conversation(conversation_id, teacher_user_id)
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
        body: AIChatConversationRenameRequest,
    ) -> AIChatConversation:
        conversation = await self._load_accessible_conversation(conversation_id, teacher_user_id)
        item = await self.repo.rename_conversation(conversation, body.title.strip())
        await self.repo.commit()
        return self._to_conversation_response(item)

    async def delete_conversation(
        self,
        conversation_id: str,
        teacher_user_id: str,
    ) -> None:
        conversation = await self._load_accessible_conversation(conversation_id, teacher_user_id)
        await self.repo.soft_delete_conversation(conversation)
        await self.repo.commit()
        redis = get_redis()
        await cache_delete(redis, self._short_memory_cache_key(conversation_id))

    def _get_base_url(self) -> str:
        base = (settings.ARK_BASE_URL or settings.AI_BASE_URL or "").rstrip("/")
        if not base:
            raise ValueError("缺少 AI 服务地址配置")
        return base

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
        teacher_user_id: str,
    ) -> AIChatConversationModel:
        item = await self.repo.get_conversation(conversation_id)
        if item:
            if item.teacher_user_id != teacher_user_id:
                raise ValueError("无权访问该对话")
            if item.is_deleted:
                raise ValueError("对话已删除")
            return item
        title = first_message.strip()[:20] or "新对话"
        return await self.repo.create_conversation(
            conversation_id=conversation_id,
            teacher_user_id=teacher_user_id,
            title=title,
        )

    async def _load_accessible_conversation(
        self,
        conversation_id: str,
        teacher_user_id: str,
    ) -> AIChatConversationModel:
        item = await self.repo.get_conversation(conversation_id)
        if not item or item.is_deleted:
            raise ValueError("对话不存在")
        if item.teacher_user_id != teacher_user_id:
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
        await cache_set(redis, self._short_memory_cache_key(conversation_id), payload, ttl=CACHE_TTL_LONG)

    async def _load_short_memory_window(self, conversation_id: str) -> list[AIChatMessageModel]:
        redis = get_redis()
        rows = await cache_get(redis, self._short_memory_cache_key(conversation_id))
        if rows:
            messages: list[AIChatMessageModel] = []
            for row in rows:
                messages.append(
                    AIChatMessageModel(
                        id=row.get("id"),
                        conversation_id=conversation_id,
                        role=row.get("role"),
                        content=row.get("content"),
                        created_at=datetime.fromisoformat(
                            row.get("created_at")) if row.get("created_at") else datetime.now(),
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
            student_id=student_id,
            facts=facts,
        )

    async def _load_long_memory_facts(self, teacher_user_id: str) -> list[dict[str, Any]]:
        items = await self.repo.list_latest_memory_facts(
            teacher_user_id=teacher_user_id,
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
    def _normalize_message_content(content: str) -> str:
        if not content:
            return ""
        return re.sub(r'https?://(?:localhost|127\.0\.0\.1):\d+(/[^\s"<]*)', r"\1", content)

    @staticmethod
    def _to_sse(event: AIChatStreamEvent) -> str:
        return f"event: {event.event}\ndata: {json.dumps(event.data, ensure_ascii=False)}\n\n"

    @staticmethod
    def _short_memory_cache_key(conversation_id: str) -> str:
        return f"ai_chat:short_memory:{conversation_id}"


class _StreamCollector:
    """包装 AsyncStream，迭代时产出 SSE message_chunk 事件，同时收集完整文本。"""

    def __init__(self, stream: Any) -> None:
        self._stream = stream
        self.collected_text: str = ""

    def __aiter__(self) -> "_StreamCollector":
        return self

    async def __anext__(self) -> str:
        try:
            chunk = await self._stream.__anext__()
        except StopAsyncIteration:
            raise
        delta = chunk.choices[0].delta if chunk.choices else None
        if not delta:
            return ""
        payload = ""
        reasoning_content = getattr(delta, "reasoning_content", None)
        if reasoning_content:
            event = AIChatStreamEvent(event="thinking_chunk", data={"content": str(reasoning_content)})
            payload += AIChatService._to_sse(event)
        if delta.content:
            text = delta.content
            self.collected_text += text
            event = AIChatStreamEvent(event="message_chunk", data={"content": text})
            payload += AIChatService._to_sse(event)
        return payload
