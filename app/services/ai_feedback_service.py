# -*- coding: utf-8 -*-
"""
为什么这样做：OCR 识别文字作为锚点与图片一起发给视觉模型，
补偿纯视觉模型对笔画细节理解不稳定的问题。
特殊逻辑：任意步骤失败时写 status=failed 静默退出，不影响提交主流程。
"""

import base64
import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from volcenginesdkarkruntime import AsyncArk

from app.core.config import settings
from app.repositories.submission_repo import SubmissionRepository
from app.services.ocr_service import OCRService

logger = logging.getLogger(__name__)

_PROMPT_TEMPLATE = (
    "你是书法评审专家。图片是一个学生手写的汉字「{char}」。\n"
    "请从以下三个维度评分（1-10分）并给出总评：\n"
    "- stroke_score：笔画质量（起收笔、粗细变化）\n"
    "- structure_score：结构布局（间架比例、重心）\n"
    "- overall_score：整体气韵\n"
    "以 JSON 格式返回，不要输出其他内容。示例：\n"
    '{{{"stroke_score":7,"structure_score":8,"overall_score":6,"summary":"..."}}}'
)

_JSON_PATTERN = re.compile(r'\{.*\}', re.DOTALL)


class AIFeedbackService:
    def __init__(self, db: AsyncSession):
        self.repo = SubmissionRepository(db)
        self.ocr = OCRService()
        self._ark_client: Optional[AsyncArk] = None

    def _get_ark_client(self) -> AsyncArk:
        if self._ark_client is None:
            self._ark_client = AsyncArk(
                base_url=(settings.ARK_BASE_URL or settings.AI_BASE_URL or "").rstrip("/"),
                api_key=settings.ARK_API_KEY or settings.AI_API_KEY or "",
            )
        return self._ark_client

    def _get_vision_model(self) -> str:
        model = settings.ARK_VISION_MODEL or settings.ARK_MODEL or settings.AI_MODEL or ""
        if not model:
            raise ValueError("缺少视觉模型配置，请设置 ARK_VISION_MODEL")
        return model

    async def generate(self, submission_id: str) -> None:
        submission = await self.repo.get(submission_id)
        if not submission:
            logger.warning("generate_ai_feedback: submission %s 不存在", submission_id)
            return

        image_paths: List[str] = submission.image_paths or []
        if not image_paths:
            await self.repo.update(submission, {
                "ai_feedback": {"status": "done", "generated_at": _now(), "items": []}
            })
            return

        try:
            items = []
            for idx, path in enumerate(image_paths):
                char = await self._recognize_char(path)
                scores = await self._call_vision_model(path, char)
                items.append({
                    "image_index": idx,
                    "char": char,
                    "stroke_score": scores.get("stroke_score"),
                    "structure_score": scores.get("structure_score"),
                    "overall_score": scores.get("overall_score"),
                    "summary": scores.get("summary", ""),
                })
            await self.repo.update(submission, {
                "ai_feedback": {"status": "done", "generated_at": _now(), "items": items}
            })
        except Exception as exc:
            logger.error("AI 评语生成失败 submission=%s: %s", submission_id, exc)
            await self.repo.update(submission, {
                "ai_feedback": {"status": "failed", "generated_at": _now(), "items": []}
            })

    async def _recognize_char(self, image_path: str) -> str:
        try:
            result = await self.ocr.recognize_image(image_path)
            if isinstance(result, list):
                return "".join(result)
            return str(result) if result else ""
        except Exception:
            return ""

    async def _call_vision_model(self, image_path: str, char: str) -> Dict[str, Any]:
        b64 = _encode_image(image_path)
        char_label = char if char else "（字符未识别）"
        prompt = _PROMPT_TEMPLATE.format(char=char_label)
        response = await self._get_ark_client().chat.completions.create(
            model=self._get_vision_model(),
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                    {"type": "text", "text": prompt},
                ],
            }],
            stream=False,
        )
        raw = response.choices[0].message.content or ""
        return _parse_json_response(raw)


def _encode_image(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _parse_json_response(raw: str) -> Dict[str, Any]:
    match = _JSON_PATTERN.search(raw)
    if not match:
        raise ValueError(f"模型未返回有效 JSON: {raw[:200]}")
    return json.loads(match.group())


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")
