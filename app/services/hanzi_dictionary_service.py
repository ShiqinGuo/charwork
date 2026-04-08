"""
为什么这样做：共享字典服务优先走 ES，失败时自动降级数据库过滤，确保检索能力在异常场景仍可用。
特殊逻辑：初始化按批量 upsert 并同步索引，兼顾大批数据导入的性能与一致性边界。
"""

import logging
from typing import Optional

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hanzi import Hanzi
from app.models.hanzi_dictionary import HanziDataset
from app.repositories.hanzi_dictionary_repo import HanziDatasetRepository, HanziDictionaryRepository
from app.schemas.hanzi import HanziCreate, HanziResponse
from app.schemas.hanzi_dictionary import (
    HanziDatasetAppendItemsRequest,
    HanziDatasetAppendItemsResponse,
    HanziDatasetCreate,
    HanziDatasetCreateHanziResponse,
    HanziDatasetDetailResponse,
    HanziDatasetItemsListResponse,
    HanziDatasetListResponse,
    HanziDatasetResponse,
    HanziDictionaryListResponse,
    HanziDictionaryResponse,
    HanziDictionaryInitResponse,
)
from app.services.hanzi_service import HanziService
from app.services.hanzi_dictionary_search_service import HanziDictionarySearchService
from app.utils.pagination import build_paged_response
from app.utils.hanzi_dictionary_parser import (
    contains_exact_stroke_units,
    parse_strokes_file,
    resolve_pinyin,
    split_stroke_pattern,
)


logger = logging.getLogger(__name__)


