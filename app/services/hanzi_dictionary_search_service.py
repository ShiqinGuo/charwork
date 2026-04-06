"""
为什么这样做：共享字典检索独立索引，支持拼音与笔画组合查询，避免数据库全文扫描开销。
特殊逻辑：笔画重复次数通过动态字段 + 脚本过滤校验，保证“包含且数量满足”的边界语义。
"""

import logging
from datetime import datetime
from typing import Any, Optional

from elasticsearch import NotFoundError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.es_client import get_es_client
from app.models.hanzi_dictionary import HanziDictionary
from app.utils.hanzi_dictionary_parser import (
    build_stroke_unit_count_fields,
    build_stroke_unit_counts,
    encode_stroke_unit_key,
    normalize_pinyin_keyword,
    split_stroke_pattern,
)


logger = logging.getLogger(__name__)


class HanziDictionarySearchService:
    def __init__(self, db: AsyncSession):
        """
        功能描述：
            初始化HanziDictionarySearchService并准备运行所需的依赖对象。

        参数：
            db (AsyncSession): 数据库会话，用于执行持久化操作。

        返回值：
            None: 无返回值。
        """
        self.db = db
        self.es = get_es_client()
        self.index_name = f"{settings.ELASTICSEARCH_INDEX_PREFIX}_hanzi_dictionary"

    async def ensure_index(self) -> None:
        """
        功能描述：
            确保索引存在，必要时自动补齐。

        参数：
            无。

        返回值：
            None: 无返回值。
        """
        exists = await self.es.indices.exists(index=self.index_name)
        if exists:
            return
        await self.es.indices.create(
            index=self.index_name,
            body={
                "mappings": {
                    "properties": {
                        "dictionary_id": {"type": "keyword"},
                        "character": {"type": "keyword"},
                        "pinyin": {"type": "keyword"},
                        "pinyin_normalized": {"type": "keyword"},
                        "stroke_count": {"type": "integer"},
                        "stroke_pattern": {"type": "keyword", "ignore_above": 1024},
                        "stroke_units": {"type": "keyword"},
                        "stroke_unit_counts": {"type": "object", "dynamic": True},
                        "source": {"type": "keyword"},
                        "updated_at": {"type": "date"},
                    }
                }
            },
        )

    async def ensure_index_with_bootstrap(self) -> int:
        """
        功能描述：
            确保索引withbootstrap存在，必要时自动补齐。

        参数：
            无。

        返回值：
            int: 返回int类型的处理结果。
        """
        await self.ensure_index()
        count_response = await self.es.count(index=self.index_name)
        total = int(count_response.get("count", 0))
        if total > 0:
            return 0
        return await self.reindex()

    async def reindex(self) -> int:
        """
        功能描述：
            处理HanziDictionarySearchService。

        参数：
            无。

        返回值：
            int: 返回int类型的处理结果。
        """
        exists = await self.es.indices.exists(index=self.index_name)
        if exists:
            try:
                await self.es.indices.delete(index=self.index_name)
            except NotFoundError:
                pass
        await self.ensure_index()
        items = (await self.db.execute(select(HanziDictionary))).scalars().all()
        for item in items:
            await self.index_document(item, refresh=False)
        await self.es.indices.refresh(index=self.index_name)
        return len(items)

    async def index_document(self, item: HanziDictionary, refresh: bool = False) -> None:
        """
        功能描述：
            处理document。

        参数：
            item (HanziDictionary): 当前处理的实体对象。
            refresh (bool): 布尔值结果。

        返回值：
            None: 无返回值。
        """
        await self.es.index(
            index=self.index_name,
            id=self._document_id(item.id),
            document=self._build_document(item),
            refresh=refresh,
        )

    async def delete_document(self, dictionary_id: str, refresh: bool = False) -> None:
        """
        功能描述：
            删除document。

        参数：
            dictionary_id (str): 字典ID。
            refresh (bool): 布尔值结果。

        返回值：
            None: 无返回值。
        """
        try:
            await self.es.delete(index=self.index_name, id=self._document_id(dictionary_id), refresh=refresh)
        except NotFoundError:
            return

    async def apply_cdc_change(self, operation: str, data: dict[str, Any]) -> None:
        """
        功能描述：
            处理cdcchange。

        参数：
            operation (str): 字符串结果。
            data (dict[str, Any]): 字典形式的结果数据。

        返回值：
            None: 无返回值。
        """
        await self.ensure_index()
        dictionary_id = str(data.get("id") or "")
        if not dictionary_id:
            return
        if operation == "delete":
            await self.delete_document(dictionary_id, refresh=False)
            return
        item = await self._get_dictionary_item(dictionary_id)
        if not item:
            await self.delete_document(dictionary_id, refresh=False)
            return
        await self.index_document(item, refresh=False)

    async def search(
        self,
        skip: int = 0,
        limit: int = 20,
        character: Optional[str] = None,
        pinyin: Optional[str] = None,
        stroke_count: Optional[int] = None,
        stroke_pattern: Optional[str] = None,
        keyword: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        功能描述：
            检索HanziDictionarySearchService。

        参数：
            skip (int): 分页偏移量。
            limit (int): 单次查询的最大返回数量。
            character (Optional[str]): 字符串结果。
            pinyin (Optional[str]): 字符串结果。
            stroke_count (Optional[int]): 数量值。
            stroke_pattern (Optional[str]): 字符串结果。
            keyword (Optional[str]): 字符串结果。

        返回值：
            dict[str, Any]: 返回字典形式的结果数据。
        """
        await self.ensure_index()
        filters: list[dict[str, Any]] = []
        character_keyword = (character or "").strip()
        if character_keyword:
            filters.append({"wildcard": {"character": {"value": f"*{character_keyword}*"}}})
        normalized_pinyin = normalize_pinyin_keyword(pinyin)
        if normalized_pinyin:
            filters.append({"wildcard": {"pinyin_normalized": {"value": f"*{normalized_pinyin}*"}}})
        if stroke_count is not None:
            filters.append({"term": {"stroke_count": stroke_count}})
        keyword_filter = self._build_keyword_filter(keyword)
        if keyword_filter:
            filters.append(keyword_filter)
        filters.extend(self._build_stroke_pattern_filters(stroke_pattern))
        response = await self.es.search(
            index=self.index_name,
            body={
                "query": {"bool": {"filter": filters}},
                "sort": [
                    {"stroke_count": {"order": "asc", "missing": "_last"}},
                    {"character": {"order": "asc"}},
                ],
                "from": skip,
                "size": limit,
                "track_total_hits": True,
            },
        )
        hits = response.get("hits", {})
        items = hits.get("hits", [])
        total = int((hits.get("total") or {}).get("value", 0))
        ids = [str(item.get("_source", {}).get("dictionary_id") or "") for item in items]
        ids = [dictionary_id for dictionary_id in ids if dictionary_id]
        return {"ids": ids, "total": total}

    async def _get_dictionary_item(self, dictionary_id: str) -> Optional[HanziDictionary]:
        """
        功能描述：
            按条件获取字典item。

        参数：
            dictionary_id (str): 字典ID。

        返回值：
            Optional[HanziDictionary]: 返回处理结果对象；无可用结果时返回 None。
        """
        result = await self.db.execute(select(HanziDictionary).where(HanziDictionary.id == dictionary_id))
        return result.scalars().first()

    def _build_keyword_filter(self, keyword: Optional[str]) -> Optional[dict[str, Any]]:
        """
        功能描述：
            构建keywordfilter。

        参数：
            keyword (Optional[str]): 字符串结果。

        返回值：
            Optional[dict[str, Any]]: 返回处理结果对象；无可用结果时返回 None。
        """
        if not keyword:
            return None
        trimmed = keyword.strip()
        normalized = normalize_pinyin_keyword(keyword)
        clauses: list[dict[str, Any]] = []
        if trimmed:
            clauses.append({"wildcard": {"character": {"value": f"*{trimmed}*"}}})
        if normalized:
            clauses.append({"wildcard": {"pinyin_normalized": {"value": f"*{normalized}*"}}})
        if not clauses:
            return None
        return {"bool": {"should": clauses, "minimum_should_match": 1}}

    def _build_stroke_pattern_filters(self, stroke_pattern: Optional[str]) -> list[dict[str, Any]]:
        """
        功能描述：
            构建笔画patternfilters。

        参数：
            stroke_pattern (Optional[str]): 字符串结果。

        返回值：
            list[dict[str, Any]]: 返回列表形式的结果数据。
        """
        query_counts = build_stroke_unit_counts(stroke_pattern)
        if not query_counts:
            return []
        filters: list[dict[str, Any]] = [{"term": {"stroke_units": unit}} for unit in query_counts]
        repeated_counts = {unit: count for unit, count in query_counts.items() if count > 1}
        if not repeated_counts:
            return filters
        script_lines = []
        for unit, count in repeated_counts.items():
            field_key = encode_stroke_unit_key(unit)
            field_name = f"stroke_unit_counts.{field_key}"
            script_lines.append(
                (
                    f"if (!doc.containsKey('{field_name}') "
                    f"|| doc['{field_name}'].size() == 0 "
                    f"|| doc['{field_name}'].value < {count}) return false;"
                )
            )
        script_lines.append("return true;")
        filters.append({"script": {"script": {"lang": "painless", "source": " ".join(script_lines)}}})
        return filters

    @staticmethod
    def _document_id(dictionary_id: str) -> str:
        """
        功能描述：
            处理标识。

        参数：
            dictionary_id (str): 字典ID。

        返回值：
            str: 返回str类型的处理结果。
        """
        return f"hanzi_dictionary_{dictionary_id}"

    @staticmethod
    def _build_document(item: HanziDictionary) -> dict[str, Any]:
        """
        功能描述：
            构建document。

        参数：
            item (HanziDictionary): 当前处理的实体对象。

        返回值：
            dict[str, Any]: 返回字典形式的结果数据。
        """
        updated_at = item.updated_at.isoformat() if isinstance(item.updated_at, datetime) else item.updated_at
        return {
            "dictionary_id": item.id,
            "character": item.character,
            "pinyin": item.pinyin or "",
            "pinyin_normalized": normalize_pinyin_keyword(item.pinyin),
            "stroke_count": item.stroke_count,
            "stroke_pattern": item.stroke_pattern or "",
            "stroke_units": split_stroke_pattern(item.stroke_pattern),
            "stroke_unit_counts": build_stroke_unit_count_fields(item.stroke_pattern),
            "source": item.source,
            "updated_at": updated_at,
        }
