from typing import List, Optional
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.hanzi import Hanzi
from app.schemas.hanzi import HanziCreate, HanziUpdate


class HanziRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, id: str) -> Optional[Hanzi]:
        result = await self.db.execute(select(Hanzi).filter(Hanzi.id == id))
        return result.scalars().first()

    async def get_by_character(self, character: str) -> Optional[Hanzi]:
        result = await self.db.execute(select(Hanzi).filter(Hanzi.character == character))
        return result.scalars().first()

    async def get_all(self, skip: int = 0, limit: int = 100,
                      structure: Optional[str] = None,
                      level: Optional[str] = None,
                      variant: Optional[str] = None,
                      search: Optional[str] = None) -> List[Hanzi]:
        query = select(Hanzi)

        if structure:
            query = query.where(Hanzi.structure == structure)
        if level:
            query = query.where(Hanzi.level == level)
        if variant:
            query = query.where(Hanzi.variant == variant)
        if search:
            query = query.where(or_(
                Hanzi.character.contains(search),
                Hanzi.pinyin.contains(search)
            ))

        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def search_by_stroke_order(self, stroke_pattern: str, skip: int = 0, limit: int = 100) -> List[Hanzi]:
        if not stroke_pattern:
            return []
        tokens = [p.strip() for p in stroke_pattern.split(" ") if p.strip()]
        if not tokens:
            return []
        query = select(Hanzi).where(Hanzi.stroke_order.is_not(None))
        for t in tokens:
            query = query.where(Hanzi.stroke_order.contains(t))
        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def count(self, structure: Optional[str] = None,
                    level: Optional[str] = None,
                    variant: Optional[str] = None,
                    search: Optional[str] = None) -> int:
        query = select(func.count()).select_from(Hanzi)

        if structure:
            query = query.where(Hanzi.structure == structure)
        if level:
            query = query.where(Hanzi.level == level)
        if variant:
            query = query.where(Hanzi.variant == variant)
        if search:
            query = query.where(or_(
                Hanzi.character.contains(search),
                Hanzi.pinyin.contains(search)
            ))

        result = await self.db.execute(query)
        return result.scalar()

    async def create(self, hanzi_in: HanziCreate) -> Hanzi:
        hanzi = Hanzi(**hanzi_in.model_dump())
        self.db.add(hanzi)
        await self.db.commit()
        await self.db.refresh(hanzi)
        return hanzi

    async def update(self, hanzi: Hanzi, hanzi_in: HanziUpdate) -> Hanzi:
        update_data = hanzi_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(hanzi, key, value)

        await self.db.commit()
        await self.db.refresh(hanzi)
        return hanzi

    async def delete(self, hanzi: Hanzi) -> None:
        await self.db.delete(hanzi)
        await self.db.commit()