class HanziDictionaryService:
    DEFAULT_INIT_BATCH_SIZE = 1000

    def __init__(self, db: AsyncSession):
        """
        功能描述：
            初始化HanziDictionaryService并准备运行所需的依赖对象。

        参数：
            db (AsyncSession): 数据库会话，用于执行持久化操作。

        返回值：
            None: 无返回值。
        """
        self.db = db
        self.repo = HanziDictionaryRepository(db)
        self.dataset_repo = HanziDatasetRepository(db)
        self.search_service = HanziDictionarySearchService(db)

    async def get_dictionary_entry(self, dictionary_id: str) -> Optional[HanziDictionaryResponse]:
        """
        功能描述：
            按条件获取字典条目。

        参数：
            dictionary_id (str): 字典ID。

        返回值：
            Optional[HanziDictionaryResponse]: 返回查询到的结果对象；未命中时返回 None。
        """
        item = await self.repo.get(dictionary_id)
        if not item:
            return None
        return self._to_dictionary_response(item)

    async def list_dictionary_entries(
        self,
        skip: int = 0,
        limit: int = 20,
        page: Optional[int] = None,
        size: Optional[int] = None,
        character: Optional[str] = None,
        pinyin: Optional[str] = None,
        stroke_count: Optional[int] = None,
        stroke_pattern: Optional[str] = None,
        keyword: Optional[str] = None,
    ) -> HanziDictionaryListResponse:
        """
        功能描述：
            按条件查询字典条目列表。

        参数：
            skip (int): 分页偏移量。
            limit (int): 单次查询的最大返回数量。
            page (Optional[int]): 当前页码。
            size (Optional[int]): 每页条数。
            character (Optional[str]): 字符串结果。
            pinyin (Optional[str]): 字符串结果。
            stroke_count (Optional[int]): 数量值。
            stroke_pattern (Optional[str]): 字符串结果。
            keyword (Optional[str]): 字符串结果。

        返回值：
            HanziDictionaryListResponse: 返回列表或分页查询结果。
        """
        normalized_stroke_pattern = stroke_pattern.strip() if stroke_pattern else None
        try:
            search_result = await self.search_service.search(
                skip=skip,
                limit=limit,
                character=character,
                pinyin=pinyin,
                stroke_count=stroke_count,
                stroke_pattern=normalized_stroke_pattern,
                keyword=keyword,
            )
            dictionary_items = await self.repo.list_by_ids_in_order(search_result["ids"])
            total = search_result["total"]
            items = [self._to_dictionary_response(item) for item in dictionary_items]
        except Exception:
            logger.exception("共享字典 ES 检索失败，已自动降级为数据库过滤")
            items, total = await self._list_dictionary_entries_by_db_fallback(
                skip=skip,
                limit=limit,
                character=character,
                pinyin=pinyin,
                stroke_count=stroke_count,
                stroke_pattern=normalized_stroke_pattern,
                keyword=keyword,
            )
        payload = build_paged_response(
            items=items,
            total=total,
            pagination={"page": page, "size": size, "skip": skip, "limit": limit},
        )
        return HanziDictionaryListResponse(**payload)

    async def initialize_from_strokes(self, file_path: str, force: bool = False) -> HanziDictionaryInitResponse:
        """
        功能描述：
            初始化，从笔画文件加载字典条目。

        参数：
            file_path (str): 文件或资源路径。
            force (bool): 布尔值结果。

        返回值：
            HanziDictionaryInitResponse: 返回HanziDictionaryInitResponse类型的处理结果。
        """
        stroke_frame = self.parse_strokes_file(file_path)
        if stroke_frame.empty:
            await self._sync_search_index(force_reindex=False)
            return HanziDictionaryInitResponse(total=0, created=0, updated=0)

        existing_map = await self.repo.get_all()
        existing_frame = pd.DataFrame(existing_map)
        if existing_frame.empty:
            existing_frame = pd.DataFrame(columns=["character"])
        else:
            existing_frame = existing_frame[["character"]].drop_duplicates()

        merged_frame = pd.merge(
            stroke_frame,
            existing_frame,
            on="character",
            how="outer",
            indicator=True,
        )
        if merged_frame.empty:
            await self._sync_search_index(force_reindex=False)
            return HanziDictionaryInitResponse(total=0, created=0, updated=0)

        new_frame = merged_frame.loc[
            merged_frame["_merge"] == "left_only",
            ["character", "stroke_count", "stroke_pattern"]
        ].copy()
        if new_frame.empty:
            await self._sync_search_index(force_reindex=False)
            return HanziDictionaryInitResponse(total=len(merged_frame), created=0, updated=0)
        new_frame["pinyin"] = new_frame["character"].apply(resolve_pinyin)
        new_frame["source"] = "strokes_txt"

        created, updated = await self.repo.upsert_many(
            new_frame,
            force=force,
            batch_size=self.DEFAULT_INIT_BATCH_SIZE,
        )
        await self._sync_search_index(force_reindex=True)
        return HanziDictionaryInitResponse(total=len(merged_frame), created=created, updated=updated)

    async def list_datasets(
        self,
        management_system_id: str,
        skip: int,
        limit: int,
        page: int,
        size: int,
    ) -> HanziDatasetListResponse:
        """
        功能描述：
            按条件查询数据集列表。

        参数：
            management_system_id (str): 管理系统ID，用于限制数据作用域。
            skip (int): 分页偏移量。
            limit (int): 单次查询的最大返回数量。
            page (int): 当前页码。
            size (int): 每页条数。

        返回值：
            HanziDatasetListResponse: 返回列表或分页查询结果。
        """
        items = await self.dataset_repo.list_all(management_system_id, skip, limit)
        total = await self.dataset_repo.count_all(management_system_id)
        data = []
        for item in items:
            data.append(await self._build_dataset_response(item))
        payload = build_paged_response(
            items=data,
            total=total,
            pagination={"page": page, "size": size, "skip": skip, "limit": limit},
        )
        return HanziDatasetListResponse(**payload)

    async def create_dataset(
        self,
        management_system_id: str,
        created_by_user_id: str,
        body: HanziDatasetCreate,
    ) -> HanziDatasetResponse:
        """
        功能描述：
            创建数据集并返回结果。

        参数：
            management_system_id (str): 管理系统ID，用于限制数据作用域。
            created_by_user_id (str): createdby用户ID。
            body (HanziDatasetCreate): 接口请求体对象。

        返回值：
            HanziDatasetResponse: 返回创建后的结果对象。
        """
        dataset = await self.dataset_repo.create(
            HanziDataset(
                management_system_id=management_system_id,
                name=body.name,
                level=body.level,
                batch_no=body.batch_no,
                created_by_user_id=created_by_user_id,
            )
        )
        if body.hanzi_ids:
            total = await self._count_accessible_hanzi(body.hanzi_ids, management_system_id)
            if total != len(set(body.hanzi_ids)):
                raise ValueError("数据集中包含无效或越权的手写体记录")
            await self.dataset_repo.replace_items(dataset.id, list(dict.fromkeys(body.hanzi_ids)))
        return await self._build_dataset_response(dataset)

    async def get_dataset(self, dataset_id: str, management_system_id: str) -> HanziDatasetDetailResponse:
        dataset = await self._get_dataset_entity(dataset_id, management_system_id)
        payload = await self._build_dataset_response(dataset)
        return HanziDatasetDetailResponse(**payload.model_dump())

    async def list_dataset_items(
        self,
        dataset_id: str,
        management_system_id: str,
        skip: int,
        limit: int,
        page: Optional[int] = None,
        size: Optional[int] = None,
    ) -> HanziDatasetItemsListResponse:
        await self._get_dataset_entity(dataset_id, management_system_id)
        items = await self.dataset_repo.list_items(
            dataset_id=dataset_id,
            management_system_id=management_system_id,
            skip=skip,
            limit=limit,
        )
        total = await self.dataset_repo.count_items_in_scope(dataset_id, management_system_id)
        payload = build_paged_response(
            items=[self._to_hanzi_response(item) for item in items],
            total=total,
            pagination={"page": page, "size": size, "skip": skip, "limit": limit},
        )
        return HanziDatasetItemsListResponse(**payload)

    async def append_dataset_items(
        self,
        dataset_id: str,
        management_system_id: str,
        body: HanziDatasetAppendItemsRequest,
    ) -> HanziDatasetAppendItemsResponse:
        dataset = await self._get_dataset_entity(dataset_id, management_system_id)
        unique_ids = list(dict.fromkeys(body.hanzi_ids))
        if unique_ids:
            total = await self._count_accessible_hanzi(unique_ids, management_system_id)
            if total != len(unique_ids):
                raise ValueError("数据集中包含无效或越权的手写体记录")
        appended_count = await self.dataset_repo.append_items(dataset_id, unique_ids)
        total_items = await self.dataset_repo.count_items_in_scope(dataset_id, management_system_id)
        dataset_payload = await self._build_dataset_response(dataset)
        return HanziDatasetAppendItemsResponse(
            dataset=dataset_payload,
            appended_count=appended_count,
            total_items=total_items,
        )

    async def create_hanzi_in_dataset(
        self,
        dataset_id: str,
        management_system_id: str,
        hanzi_in: HanziCreate,
    ) -> HanziDatasetCreateHanziResponse:
        dataset = await self._get_dataset_entity(dataset_id, management_system_id)
        hanzi_service = HanziService(self.db)
        hanzi = await hanzi_service.create_hanzi(hanzi_in, management_system_id)
        await self.dataset_repo.append_items(dataset_id, [hanzi.id])
        dataset_payload = await self._build_dataset_response(dataset)
        return HanziDatasetCreateHanziResponse(dataset=dataset_payload, hanzi=hanzi)

    async def delete_dataset(self, dataset_id: str, management_system_id: str) -> None:
        await self._get_dataset_entity(dataset_id, management_system_id)
        await self.dataset_repo.delete_dataset(dataset_id)

    async def _count_accessible_hanzi(self, hanzi_ids: list[str], management_system_id: str) -> int:
        if not hanzi_ids:
            return 0
        result = await self.db.execute(
            select(func.count())
            .select_from(Hanzi)
            .where(Hanzi.id.in_(hanzi_ids), Hanzi.management_system_id == management_system_id)
        )
        return int(result.scalar() or 0)

    async def _get_dataset_entity(self, dataset_id: str, management_system_id: str) -> HanziDataset:
        dataset = await self.dataset_repo.get(dataset_id, management_system_id)
        if not dataset:
            raise ValueError("数据集不存在")
        return dataset

    async def _build_dataset_response(self, dataset: HanziDataset) -> HanziDatasetResponse:
        count = await self.dataset_repo.count_items_in_scope(dataset.id, dataset.management_system_id)
        return HanziDatasetResponse(
            id=dataset.id,
            management_system_id=dataset.management_system_id,
            name=dataset.name,
            level=dataset.level,
            batch_no=dataset.batch_no,
            created_by_user_id=dataset.created_by_user_id,
            hanzi_count=count,
            created_at=dataset.created_at,
            updated_at=dataset.updated_at,
        )

    @staticmethod
    def _to_hanzi_response(item: Hanzi) -> HanziResponse:
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
            management_system_id=item.management_system_id,
            created_at=item.created_at.isoformat() if item.created_at else None,
            updated_at=item.updated_at.isoformat() if item.updated_at else None,
        )

    @staticmethod
    def parse_strokes_file(file_path: str) -> pd.DataFrame:
        """
        功能描述：
            解析strokes文件。

        参数：
            file_path (str): 文件或资源路径。

        返回值：
            pd.DataFrame: 返回pd.DataFrame类型的处理结果。
        """
        return parse_strokes_file(file_path)

    async def _list_dictionary_entries_by_db_fallback(
        self,
        skip: int,
        limit: int,
        character: Optional[str],
        pinyin: Optional[str],
        stroke_count: Optional[int],
        stroke_pattern: Optional[str],
        keyword: Optional[str],
    ) -> tuple[list[HanziDictionaryResponse], int]:
        """
        功能描述：
            按条件查询字典条目by数据库fallback列表。

        参数：
            skip (int): 分页偏移量。
            limit (int): 单次查询的最大返回数量。
            character (Optional[str]): 字符串结果。
            pinyin (Optional[str]): 字符串结果。
            stroke_count (Optional[int]): 数量值。
            stroke_pattern (Optional[str]): 字符串结果。
            keyword (Optional[str]): 字符串结果。

        返回值：
            tuple[list[HanziDictionaryResponse], int]: 返回tuple[list[HanziDictionaryResponse], int]类型的处理结果。
        """
        if not stroke_pattern:
            dictionary_items = await self.repo.list_all_filtered(
                skip=skip,
                limit=limit,
                character=character,
                pinyin=pinyin,
                stroke_count=stroke_count,
                keyword=keyword,
            )
            total = await self.repo.count_filtered(
                character=character,
                pinyin=pinyin,
                stroke_count=stroke_count,
                keyword=keyword,
            )
            return [self._to_dictionary_response(item) for item in dictionary_items], total
        candidates = await self.repo.list_search_candidates(
            character=character,
            pinyin=pinyin,
            stroke_count=stroke_count,
            keyword=keyword,
        )
        matched_items = [
            self._to_dictionary_response(item)
            for item in candidates
            if contains_exact_stroke_units(item.stroke_pattern, stroke_pattern)
        ]
        return matched_items[skip:skip + limit], len(matched_items)

    async def _sync_search_index(self, force_reindex: bool) -> None:
        """
        功能描述：
            同步检索索引。

        参数：
            force_reindex (bool): 布尔值结果。

        返回值：
            None: 无返回值。
        """
        try:
            if force_reindex:
                await self.search_service.reindex()
            else:
                await self.search_service.ensure_index_with_bootstrap()
        except Exception:
            logger.exception("共享字典 ES 索引同步失败")

    @staticmethod
    def _to_dictionary_response(item) -> HanziDictionaryResponse:
        """
        功能描述：
            将输入数据转换为字典响应。

        参数：
            item (Any): 当前处理的实体对象。

        返回值：
            HanziDictionaryResponse: 返回HanziDictionaryResponse类型的处理结果。
        """
        return HanziDictionaryResponse(
            id=item.id,
            character=item.character,
            stroke_count=item.stroke_count,
            stroke_pattern=item.stroke_pattern,
            stroke_units=split_stroke_pattern(item.stroke_pattern),
            pinyin=item.pinyin,
            source=item.source,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
