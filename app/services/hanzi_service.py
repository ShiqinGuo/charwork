"""
为什么这样做：汉字服务保持轻量 CRUD，并统一输出字段，降低前后端字段别名不一致的接入成本。
特殊逻辑：笔画能力从全局 stroke_service 读取，避免每次请求重复加载笔画源数据。
"""

from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.hanzi_repo import HanziRepository
from app.repositories.hanzi_dictionary_repo import HanziDictionaryRepository
from fastapi import UploadFile

from app.schemas.hanzi import (
    HanziCreate,
    HanziListResponse,
    HanziOCRBatchPrefillItem,
    HanziOCRBatchPrefillResponse,
    HanziOCRPrefillResponse,
    HanziResponse,
    HanziUpdate,
    OCRDictionaryCandidate,
)
from app.core.app_state import stroke_service
from app.services.ocr_service import OCRService
from app.utils.pagination import build_paged_response
from app.utils.hanzi_dictionary_parser import split_stroke_pattern


class HanziService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = HanziRepository(db)
        self.dictionary_repo = HanziDictionaryRepository(db)
        self.ocr_service = OCRService()

    async def get_hanzi(self, id: str, current_user_id: str) -> Optional[HanziResponse]:
        """
        功能描述：
            按条件获取汉字。

        参数：
            id (str): 目标记录ID。
            current_user_id (str): 当前用户ID，用于限制私有字库作用域。

        返回值：
            Optional[HanziResponse]: 返回查询到的结果对象；未命中时返回 None。
        """
        hanzi = await self.repo.get(id, current_user_id)
        if hanzi:
            return self._to_response(hanzi)
        return None

    async def get_hanzi_by_char(self, char: str, current_user_id: str) -> Optional[HanziResponse]:
        """
        功能描述：
            根据字符获取汉字实例。

        参数：
            char (str): 字符串结果。
            current_user_id (str): 当前用户ID，用于限制私有字库作用域。

        返回值：
            Optional[HanziResponse]: 返回查询到的结果对象；未命中时返回 None。
        """
        hanzi = await self.repo.get_by_character(char, current_user_id)
        if hanzi:
            return self._to_response(hanzi)
        return None

    async def list_hanzi(self, skip: int = 0, limit: int = 20,
                         structure: Optional[str] = None,
                         level: Optional[str] = None,
                         variant: Optional[str] = None,
                         search: Optional[str] = None,
                         character: Optional[str] = None,
                         pinyin: Optional[str] = None,
                         stroke_count: Optional[int] = None,
                         stroke_pattern: Optional[str] = None,
                         dataset_id: Optional[str] = None,
                         source: Optional[str] = None,
                         current_user_id: Optional[str] = None,
                         page: Optional[int] = None,
                         size: Optional[int] = None) -> HanziListResponse:
        items = await self.repo.get_all(
            skip=skip,
            limit=limit,
            structure=structure,
            level=level,
            variant=variant,
            search=search,
            created_by_user_id=current_user_id,
            character=character,
            pinyin=pinyin,
            stroke_count=stroke_count,
            stroke_pattern=stroke_pattern,
            dataset_id=dataset_id,
            source=source,
        )
        total = await self.repo.count(
            structure=structure,
            level=level,
            variant=variant,
            search=search,
            created_by_user_id=current_user_id,
            character=character,
            pinyin=pinyin,
            stroke_count=stroke_count,
            stroke_pattern=stroke_pattern,
            dataset_id=dataset_id,
            source=source,
        )
        payload = build_paged_response(
            items=[self._to_response(item) for item in items],
            total=total,
            pagination={"page": page, "size": size, "skip": skip, "limit": limit},
        )
        return HanziListResponse(**payload)

    async def create_hanzi(self, hanzi_in: HanziCreate, current_user_id: str) -> HanziResponse:
        """
        功能描述：
            创建汉字。

        参数：
            hanzi_in (HanziCreate): 创建汉字的请求体。
            current_user_id (str): 当前用户ID，用于归属新建字库条目。

        返回值：
            HanziResponse: 返回创建的汉字对象。
        """
        prepared = await self._prepare_payload(hanzi_in)
        hanzi = await self.repo.create(prepared, current_user_id)
        return self._to_response(hanzi)

    async def update_hanzi(self, id: str, hanzi_in: HanziUpdate, current_user_id: str) -> Optional[HanziResponse]:
        """
        功能描述：
            更新汉字。

        参数：
            id (str): 目标记录ID。
            hanzi_in (HanziUpdate): 更新汉字的请求体。
            current_user_id (str): 当前用户ID，用于限制私有字库作用域。

        返回值：
            Optional[HanziResponse]: 返回更新后的汉字对象；未命中时返回 None。
        """
        hanzi = await self.repo.get(id, current_user_id)
        if not hanzi:
            return None

        prepared = await self._prepare_payload(hanzi_in)
        updated_hanzi = await self.repo.update(hanzi, prepared)
        return self._to_response(updated_hanzi)

    async def delete_hanzi(self, id: str, current_user_id: str) -> bool:
        """
        功能描述：
            删除汉字。

        参数：
            id (str): 目标记录ID。
            current_user_id (str): 当前用户ID，用于限制私有字库作用域。

        返回值：
            bool: 返回操作是否成功。
        """
        hanzi = await self.repo.get(id, current_user_id)
        if not hanzi:
            return False

        await self.repo.delete(hanzi)
        return True

    async def get_strokes(self, ch: str) -> dict:
        """
        功能描述：
            根据字符获取汉字的笔画信息。

        参数：
            ch (str): 目标汉字字符。

        返回值：
            dict: 返回包含字符、笔画数和笔画顺序的字典。
        """
        return {
            "character": ch,
            "stroke_count": await self.repo.get_stroke_count(ch),
            "stroke_order": await self.repo.get_stroke_order(ch),
        }

    async def search_by_stroke_order(
        self,
        stroke_pattern: str,
        skip: int = 0,
        limit: int = 20,
        current_user_id: Optional[str] = None,
        page: Optional[int] = None,
        size: Optional[int] = None,
    ) -> HanziListResponse:
        items = await self.repo.search_by_stroke_order(stroke_pattern, skip, limit, current_user_id)
        payload = build_paged_response(
            items=[self._to_response(item) for item in items],
            total=len(items),
            pagination={"page": page, "size": size, "skip": skip, "limit": limit},
        )
        return HanziListResponse(**payload)

    async def build_prefill_by_upload(self, file: UploadFile) -> HanziOCRPrefillResponse:
        file_path = await self._save_upload_file(file)
        try:
            recognized = await self.ocr_service.recognize_image(file_path)
            recognized_text = self._normalize_recognized_text(recognized)
            return await self._build_prefill_by_character(recognized_text)
        finally:
            Path(file_path).unlink(missing_ok=True)

    async def build_batch_prefill_by_uploads(self, files: list[UploadFile]) -> HanziOCRBatchPrefillResponse:
        """
        功能描述：
            批量处理OCR识别结果，生成汉字的预填充数据。

        参数：
            files (list[UploadFile]): 上传的OCR识别文件列表。

        返回值：
            HanziOCRBatchPrefillResponse: 返回包含批量预填充数据的响应对象。
        """
        items: list[HanziOCRBatchPrefillItem] = []
        for file in files:
            file_path = await self._save_upload_file(file)
            try:
                recognized = await self.ocr_service.recognize_image(file_path)
                recognized_text = self._normalize_recognized_text(recognized)
                prefill = await self._build_prefill_by_character(recognized_text)
                items.append(
                    HanziOCRBatchPrefillItem(
                        file_name=file.filename or Path(file_path).name,
                        recognized_text=recognized_text,
                        draft=prefill.draft,
                        candidates=prefill.candidates,
                    )
                )
            finally:
                Path(file_path).unlink(missing_ok=True)
        return HanziOCRBatchPrefillResponse(total=len(items), items=items)

    async def _prepare_payload(self, payload_model: HanziCreate | HanziUpdate) -> HanziCreate | HanziUpdate:
        payload = payload_model.model_dump(exclude_unset=True)
        dictionary_id = payload.get("dictionary_id")
        if dictionary_id:
            dictionary_item = await self.dictionary_repo.get(dictionary_id)
            if not dictionary_item:
                raise ValueError("关联的共享字典条目不存在")
            payload["character"] = payload.get("character") or dictionary_item.character
            payload["pinyin"] = payload.get("pinyin") or dictionary_item.pinyin
            payload["stroke_count"] = payload.get("stroke_count") or dictionary_item.stroke_count
            payload["stroke_pattern"] = payload.get("stroke_pattern") or dictionary_item.stroke_pattern
            payload["source"] = payload.get("source") or dictionary_item.source
            payload["stroke_order"] = payload.get(
                "stroke_order") or stroke_service.get_stroke_order(dictionary_item.character)
        elif payload.get("character") and not payload.get("stroke_order"):
            payload["stroke_order"] = stroke_service.get_stroke_order(payload["character"])
        if isinstance(payload_model, HanziCreate):
            return HanziCreate(**payload)
        return HanziUpdate(**payload)

    async def _build_prefill_by_character(self, character: str) -> HanziOCRPrefillResponse:
        candidates = await self.dictionary_repo.list_candidates_by_character(character, limit=5)
        selected = candidates[0] if candidates else None
        draft = HanziCreate(
            dictionary_id=selected.id if selected else None,
            character=character,
            pinyin=selected.pinyin if selected else None,
            stroke_count=selected.stroke_count if selected else None,
            stroke_pattern=selected.stroke_pattern if selected else None,
            source=selected.source if selected else "ocr",
            stroke_order=stroke_service.get_stroke_order(character),
        )
        return HanziOCRPrefillResponse(
            recognized_text=character,
            draft=draft,
            candidates=[
                OCRDictionaryCandidate(
                    id=item.id,
                    character=item.character,
                    pinyin=item.pinyin,
                    stroke_count=item.stroke_count,
                    stroke_pattern=item.stroke_pattern,
                    source=item.source,
                )
                for item in candidates
            ],
        )

    @staticmethod
    def _normalize_recognized_text(recognized: str | list[str]) -> str:
        if isinstance(recognized, list):
            text = "".join(recognized).strip()
        else:
            text = recognized.strip()
        if not text:
            raise ValueError("OCR 未识别到有效汉字")
        return text[0]

    @staticmethod
    async def _save_upload_file(file: UploadFile) -> str:
        file.file.seek(0)
        suffix = Path(file.filename or "upload.png").suffix or ".png"
        with NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            content = await file.read()
            temp_file.write(content)
            return temp_file.name

    @staticmethod
    def _to_response(item) -> HanziResponse:
        return HanziResponse(
            id=item.id,
            dictionary_id=item.dictionary_id,
            character=item.character,
            char=item.character,
            image_path=item.image_path,
            stroke_count=item.stroke_count,
            structure=item.structure,
            stroke_order=item.stroke_order,
            stroke_pattern=item.stroke_pattern,
            stroke_units=split_stroke_pattern(item.stroke_pattern),
            pinyin=item.pinyin,
            source=item.source,
            level=item.level,
            comment=item.comment,
            variant=item.variant,
            standard_image=item.standard_image,
            created_at=str(item.created_at) if item.created_at else None,
            updated_at=str(item.updated_at) if item.updated_at else None,
        )
