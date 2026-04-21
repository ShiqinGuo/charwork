from typing import Optional

import pandas as pd
from sqlalchemy import case, delete, func, insert, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hanzi import Hanzi
from app.models.hanzi_dictionary import HanziDataset, HanziDatasetItem, HanziDictionary
from app.utils.hanzi_dictionary_parser import normalize_pinyin_keyword


class HanziDictionaryRepository:
    def __init__(self, db: AsyncSession):
        """
        功能描述：
            初始化HanziDictionaryRepository并准备运行所需的依赖对象。

        参数：
            db (AsyncSession): 数据库会话，用于执行持久化操作。

        返回值：
            None: 无返回值。
        """
        self.db = db

    @staticmethod
    def _apply_filters(query, character: Optional[str] = None,
                       pinyin: Optional[str] = None, stroke_count: Optional[int] = None):
        """
        功能描述：
            处理filters。

        参数：
            query (Any): 检索或查询条件。
            character (Optional[str]): 字符串结果。
            pinyin (Optional[str]): 字符串结果。
            stroke_count (Optional[int]): 数量值。

        返回值：
            None: 无返回值。
        """
        if character:
            keyword = character.strip()
            if keyword:
                query = query.where(HanziDictionary.character.contains(keyword))
        if pinyin:
            normalized = normalize_pinyin_keyword(pinyin)
            if normalized:
                query = query.where(
                    func.lower(
                        func.replace(
                            func.coalesce(
                                HanziDictionary.pinyin,
                                ""),
                            " ",
                            "")).contains(normalized))
        if stroke_count is not None:
            query = query.where(HanziDictionary.stroke_count == stroke_count)
        return query

    async def count_all(self) -> int:
        """
        功能描述：
            统计all数量。

        参数：
            无。

        返回值：
            int: 返回统计结果。
        """
        result = await self.db.execute(select(func.count()).select_from(HanziDictionary))
        return int(result.scalar() or 0)

    async def get_all(self) -> list[dict]:
        """
        功能描述：
            按条件获取all。

        参数：
            无。

        返回值：
            list[dict]: 返回列表形式的结果数据。
        """
        result = await self.db.execute(select(HanziDictionary))
        items = result.scalars().all()
        return [
            {
                "id": item.id,
                "character": item.character,
                "stroke_count": item.stroke_count,
                "stroke_pattern": item.stroke_pattern,
                "pinyin": item.pinyin,
                "source": item.source,
            }
            for item in items
        ]

    async def get_by_character(self, character: str) -> Optional[HanziDictionary]:
        """
        功能描述：
            按条件获取bycharacter。

        参数：
            character (str): 字符串结果。

        返回值：
            Optional[HanziDictionary]: 返回查询到的结果对象；未命中时返回 None。
        """
        result = await self.db.execute(select(HanziDictionary).where(HanziDictionary.character == character))
        return result.scalars().first()

    async def list_candidates_by_character(self, character: str, limit: int = 5) -> list[HanziDictionary]:
        if not character:
            return []
        result = await self.db.execute(
            select(HanziDictionary)
            .where(HanziDictionary.character == character)
            .order_by(HanziDictionary.stroke_count.asc(), HanziDictionary.character.asc())
            .limit(limit)
        )
        return result.scalars().all()

    async def get(self, dictionary_id: str) -> Optional[HanziDictionary]:
        """
        功能描述：
            获取HanziDictionaryRepository。

        参数：
            dictionary_id (str): 字典ID。

        返回值：
            Optional[HanziDictionary]: 返回处理结果对象；无可用结果时返回 None。
        """
        result = await self.db.execute(select(HanziDictionary).where(HanziDictionary.id == dictionary_id))
        return result.scalars().first()

    async def list_by_ids_in_order(self, dictionary_ids: list[str]) -> list[HanziDictionary]:
        """
        功能描述：
            按条件查询by标识列表inorder列表。

        参数：
            dictionary_ids (list[str]): 字典ID列表。

        返回值：
            list[HanziDictionary]: 返回列表形式的结果数据。
        """
        if not dictionary_ids:
            return []
        ordering = case({dictionary_id: index for index,
                         dictionary_id in enumerate(dictionary_ids)},
                        value=HanziDictionary.id)
        result = await self.db.execute(
            select(HanziDictionary)
            .where(HanziDictionary.id.in_(dictionary_ids))
            .order_by(ordering)
        )
        return result.scalars().all()

    async def list_all_filtered(
        self,
        skip: int = 0,
        limit: int = 20,
        character: Optional[str] = None,
        pinyin: Optional[str] = None,
        stroke_count: Optional[int] = None,
        keyword: Optional[str] = None,
    ) -> list[HanziDictionary]:
        """
        功能描述：
            按条件查询allfiltered列表。

        参数：
            skip (int): 分页偏移量。
            limit (int): 单次查询的最大返回数量。
            character (Optional[str]): 字符串结果。
            pinyin (Optional[str]): 字符串结果。
            stroke_count (Optional[int]): 数量值。
            keyword (Optional[str]): 字符串结果。

        返回值：
            list[HanziDictionary]: 返回列表形式的结果数据。
        """
        query = select(HanziDictionary)
        query = self._apply_filters(query, character=character, pinyin=pinyin, stroke_count=stroke_count)
        if keyword:
            normalized = normalize_pinyin_keyword(keyword)
            trimmed = keyword.strip()
            conditions = []
            if trimmed:
                conditions.append(HanziDictionary.character.contains(trimmed))
            if normalized:
                conditions.append(
                    func.lower(func.replace(func.coalesce(HanziDictionary.pinyin, ""), " ", "")).contains(normalized)
                )
            if conditions:
                query = query.where(or_(*conditions))
        query = query.order_by(HanziDictionary.stroke_count.asc(),
                               HanziDictionary.character.asc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def count_filtered(
        self,
        character: Optional[str] = None,
        pinyin: Optional[str] = None,
        stroke_count: Optional[int] = None,
        keyword: Optional[str] = None,
    ) -> int:
        """
        功能描述：
            统计filtered数量。

        参数：
            character (Optional[str]): 字符串结果。
            pinyin (Optional[str]): 字符串结果。
            stroke_count (Optional[int]): 数量值。
            keyword (Optional[str]): 字符串结果。

        返回值：
            int: 返回统计结果。
        """
        query = select(func.count()).select_from(HanziDictionary)
        query = self._apply_filters(query, character=character, pinyin=pinyin, stroke_count=stroke_count)
        if keyword:
            normalized = normalize_pinyin_keyword(keyword)
            trimmed = keyword.strip()
            conditions = []
            if trimmed:
                conditions.append(HanziDictionary.character.contains(trimmed))
            if normalized:
                conditions.append(
                    func.lower(func.replace(func.coalesce(HanziDictionary.pinyin, ""), " ", "")).contains(normalized)
                )
            if conditions:
                query = query.where(or_(*conditions))
        result = await self.db.execute(query)
        return int(result.scalar() or 0)

    async def list_search_candidates(
        self,
        character: Optional[str] = None,
        pinyin: Optional[str] = None,
        stroke_count: Optional[int] = None,
        keyword: Optional[str] = None,
    ) -> list[HanziDictionary]:
        """
        功能描述：
            按条件查询检索candidates列表。

        参数：
            character (Optional[str]): 字符串结果。
            pinyin (Optional[str]): 字符串结果。
            stroke_count (Optional[int]): 数量值。
            keyword (Optional[str]): 字符串结果。

        返回值：
            list[HanziDictionary]: 返回列表形式的结果数据。
        """
        query = select(HanziDictionary)
        query = self._apply_filters(query, character=character, pinyin=pinyin, stroke_count=stroke_count)
        if keyword:
            normalized = normalize_pinyin_keyword(keyword)
            trimmed = keyword.strip()
            conditions = []
            if trimmed:
                conditions.append(HanziDictionary.character.contains(trimmed))
            if normalized:
                conditions.append(
                    func.lower(func.replace(func.coalesce(HanziDictionary.pinyin, ""), " ", "")).contains(normalized)
                )
            if conditions:
                query = query.where(or_(*conditions))
        query = query.where(HanziDictionary.stroke_pattern.is_not(None)).order_by(
            HanziDictionary.stroke_count.asc(),
            HanziDictionary.character.asc(),
        )
        result = await self.db.execute(query)
        return result.scalars().all()

    async def upsert_many(self, rows: pd.DataFrame, force: bool = False, batch_size: int = 1000) -> tuple[int, int]:
        """
        功能描述：
            新增或更新many。

        参数：
            rows (pd.DataFrame): pd.DataFrame 类型的数据。
            force (bool): 布尔值结果。
            batch_size (int): 整数结果。

        返回值：
            tuple[int, int]: 返回tuple[int, int]类型的处理结果。
        """
        if rows.empty:
            return 0, 0

        created = 0
        for index in range(0, len(rows), batch_size):
            chunk = rows.iloc[index:index + batch_size]
            payload = chunk.to_dict(orient="records")
            statement = insert(HanziDictionary.__table__).values(payload)
            await self.db.execute(statement)
            created += len(payload)
        await self.db.commit()
        return created, 0


class HanziDatasetRepository:
    def __init__(self, db: AsyncSession):
        """
        功能描述：
            初始化HanziDatasetRepository并准备运行所需的依赖对象。

        参数：
            db (AsyncSession): 数据库会话，用于执行持久化操作。

        返回值：
            None: 无返回值。
        """
        self.db = db

    async def get(self, dataset_id: str, created_by_user_id: str) -> Optional[HanziDataset]:
        """
        功能描述：
            获取HanziDatasetRepository。

        参数：
            dataset_id (str): 数据集ID。
            created_by_user_id (str): 数据集创建者用户ID。

        返回值：
            Optional[HanziDataset]: 返回处理结果对象；无可用结果时返回 None。
        """
        result = await self.db.execute(
            select(HanziDataset).where(
                HanziDataset.id == dataset_id,
                HanziDataset.created_by_user_id == created_by_user_id,
            )
        )
        return result.scalars().first()

    async def list_all(self, created_by_user_id: str, skip: int, limit: int) -> list[HanziDataset]:
        """
        功能描述：
            按条件查询all列表。

        参数：
            created_by_user_id (str): 数据集创建者用户ID。
            skip (int): 分页偏移量。
            limit (int): 单次查询的最大返回数量。

        返回值：
            list[HanziDataset]: 返回列表形式的结果数据。
        """
        result = await self.db.execute(
            select(HanziDataset)
            .where(HanziDataset.created_by_user_id == created_by_user_id)
            .order_by(HanziDataset.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def count_all(self, created_by_user_id: str) -> int:
        """
        功能描述：
            统计all数量。

        参数：
            created_by_user_id (str): 数据集创建者用户ID。

        返回值：
            int: 返回统计结果。
        """
        result = await self.db.execute(
            select(func.count()).select_from(HanziDataset).where(
                HanziDataset.created_by_user_id == created_by_user_id)
        )
        return int(result.scalar() or 0)

    async def count_items(self, dataset_id: str) -> int:
        result = await self.db.execute(
            select(func.count())
            .select_from(HanziDatasetItem)
            .join(Hanzi, Hanzi.id == HanziDatasetItem.hanzi_id)
            .where(HanziDatasetItem.dataset_id == dataset_id)
        )
        return int(result.scalar() or 0)

    async def list_items(
        self,
        dataset_id: str,
        created_by_user_id: str,
        skip: int,
        limit: int,
    ) -> list[Hanzi]:
        result = await self.db.execute(
            select(Hanzi)
            .join(HanziDatasetItem, HanziDatasetItem.hanzi_id == Hanzi.id)
            .join(HanziDataset, HanziDataset.id == HanziDatasetItem.dataset_id)
            .where(
                HanziDatasetItem.dataset_id == dataset_id,
                HanziDataset.created_by_user_id == created_by_user_id,
                or_(
                    Hanzi.created_by_user_id == created_by_user_id,
                    Hanzi.created_by_user_id.is_(None),
                ),
            )
            .order_by(Hanzi.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def count_items_in_scope(self, dataset_id: str, created_by_user_id: str) -> int:
        result = await self.db.execute(
            select(func.count())
            .select_from(HanziDatasetItem)
            .join(Hanzi, Hanzi.id == HanziDatasetItem.hanzi_id)
            .join(HanziDataset, HanziDataset.id == HanziDatasetItem.dataset_id)
            .where(
                HanziDatasetItem.dataset_id == dataset_id,
                HanziDataset.created_by_user_id == created_by_user_id,
                or_(
                    Hanzi.created_by_user_id == created_by_user_id,
                    Hanzi.created_by_user_id.is_(None),
                ),
            )
        )
        return int(result.scalar() or 0)

    async def create(self, dataset: HanziDataset) -> HanziDataset:
        """
        功能描述：
            创建HanziDatasetRepository。

        参数：
            dataset (HanziDataset): HanziDataset 类型的数据。

        返回值：
            HanziDataset: 返回HanziDataset类型的处理结果。
        """
        self.db.add(dataset)
        await self.db.commit()
        await self.db.refresh(dataset)
        return dataset

    async def replace_items(self, dataset_id: str, hanzi_ids: list[str]) -> None:
        await self.db.execute(delete(HanziDatasetItem).where(HanziDatasetItem.dataset_id == dataset_id))
        for hanzi_id in hanzi_ids:
            self.db.add(HanziDatasetItem(dataset_id=dataset_id, hanzi_id=hanzi_id))
        await self.db.commit()

    async def get_item_hanzi_ids(self, dataset_id: str) -> set[str]:
        result = await self.db.execute(
            select(HanziDatasetItem.hanzi_id).where(HanziDatasetItem.dataset_id == dataset_id)
        )
        return set(result.scalars().all())

    async def append_items(self, dataset_id: str, hanzi_ids: list[str]) -> int:
        if not hanzi_ids:
            return 0
        existing_ids = await self.get_item_hanzi_ids(dataset_id)
        append_ids = [hanzi_id for hanzi_id in hanzi_ids if hanzi_id not in existing_ids]
        if not append_ids:
            return 0
        for hanzi_id in append_ids:
            self.db.add(HanziDatasetItem(dataset_id=dataset_id, hanzi_id=hanzi_id))
        await self.db.commit()
        return len(append_ids)

    async def delete_dataset(self, dataset_id: str) -> None:
        await self.db.execute(delete(HanziDatasetItem).where(HanziDatasetItem.dataset_id == dataset_id))
        await self.db.execute(delete(HanziDataset).where(HanziDataset.id == dataset_id))
        await self.db.commit()
