import asyncio
import json
import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
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

MAX_TOOL_ROUNDS = 5

STUDENT_ID_PATTERN = re.compile(r"(stu_[a-zA-Z0-9]+|[a-zA-Z0-9]{10,50})")

SYSTEM_PROMPT = (
    "你是教师工作台中的教学助手。\n"
    "你可以使用 search_resources 工具搜索课程、作业、学生、教学班级、汉字、讨论等资源。\n"
    "你可以使用 search_hanzi_dictionary 工具从共享汉字字典中按拼音、笔画数、笔画模式等条件精确查询汉字。\n"
    "当用户要求根据拼音推荐汉字时，先用 search_hanzi_dictionary 以拼音条件查询所有同音字，"
    "再多次调用该工具以不同笔画数范围（如 1-5 画、6-10 画、11-15 画、16+ 画）分批获取，"
    "最后从各笔画段中挑选共 10 个拼音相近但笔画差异大的汉字，以简洁表格形式列出（序号、汉字、拼音、笔画数）。"
    "每个推荐汉字需附带 id 字段以便前端勾选添加。\n"
    "当用户要求查找或筛选资源时，主动调用搜索工具，将结果以列表形式呈现。\n"
    "优先依据工具结果回答，结论要简洁，给出可执行建议。\n"
    "如缺少必要上下文，要明确指出。"
)

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
    {
        "type": "function",
        "function": {
            "name": "search_hanzi_dictionary",
            "description": (
                "搜索共享汉字字典，支持拼音、笔画数范围、笔画模式、汉字精确匹配。"
                "可用于根据拼音推荐笔画差异大的汉字。返回含 id、character、pinyin、stroke_count、stroke_pattern 的列表。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pinyin": {
                        "type": "string",
                        "description": "拼音全拼或首字母，如 'shu'",
                    },
                    "stroke_count_min": {
                        "type": "integer",
                        "description": "最小笔画数，如 1",
                    },
                    "stroke_count_max": {
                        "type": "integer",
                        "description": "最大笔画数，如 10",
                    },
                    "stroke_pattern": {
                        "type": "string",
                        "description": "笔画模式，如 'heng-shu-pie-na'",
                    },
                    "character": {
                        "type": "string",
                        "description": "精确汉字，如 '书'",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回数量上限，默认 50",
                    },
                },
            },
        },
    },
]


class StreamPhase(str, Enum):
    THINKING = "thinking"
    TOOL_CALLING = "tool_calling"
    ANSWERING = "answering"
    DONE = "done"


@dataclass
class StreamContext:
    """状态机流转上下文。"""
    messages: list[dict[str, Any]]
    tool_calls_record: list[dict[str, Any]] = field(default_factory=list)
    round: int = 0
    next_phase: StreamPhase = StreamPhase.THINKING
    thinking_content: str = ""
    thinking_tool_calls: list[dict[str, Any]] = field(default_factory=list)


