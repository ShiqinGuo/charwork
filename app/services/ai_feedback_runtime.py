# -*- coding: utf-8 -*-
"""
AI 反馈运行时。

统一封装 OCR、视觉模型、多附件总结模型的调用细节，
避免附件级评价与提交总评重复维护同一套客户端逻辑。
"""

import base64
import json
import logging
import re
from typing import Any, Dict, Optional

from volcenginesdkarkruntime import AsyncArk

from app.core.config import settings
from app.services.ocr_service import OCRService


logger = logging.getLogger(__name__)

_ATTACHMENT_PROMPT_TEMPLATE = (
    "你是书法评审专家。图片是一个学生手写的汉字「{char}」。\n"
    "请从以下四个维度评分（1-10分）并给出简短评语：\n"
    "- stroke_quality：笔画规范性（笔画完整性、规范性、起收笔自然度）\n"
    "- structure_balance：结构协调性（字内各部分比例关系、重心分布）\n"
    "- layout_placement：整体布局性（字在书写区域中的位置安排是否恰当）\n"
    "- aesthetic_appeal：书写美观性（综合视觉效果，在前述维度上的整体观感）\n"
    "以 JSON 格式返回，不要输出其他内容。示例：\n"
    '{{"stroke_quality":7,"structure_balance":8,"layout_placement":6,"aesthetic_appeal":7,"summary":"..."}}'
)
_SUMMARY_PROMPT_TEMPLATE = (
    "你是书法老师，请根据以下多个汉字图片的评价结果生成一次总评。\n"
    "输入是 JSON 数组，每项包含 char、stroke_quality、structure_balance、layout_placement、aesthetic_appeal、summary。\n"
    "请输出 JSON，字段必须包含：summary、strengths、improvements、overall_level，\n"
    "以及各维度综合平均分：stroke_quality_avg、structure_balance_avg、layout_placement_avg、aesthetic_appeal_avg。\n"
    "strengths 和 improvements 必须是字符串数组，不要输出额外文本。"
)
_JSON_PATTERN = re.compile(r"\{.*\}", re.DOTALL)


class AIFeedbackRuntime:
    def __init__(self) -> None:
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

    def _get_text_model(self) -> str:
        model = settings.ARK_MODEL or settings.AI_MODEL or settings.ARK_VISION_MODEL or ""
        if not model:
            raise ValueError("缺少文本模型配置，请设置 ARK_MODEL 或 AI_MODEL")
        return model

    async def recognize_char(self, image_path: str) -> str:
        try:
            result = await self.ocr.recognize_image(image_path)
        except Exception as exc:
            logger.warning("OCR 识别失败 path=%s: %s", image_path, exc)
            return ""
        if isinstance(result, list):
            return "".join(result)
        return str(result) if result else ""

    async def call_attachment_model(self, image_path: str, char: str) -> Dict[str, Any]:
        char_label = char if char else "（字符未识别）"
        prompt = _ATTACHMENT_PROMPT_TEMPLATE.format(char=char_label)
        response = await self._get_ark_client().chat.completions.create(
            model=self._get_vision_model(),
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": _build_vision_image_url(image_path)}},
                    {"type": "text", "text": prompt},
                ],
            }],
            stream=False,
        )
        raw = response.choices[0].message.content or ""
        return _parse_json_response(raw)

    async def call_summary_model(self, feedback_items: list[dict[str, Any]]) -> Dict[str, Any]:
        payload = json.dumps(feedback_items, ensure_ascii=False)
        response = await self._get_ark_client().chat.completions.create(
            model=self._get_text_model(),
            messages=[{
                "role": "user",
                "content": f"{_SUMMARY_PROMPT_TEMPLATE}\n输入数据：{payload}",
            }],
            stream=False,
        )
        raw = response.choices[0].message.content or ""
        return _parse_json_response(raw)


def _encode_image(image_path: str) -> str:
    with open(image_path, "rb") as file_obj:
        return base64.b64encode(file_obj.read()).decode("utf-8")


def _build_vision_image_url(image_path: str) -> str:
    if image_path.startswith(("http://", "https://")):
        return image_path
    return f"data:image/jpeg;base64,{_encode_image(image_path)}"


def _parse_json_response(raw: str) -> Dict[str, Any]:
    match = _JSON_PATTERN.search(raw)
    if not match:
        raise ValueError(f"模型未返回有效 JSON: {raw[:200]}")
    return json.loads(match.group())
