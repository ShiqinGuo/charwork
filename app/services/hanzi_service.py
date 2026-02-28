from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.hanzi_repo import HanziRepository
from app.schemas.hanzi import HanziCreate, HanziUpdate, HanziResponse, HanziListResponse
from app.core.app_state import stroke_service


class HanziService:
    def __init__(self, db: AsyncSession):
        self.repo = HanziRepository(db)

    async def get_hanzi(self, id: str) -> Optional[HanziResponse]:
        hanzi = await self.repo.get(id)
        if hanzi:
            return HanziResponse.model_validate(hanzi)
        return None

    async def get_hanzi_by_char(self, char: str) -> Optional[HanziResponse]:
        hanzi = await self.repo.get_by_character(char)
        if hanzi:
            return HanziResponse.model_validate(hanzi)
        return None

    async def list_hanzi(self, skip: int = 0, limit: int = 20,
                         structure: Optional[str] = None,
                         level: Optional[str] = None,
                         variant: Optional[str] = None,
                         search: Optional[str] = None) -> HanziListResponse:
        items = await self.repo.get_all(skip, limit, structure, level, variant, search)
        total = await self.repo.count(structure, level, variant, search)

        return HanziListResponse(
            total=total,
            items=[HanziResponse.model_validate(item) for item in items]
        )

    async def create_hanzi(self, hanzi_in: HanziCreate) -> HanziResponse:
        # 是否需要校验汉字唯一性：可按业务规则在此校验或交由数据库约束
        hanzi = await self.repo.create(hanzi_in)
        return HanziResponse.model_validate(hanzi)

    async def update_hanzi(self, id: str, hanzi_in: HanziUpdate) -> Optional[HanziResponse]:
        hanzi = await self.repo.get(id)
        if not hanzi:
            return None

        updated_hanzi = await self.repo.update(hanzi, hanzi_in)
        return HanziResponse.model_validate(updated_hanzi)

    async def delete_hanzi(self, id: str) -> bool:
        hanzi = await self.repo.get(id)
        if not hanzi:
            return False

        await self.repo.delete(hanzi)
        return True

    def get_strokes(self, ch: str) -> dict:
        return {
            "character": ch,
            "stroke_count": stroke_service.get_stroke_count(ch),
            "stroke_order": stroke_service.get_stroke_order(ch),
        }

    async def search_by_stroke_order(self, stroke_pattern: str, skip: int = 0, limit: int = 20) -> HanziListResponse:
        items = await self.repo.search_by_stroke_order(stroke_pattern, skip, limit)
        return HanziListResponse(
            total=len(items),
            items=[HanziResponse.model_validate(item) for item in items],
        )