class AIChatService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = AIChatRepository(db)
        self.tools_service = AIToolsService(db)
        self.ark_client = AsyncArk(
            base_url=self._get_base_url(),
            api_key=self._get_api_key(),
        )

    # ---- 工具分派字典 ----

    def _tool_search_resources(self, args: dict[str, Any], teacher_user_id: str):
        """工具: search_resources"""
        return self.tools_service.search_resources(
            keyword=args.get("keyword", ""),
            teacher_user_id=teacher_user_id,
            modules=args.get("modules"),
            limit=args.get("limit", 10),
        )

    def _tool_search_hanzi_dictionary(self, args: dict[str, Any], _teacher_user_id: str):
        """工具: search_hanzi_dictionary"""
        return self.tools_service.search_hanzi_dictionary(
            pinyin=args.get("pinyin"),
            stroke_count_min=args.get("stroke_count_min"),
            stroke_count_max=args.get("stroke_count_max"),
            stroke_pattern=args.get("stroke_pattern"),
            character=args.get("character"),
            limit=args.get("limit", 50),
        )

    @property
    def _TOOL_HANDLERS(self) -> dict[str, Callable[..., Any]]:
        return {
            "search_resources": self._tool_search_resources,
            "search_hanzi_dictionary": self._tool_search_hanzi_dictionary,
        }

    async def _execute_tool(
        self, name: str, args: dict[str, Any], teacher_user_id: str,
    ) -> dict[str, Any]:
        """按名称分派工具调用。"""
        handler = self._TOOL_HANDLERS.get(name)
        if handler is None:
            return {"error": f"未知工具: {name}"}
        return await handler(args, teacher_user_id)

    # ---- 状态机 ----

    async def stream_chat(self, body: AIChatRequest, teacher_user_id: str) -> AsyncIterator[str]:
        conversation = await self._ensure_conversation(
            conversation_id=body.conversation_id or generate_id(),
            first_message=body.message,
            teacher_user_id=teacher_user_id,
        )
        await self.repo.create_message(
            message_id=generate_id(), conversation_id=conversation.id,
            role="user", content=body.message, tool_calls_json=[],
        )

        short_messages, long_memory = await asyncio.gather(
            self._load_short_memory_window(conversation.id),
            self._load_long_memory_facts(teacher_user_id),
        )
        messages = self._build_messages(body.message, short_messages, long_memory)

        ctx = StreamContext(
            messages=messages,
            next_phase=StreamPhase.THINKING,
        )

        while ctx.next_phase != StreamPhase.DONE:
            handler = self._PHASE_HANDLERS[ctx.next_phase]
            async for sse in handler(self, ctx, teacher_user_id):
                yield sse

        # 持久化
        tool_calls_models = [AIChatToolCall(**tc) for tc in ctx.tool_calls_record]
        assistant_message = await self.repo.create_message(
            message_id=generate_id(), conversation_id=conversation.id,
            role="assistant", content=ctx.thinking_content,
            tool_calls_json=[tc.model_dump() for tc in tool_calls_models],
        )
        await self.repo.touch_conversation(conversation)
        await self._persist_long_memory_facts(
            conversation_id=conversation.id, message_id=assistant_message.id,
            teacher_user_id=teacher_user_id,
            student_id=body.student_id or self._extract_student_id(body.message),
            tool_calls=tool_calls_models,
        )
        await self.repo.commit()
        await self._refresh_short_memory_cache(conversation.id)

        yield self._to_sse(AIChatStreamEvent(event="done", data={
            "conversation_id": conversation.id,
            "message_id": assistant_message.id,
            "tool_calls": [tc.model_dump() for tc in tool_calls_models],
            "answer": ctx.thinking_content,
        }))

    # ---- Phase handlers ----

    async def _handle_thinking(self, ctx: StreamContext, teacher_user_id: str) -> AsyncIterator[str]:
        """THINKING: LLM + tools 流式调用，实时输出内容，同时收集工具调用。"""
        ctx.round += 1
        yield self._to_sse(AIChatStreamEvent(event="status", data={
            "phase": "analysis", "message": "正在分析问题",
        }))
        try:
            stream = await self.ark_client.chat.completions.create(
                model=self._get_model(), messages=ctx.messages,
                tools=TOOL_DEFINITIONS, tool_choice="auto", stream=True,
            )
        except Exception as exc:
            logger.error("调用 AI 模型失败: %s", exc)
            ctx.thinking_content = "当前 AI 服务不可用，请稍后重试。"
            yield self._to_sse(AIChatStreamEvent(event="message_chunk", data={"content": ctx.thinking_content}))
            ctx.next_phase = StreamPhase.DONE
            return

        # 流式输出 + 收集
        content = ""
        tool_calls: list[dict[str, Any]] = []
        finish_reason = None

        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            finish_reason = chunk.choices[0].finish_reason

            reasoning = getattr(delta, "reasoning_content", None)
            if reasoning:
                yield self._to_sse(AIChatStreamEvent(event="thinking_chunk", data={"content": str(reasoning)}))

            if delta.content:
                content += delta.content
                yield self._to_sse(AIChatStreamEvent(event="message_chunk", data={"content": delta.content}))

            if delta.tool_calls:
                for tc in delta.tool_calls:
                    if tc.id:
                        tool_calls.append({"id": tc.id, "name": "", "args": ""})
                    if tc.function:
                        if tc.function.name and tool_calls:
                            tool_calls[-1]["name"] = tc.function.name
                        if tc.function.arguments and tool_calls:
                            tool_calls[-1]["args"] += tc.function.arguments

        has_tool = finish_reason == "tool_calls" and tool_calls

        if has_tool and ctx.round < MAX_TOOL_ROUNDS:
            ctx.messages.append({
                "role": "assistant",
                "content": content or None,
                "tool_calls": [
                    {"id": tc["id"], "type": "function", "function": {"name": tc["name"], "arguments": tc["args"]}}
                    for tc in tool_calls
                ],
            })
            ctx.thinking_tool_calls = tool_calls
            ctx.next_phase = StreamPhase.TOOL_CALLING
        elif has_tool and ctx.round >= MAX_TOOL_ROUNDS:
            yield self._to_sse(AIChatStreamEvent(event="status", data={
                "phase": "answer", "message": f"已达到最大工具调用轮次（{MAX_TOOL_ROUNDS}），开始生成回答",
            }))
            ctx.next_phase = StreamPhase.ANSWERING
        else:
            # finish=stop: 内容已流式输出给用户，直接完成
            ctx.thinking_content = self._normalize_message_content(content)
            ctx.messages.append({"role": "assistant", "content": content})
            ctx.next_phase = StreamPhase.DONE

    async def _handle_tool_calling(self, ctx: StreamContext, teacher_user_id: str) -> AsyncIterator[str]:
        """TOOL_CALLING: 执行本轮所有工具调用。"""
        for tc in ctx.thinking_tool_calls:
            fn_name = tc["name"]
            fn_args = json.loads(tc["args"]) if tc["args"] else {}
            yield self._to_sse(AIChatStreamEvent(event="tool_call_start", data={
                "name": fn_name, "args": fn_args,
            }))
            tool_result = await self._execute_tool(fn_name, fn_args, teacher_user_id)
            yield self._to_sse(AIChatStreamEvent(event="tool_call_result", data={
                "name": fn_name, "result": tool_result,
            }))
            ctx.tool_calls_record.append({"name": fn_name, "args": fn_args, "result": tool_result})
            ctx.messages.append({
                "role": "tool", "tool_call_id": tc["id"],
                "content": json.dumps(tool_result, ensure_ascii=False),
            })
        ctx.next_phase = StreamPhase.THINKING

    async def _handle_answering(self, ctx: StreamContext, teacher_user_id: str) -> AsyncIterator[str]:
        """ANSWERING: 工具轮次耗尽后的最终无工具 LLM 调用，流式输出。"""
        yield self._to_sse(AIChatStreamEvent(event="status", data={
            "phase": "answer", "message": "正在生成回复",
        }))
        try:
            stream = await self.ark_client.chat.completions.create(
                model=self._get_model(), messages=ctx.messages, stream=True,
            )
        except Exception as exc:
            logger.error("生成回答失败: %s", exc)
            err = "生成回答时出错，请稍后重试。"
            yield self._to_sse(AIChatStreamEvent(event="message_chunk", data={"content": err}))
            ctx.thinking_content = err
            ctx.next_phase = StreamPhase.DONE
            return
        content = ""
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                content += delta.content
                yield self._to_sse(AIChatStreamEvent(event="message_chunk", data={"content": delta.content}))
        ctx.thinking_content = self._normalize_message_content(content)
        ctx.next_phase = StreamPhase.DONE

    _PHASE_HANDLERS: dict[StreamPhase, Callable] = {
        StreamPhase.THINKING: _handle_thinking,
        StreamPhase.TOOL_CALLING: _handle_tool_calling,
        StreamPhase.ANSWERING: _handle_answering,
    }

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
