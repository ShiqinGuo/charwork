"""
为什么这样做：汉字服务保持轻量 CRUD，并统一输出字段，降低前后端字段别名不一致的接入成本。
特殊逻辑：笔画能力从全局 stroke_service 读取，避免每次请求重复加载笔画源数据。
"""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.hanzi_repo import HanziRepository
from app.schemas.hanzi import HanziCreate, HanziUpdate, HanziResponse, HanziListResponse
from app.core.app_state import stroke_service
from app.utils.pagination import build_paged_response


class HanziService:
    def __init__(self, db: AsyncSession):
        """
        功能描述：
            初始化HanziService并准备运行所需的依赖对象。

        参数：
            db (AsyncSession): 数据库会话，用于执行持久化操作。

        返回值：
            None: 无返回值。
        """
        self.repo = HanziRepository(db)

    async def get_hanzi(self, id: str, management_system_id: str) -> Optional[HanziResponse]:
        """
        功能描述：
            按条件获取汉字。

        参数：
            id (str): 目标记录ID。
            management_system_id (str): 管理系统ID，用于限制数据作用域。

        返回值：
            Optional[HanziResponse]: 返回查询到的结果对象；未命中时返回 None。
        """
        hanzi = await self.repo.get(id, management_system_id)
        if hanzi:
            return self._to_response(hanzi)
        return None

    async def get_hanzi_by_char(self, char: str, management_system_id: str) -> Optional[HanziResponse]:
        """
        功能描述：
            按条件获取汉字by字符。

        参数：
            char (str): 字符串结果。
            management_system_id (str): 管理系统ID，用于限制数据作用域。

        返回值：
            Optional[HanziResponse]: 返回查询到的结果对象；未命中时返回 None。
        """
        hanzi = await self.repo.get_by_character(char, management_system_id)
        if hanzi:
            return self._to_response(hanzi)
        return None

    async def list_hanzi(self, skip: int = 0, limit: int = 20,
                         structure: Optional[str] = None,
                         level: Optional[str] = None,
                         variant: Optional[str] = None,
                         search: Optional[str] = None,
                         management_system_id: Optional[str] = None,
                         page: Optional[int] = None,
                         size: Optional[int] = None) -> HanziListResponse:
        """
        功能描述：
            按条件查询汉字列表。

        参数：
            skip (int): 分页偏移量。
            limit (int): 单次查询的最大返回数量。
            structure (Optional[str]): 字符串结果。
            level (Optional[str]): 字符串结果。
            variant (Optional[str]): 字符串结果。
            search (Optional[str]): 字符串结果。
            management_system_id (Optional[str]): 管理系统ID，用于限制数据作用域。
            page (Optional[int]): 当前页码。
            size (Optional[int]): 每页条数。

        返回值：
            HanziListResponse: 返回列表或分页查询结果。
        """
        items = await self.repo.get_all(skip, limit, structure, level, variant, search, management_system_id)
        total = await self.repo.count(structure, level, variant, search, management_system_id)
        payload = build_paged_response(
            items=[self._to_response(item) for item in items],
            total=total,
            pagination={"page": page, "size": size, "skip": skip, "limit": limit},
        )
        return HanziListResponse(**payload)

    async def create_hanzi(self, hanzi_in: HanziCreate, management_system_id: str) -> HanziResponse:
        """
        功能描述：
            创建汉字并返回结果。

        参数：
            hanzi_in (HanziCreate): 汉字输入对象。
            management_system_id (str): 管理系统ID，用于限制数据作用域。

        返回值：
            HanziResponse: 返回创建后的结果对象。
        """
        hanzi = await self.repo.create(hanzi_in, management_system_id)
        return self._to_response(hanzi)

    async def update_hanzi(self, id: str, hanzi_in: HanziUpdate, management_system_id: str) -> Optional[HanziResponse]:
        """
        功能描述：
            更新汉字并返回最新结果。

        参数：
            id (str): 目标记录ID。
            hanzi_in (HanziUpdate): 汉字输入对象。
            management_system_id (str): 管理系统ID，用于限制数据作用域。

        返回值：
            Optional[HanziResponse]: 返回更新后的结果对象；未命中时返回 None。
        """
        hanzi = await self.repo.get(id, management_system_id)
        if not hanzi:
            return None

        updated_hanzi = await self.repo.update(hanzi, hanzi_in)
        return self._to_response(updated_hanzi)

    async def delete_hanzi(self, id: str, management_system_id: str) -> bool:
        """
        功能描述：
            删除汉字。

        参数：
            id (str): 目标记录ID。
            management_system_id (str): 管理系统ID，用于限制数据作用域。

        返回值：
            bool: 返回操作是否成功。
        """
        hanzi = await self.repo.get(id, management_system_id)
        if not hanzi:
            return False

        await self.repo.delete(hanzi)
        return True

    def get_strokes(self, ch: str) -> dict:
        """
        功能描述：
            按条件获取strokes。

        参数：
            ch (str): 字符串结果。

        返回值：
            dict: 返回字典形式的结果数据。
        """
        return {
            "character": ch,
            "stroke_count": stroke_service.get_stroke_count(ch),
            "stroke_order": stroke_service.get_stroke_order(ch),
        }

    async def search_by_stroke_order(
        self,
        stroke_pattern: str,
        skip: int = 0,
        limit: int = 20,
        management_system_id: Optional[str] = None,
        page: Optional[int] = None,
        size: Optional[int] = None,
    ) -> HanziListResponse:
        """
        功能描述：
            检索by笔画order。

        参数：
            stroke_pattern (str): 字符串结果。
            skip (int): 分页偏移量。
            limit (int): 单次查询的最大返回数量。
            management_system_id (Optional[str]): 管理系统ID，用于限制数据作用域。
            page (Optional[int]): 当前页码。
            size (Optional[int]): 每页条数。

        返回值：
            HanziListResponse: 返回检索结果。
        """
        items = await self.repo.search_by_stroke_order(stroke_pattern, skip, limit, management_system_id)
        payload = build_paged_response(
            items=[self._to_response(item) for item in items],
            total=len(items),
            pagination={"page": page, "size": size, "skip": skip, "limit": limit},
        )
        return HanziListResponse(**payload)

    @staticmethod
    def _to_response(item) -> HanziResponse:
        """
        功能描述：
            将输入数据转换为响应。

        参数：
            item (Any): 当前处理的实体对象。

        返回值：
            HanziResponse: 返回HanziResponse类型的处理结果。
        """
        return HanziResponse(
            id=item.id,
            character=item.character,
            char=item.character,
            image_path=item.image_path,
            stroke_count=item.stroke_count,
            structure=item.structure,
            stroke_order=item.stroke_order,
            pinyin=item.pinyin,
            level=item.level,
            comment=item.comment,
            variant=item.variant,
            standard_image=item.standard_image,
            management_system_id=item.management_system_id,
            created_at=str(item.created_at) if item.created_at else None,
            updated_at=str(item.updated_at) if item.updated_at else None,
        )
