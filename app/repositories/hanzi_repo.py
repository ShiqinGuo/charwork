from typing import List, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hanzi import Hanzi
from app.models.hanzi_dictionary import HanziDatasetItem
from app.schemas.hanzi import HanziCreate, HanziUpdate
from app.utils.hanzi_dictionary_parser import normalize_pinyin_keyword


class HanziRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _apply_filters(
        self,
        query,
        management_system_id: Optional[str] = None,
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
    ):
        if dataset_id:
            query = query.join(HanziDatasetItem, HanziDatasetItem.hanzi_id == Hanzi.id)
            query = query.where(HanziDatasetItem.dataset_id == dataset_id)
        if management_system_id:
            query = query.where(Hanzi.management_system_id == management_system_id)
        if structure:
            query = query.where(Hanzi.structure == structure)
        if level:
            query = query.where(Hanzi.level == level)
        if variant:
            query = query.where(Hanzi.variant == variant)
        if source:
            query = query.where(Hanzi.source == source)
        if character:
            query = query.where(Hanzi.character.contains(character.strip()))
        if pinyin:
            normalized = normalize_pinyin_keyword(pinyin)
            if normalized:
                query = query.where(
                    func.lower(func.replace(func.coalesce(Hanzi.pinyin, ""), " ", "")).contains(normalized)
                )
        if stroke_count is not None:
            query = query.where(Hanzi.stroke_count == stroke_count)
        if stroke_pattern:
            tokens = [token.strip() for token in stroke_pattern.split(" ") if token.strip()]
            pattern_field = func.coalesce(Hanzi.stroke_pattern, Hanzi.stroke_order, "")
            for token in tokens:
                query = query.where(pattern_field.contains(token))
        keyword = search.strip() if search else ""
        normalized_keyword = normalize_pinyin_keyword(keyword) if keyword else ""
        conditions = []
        if keyword:
            conditions.extend(
                [
                    Hanzi.character.contains(keyword),
                    func.coalesce(Hanzi.comment, "").contains(keyword),
                    func.coalesce(Hanzi.source, "").contains(keyword),
                ]
            )
        if normalized_keyword:
            conditions.append(
                func.lower(func.replace(func.coalesce(Hanzi.pinyin, ""), " ", "")).contains(normalized_keyword)
            )
        if conditions:
            query = query.where(or_(*conditions))
        return query

    async def get(self, id: str, management_system_id: Optional[str] = None) -> Optional[Hanzi]:
        query = select(Hanzi).where(Hanzi.id == id)
        if management_system_id:
            query = query.where(Hanzi.management_system_id == management_system_id)
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_by_character(self, character: str, management_system_id: Optional[str] = None) -> Optional[Hanzi]:
        query = select(Hanzi).where(Hanzi.character == character)
        if management_system_id:
            query = query.where(Hanzi.management_system_id == management_system_id)
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        structure: Optional[str] = None,
        level: Optional[str] = None,
        variant: Optional[str] = None,
        search: Optional[str] = None,
        management_system_id: Optional[str] = None,
        character: Optional[str] = None,
        pinyin: Optional[str] = None,
        stroke_count: Optional[int] = None,
        stroke_pattern: Optional[str] = None,
        dataset_id: Optional[str] = None,
        source: Optional[str] = None,
    ) -> List[Hanzi]:
        query = select(Hanzi)
        query = self._apply_filters(
            query,
            management_system_id=management_system_id,
            structure=structure,
            level=level,
            variant=variant,
            search=search,
            character=character,
            pinyin=pinyin,
            stroke_count=stroke_count,
            stroke_pattern=stroke_pattern,
            dataset_id=dataset_id,
            source=source,
        )
        query = query.order_by(Hanzi.updated_at.desc()).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def search_by_stroke_order(
        self,
        stroke_pattern: str,
        skip: int = 0,
        limit: int = 100,
        management_system_id: Optional[str] = None,
        dataset_id: Optional[str] = None,
    ) -> List[Hanzi]:
        return await self.get_all(
            skip=skip,
            limit=limit,
            management_system_id=management_system_id,
            stroke_pattern=stroke_pattern,
            dataset_id=dataset_id,
        )

    async def count(
        self,
        structure: Optional[str] = None,
        level: Optional[str] = None,
        variant: Optional[str] = None,
        search: Optional[str] = None,
        management_system_id: Optional[str] = None,
        character: Optional[str] = None,
        pinyin: Optional[str] = None,
        stroke_count: Optional[int] = None,
        stroke_pattern: Optional[str] = None,
        dataset_id: Optional[str] = None,
        source: Optional[str] = None,
    ) -> int:
        query = select(func.count()).select_from(Hanzi)
        query = self._apply_filters(
            query,
            management_system_id=management_system_id,
            structure=structure,
            level=level,
            variant=variant,
            search=search,
            character=character,
            pinyin=pinyin,
            stroke_count=stroke_count,
            stroke_pattern=stroke_pattern,
            dataset_id=dataset_id,
            source=source,
        )
        result = await self.db.execute(query)
        return int(result.scalar() or 0)

    async def create(self, hanzi_in: HanziCreate, management_system_id: str) -> Hanzi:
        payload = hanzi_in.model_dump()
        payload["management_system_id"] = management_system_id
        payload.pop("char", None)
        hanzi = Hanzi(**payload)
        self.db.add(hanzi)
        await self.db.commit()
        await self.db.refresh(hanzi)
        return hanzi

    async def update(self, hanzi: Hanzi, hanzi_in: HanziUpdate) -> Hanzi:
        update_data = hanzi_in.model_dump(exclude_unset=True)
        update_data.pop("char", None)
        update_data.pop("management_system_id", None)
        for key, value in update_data.items():
            setattr(hanzi, key, value)
        await self.db.commit()
        await self.db.refresh(hanzi)
        return hanzi

    async def delete(self, hanzi: Hanzi) -> None:
        await self.db.delete(hanzi)
        await self.db.commit()

    async def get_stroke_count(self, character: str) -> Optional[int]:
        query = select(Hanzi.stroke_count).where(Hanzi.character == character)
        result = await self.db.execute(query)
        return result.scalar()

    async def get_stroke_order(self, character: str) -> Optional[str]:
        query = select(Hanzi.stroke_order).where(Hanzi.character == character)
        result = await self.db.execute(query)
        return result.scalar()
