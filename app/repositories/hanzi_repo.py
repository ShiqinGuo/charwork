from typing import List, Optional
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.hanzi import Hanzi
from app.schemas.hanzi import HanziCreate, HanziUpdate


class HanziRepository:
    def __init__(self, db: AsyncSession):
        """
        功能描述：
            初始化HanziRepository并准备运行所需的依赖对象。

        参数：
            db (AsyncSession): 数据库会话，用于执行持久化操作。

        返回值：
            None: 无返回值。
        """
        self.db = db

    async def get(self, id: str, management_system_id: Optional[str] = None) -> Optional[Hanzi]:
        """
        功能描述：
            获取HanziRepository。

        参数：
            id (str): 目标记录ID。
            management_system_id (Optional[str]): 管理系统ID，用于限制数据作用域。

        返回值：
            Optional[Hanzi]: 返回处理结果对象；无可用结果时返回 None。
        """
        query = select(Hanzi).filter(Hanzi.id == id)
        if management_system_id:
            query = query.where(Hanzi.management_system_id == management_system_id)
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_by_character(self, character: str, management_system_id: Optional[str] = None) -> Optional[Hanzi]:
        """
        功能描述：
            按条件获取bycharacter。

        参数：
            character (str): 字符串结果。
            management_system_id (Optional[str]): 管理系统ID，用于限制数据作用域。

        返回值：
            Optional[Hanzi]: 返回查询到的结果对象；未命中时返回 None。
        """
        query = select(Hanzi).filter(Hanzi.character == character)
        if management_system_id:
            query = query.where(Hanzi.management_system_id == management_system_id)
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_all(self, skip: int = 0, limit: int = 100,
                      structure: Optional[str] = None,
                      level: Optional[str] = None,
                      variant: Optional[str] = None,
                      search: Optional[str] = None,
                      management_system_id: Optional[str] = None) -> List[Hanzi]:
        """
        功能描述：
            按条件获取all。

        参数：
            skip (int): 分页偏移量。
            limit (int): 单次查询的最大返回数量。
            structure (Optional[str]): 字符串结果。
            level (Optional[str]): 字符串结果。
            variant (Optional[str]): 字符串结果。
            search (Optional[str]): 字符串结果。
            management_system_id (Optional[str]): 管理系统ID，用于限制数据作用域。

        返回值：
            List[Hanzi]: 返回查询到的结果对象。
        """
        query = select(Hanzi)
        if management_system_id:
            query = query.where(Hanzi.management_system_id == management_system_id)

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

    async def search_by_stroke_order(
        self,
        stroke_pattern: str,
        skip: int = 0,
        limit: int = 100,
        management_system_id: Optional[str] = None,
    ) -> List[Hanzi]:
        """
        功能描述：
            检索by笔画order。

        参数：
            stroke_pattern (str): 字符串结果。
            skip (int): 分页偏移量。
            limit (int): 单次查询的最大返回数量。
            management_system_id (Optional[str]): 管理系统ID，用于限制数据作用域。

        返回值：
            List[Hanzi]: 返回检索结果。
        """
        if not stroke_pattern:
            return []
        tokens = [p.strip() for p in stroke_pattern.split(" ") if p.strip()]
        if not tokens:
            return []
        query = select(Hanzi).where(Hanzi.stroke_order.is_not(None))
        if management_system_id:
            query = query.where(Hanzi.management_system_id == management_system_id)
        for t in tokens:
            query = query.where(Hanzi.stroke_order.contains(t))
        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def count(self, structure: Optional[str] = None,
                    level: Optional[str] = None,
                    variant: Optional[str] = None,
                    search: Optional[str] = None,
                    management_system_id: Optional[str] = None) -> int:
        """
        功能描述：
            统计HanziRepository。

        参数：
            structure (Optional[str]): 字符串结果。
            level (Optional[str]): 字符串结果。
            variant (Optional[str]): 字符串结果。
            search (Optional[str]): 字符串结果。
            management_system_id (Optional[str]): 管理系统ID，用于限制数据作用域。

        返回值：
            int: 返回int类型的处理结果。
        """
        query = select(func.count()).select_from(Hanzi)
        if management_system_id:
            query = query.where(Hanzi.management_system_id == management_system_id)

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

    async def create(self, hanzi_in: HanziCreate, management_system_id: str) -> Hanzi:
        """
        功能描述：
            创建HanziRepository。

        参数：
            hanzi_in (HanziCreate): 汉字输入对象。
            management_system_id (str): 管理系统ID，用于限制数据作用域。

        返回值：
            Hanzi: 返回Hanzi类型的处理结果。
        """
        payload = hanzi_in.model_dump()
        payload["management_system_id"] = management_system_id
        payload.pop("char", None)
        hanzi = Hanzi(**payload)
        self.db.add(hanzi)
        await self.db.commit()
        await self.db.refresh(hanzi)
        return hanzi

    async def update(self, hanzi: Hanzi, hanzi_in: HanziUpdate) -> Hanzi:
        """
        功能描述：
            更新HanziRepository。

        参数：
            hanzi (Hanzi): Hanzi 类型的数据。
            hanzi_in (HanziUpdate): 汉字输入对象。

        返回值：
            Hanzi: 返回Hanzi类型的处理结果。
        """
        update_data = hanzi_in.model_dump(exclude_unset=True)
        update_data.pop("char", None)
        update_data.pop("management_system_id", None)
        for key, value in update_data.items():
            setattr(hanzi, key, value)

        await self.db.commit()
        await self.db.refresh(hanzi)
        return hanzi

    async def delete(self, hanzi: Hanzi) -> None:
        """
        功能描述：
            删除HanziRepository。

        参数：
            hanzi (Hanzi): Hanzi 类型的数据。

        返回值：
            None: 无返回值。
        """
        await self.db.delete(hanzi)
        await self.db.commit()
