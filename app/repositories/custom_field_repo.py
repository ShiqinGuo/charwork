from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.custom_field import ManagementSystemCustomField, ManagementSystemCustomFieldValue


class CustomFieldRepository:
    def __init__(self, db: AsyncSession):
        """
        功能描述：
            初始化CustomFieldRepository并准备运行所需的依赖对象。

        参数：
            db (AsyncSession): 数据库会话，用于执行持久化操作。

        返回值：
            None: 无返回值。
        """
        self.db = db

    async def get_field(self, id: str,
                        management_system_id: Optional[str] = None) -> Optional[ManagementSystemCustomField]:
        """
        功能描述：
            按条件获取字段。

        参数：
            id (str): 目标记录ID。
            management_system_id (Optional[str]): 管理系统ID，用于限制数据作用域。

        返回值：
            Optional[ManagementSystemCustomField]: 返回查询到的结果对象；未命中时返回 None。
        """
        query = select(ManagementSystemCustomField).where(ManagementSystemCustomField.id == id)
        if management_system_id:
            # 读取单字段时可选追加系统边界，供上层在“全局 ID”与“系统内 ID”两种场景复用同一查询入口。
            query = query.where(ManagementSystemCustomField.management_system_id == management_system_id)
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_field_by_key(
        self,
        management_system_id: str,
        target_type: str,
        field_key: str,
    ) -> Optional[ManagementSystemCustomField]:
        """
        功能描述：
            按条件获取字段bykey。

        参数：
            management_system_id (str): 管理系统ID，用于限制数据作用域。
            target_type (str): 字符串结果。
            field_key (str): 字符串结果。

        返回值：
            Optional[ManagementSystemCustomField]: 返回查询到的结果对象；未命中时返回 None。
        """
        result = await self.db.execute(
            select(ManagementSystemCustomField).where(
                ManagementSystemCustomField.management_system_id == management_system_id,
                ManagementSystemCustomField.target_type == target_type,
                ManagementSystemCustomField.field_key == field_key,
            )
        )
        return result.scalars().first()

    async def list_fields(
        self,
        management_system_id: str,
        target_type: Optional[str] = None,
        searchable_only: bool = False,
    ) -> list[ManagementSystemCustomField]:
        """
        功能描述：
            按条件查询字段列表。

        参数：
            management_system_id (str): 管理系统ID，用于限制数据作用域。
            target_type (Optional[str]): 字符串结果。
            searchable_only (bool): 布尔值结果。

        返回值：
            list[ManagementSystemCustomField]: 返回列表形式的结果数据。
        """
        query = select(ManagementSystemCustomField).where(
            ManagementSystemCustomField.management_system_id == management_system_id
        )
        if target_type:
            query = query.where(ManagementSystemCustomField.target_type == target_type)
        if searchable_only:
            query = query.where(ManagementSystemCustomField.is_searchable.is_(True))
        result = await self.db.execute(
            # 先按目标类型再按显式排序位，最后按创建时间兜底，保证配置页展示稳定可预测。
            query.order_by(
                ManagementSystemCustomField.target_type.asc(),
                ManagementSystemCustomField.sort_order.asc(),
                ManagementSystemCustomField.created_at.asc(),
            )
        )
        return result.scalars().all()

    async def count_fields(
        self,
        management_system_id: str,
        target_type: Optional[str] = None,
        searchable_only: bool = False,
    ) -> int:
        """
        功能描述：
            统计字段数量。

        参数：
            management_system_id (str): 管理系统ID，用于限制数据作用域。
            target_type (Optional[str]): 字符串结果。
            searchable_only (bool): 布尔值结果。

        返回值：
            int: 返回统计结果。
        """
        query = select(func.count()).select_from(ManagementSystemCustomField).where(
            ManagementSystemCustomField.management_system_id == management_system_id
        )
        if target_type:
            query = query.where(ManagementSystemCustomField.target_type == target_type)
        if searchable_only:
            query = query.where(ManagementSystemCustomField.is_searchable.is_(True))
        result = await self.db.execute(query)
        return int(result.scalar() or 0)

    async def add_field(self, field: ManagementSystemCustomField) -> ManagementSystemCustomField:
        """
        功能描述：
            新增字段。

        参数：
            field (ManagementSystemCustomField): ManagementSystemCustomField 类型的数据。

        返回值：
            ManagementSystemCustomField: 返回ManagementSystemCustomField类型的处理结果。
        """
        self.db.add(field)
        await self.db.commit()
        await self.db.refresh(field)
        return field

    async def get_value(self, field_id: str, target_id: str) -> Optional[ManagementSystemCustomFieldValue]:
        """
        功能描述：
            按条件获取值。

        参数：
            field_id (str): 字段ID。
            target_id (str): targetID。

        返回值：
            Optional[ManagementSystemCustomFieldValue]: 返回查询到的结果对象；未命中时返回 None。
        """
        result = await self.db.execute(
            select(ManagementSystemCustomFieldValue).where(
                ManagementSystemCustomFieldValue.field_id == field_id,
                ManagementSystemCustomFieldValue.target_id == target_id,
            )
        )
        return result.scalars().first()

    async def list_values(
        self,
        management_system_id: str,
        target_type: str,
        target_id: str,
    ) -> list[ManagementSystemCustomFieldValue]:
        """
        功能描述：
            按条件查询值列表。

        参数：
            management_system_id (str): 管理系统ID，用于限制数据作用域。
            target_type (str): 字符串结果。
            target_id (str): targetID。

        返回值：
            list[ManagementSystemCustomFieldValue]: 返回列表形式的结果数据。
        """
        result = await self.db.execute(
            select(ManagementSystemCustomFieldValue)
            .where(
                ManagementSystemCustomFieldValue.management_system_id == management_system_id,
                ManagementSystemCustomFieldValue.target_type == target_type,
                ManagementSystemCustomFieldValue.target_id == target_id,
            )
            .options(selectinload(ManagementSystemCustomFieldValue.field))
            .order_by(ManagementSystemCustomFieldValue.created_at.asc())
        )
        return result.scalars().all()

    async def list_values_for_targets(
        self,
        management_system_id: str,
        target_type: str,
        target_ids: list[str],
    ) -> list[ManagementSystemCustomFieldValue]:
        """
        功能描述：
            按条件查询值fortargets列表。

        参数：
            management_system_id (str): 管理系统ID，用于限制数据作用域。
            target_type (str): 字符串结果。
            target_ids (list[str]): targetID列表。

        返回值：
            list[ManagementSystemCustomFieldValue]: 返回列表形式的结果数据。
        """
        if not target_ids:
            # 显式短路空集合，避免生成 in_([]) 导致数据库执行无意义条件表达式。
            return []
        result = await self.db.execute(
            select(ManagementSystemCustomFieldValue)
            .where(
                ManagementSystemCustomFieldValue.management_system_id == management_system_id,
                ManagementSystemCustomFieldValue.target_type == target_type,
                ManagementSystemCustomFieldValue.target_id.in_(target_ids),
            )
            # 批量值查询按 target_id 分组输出，便于上层一次遍历构建“目标 -> 字段值列表”映射。
            .options(selectinload(ManagementSystemCustomFieldValue.field))
            .order_by(
                ManagementSystemCustomFieldValue.target_id.asc(),
                ManagementSystemCustomFieldValue.created_at.asc(),
            )
        )
        return result.scalars().all()

    async def count_values(self, management_system_id: str, target_type: str, target_id: str) -> int:
        """
        功能描述：
            统计值数量。

        参数：
            management_system_id (str): 管理系统ID，用于限制数据作用域。
            target_type (str): 字符串结果。
            target_id (str): targetID。

        返回值：
            int: 返回统计结果。
        """
        result = await self.db.execute(
            select(func.count()).select_from(ManagementSystemCustomFieldValue).where(
                ManagementSystemCustomFieldValue.management_system_id == management_system_id,
                ManagementSystemCustomFieldValue.target_type == target_type,
                ManagementSystemCustomFieldValue.target_id == target_id,
            )
        )
        return int(result.scalar() or 0)

    async def list_values_by_field(
        self,
        management_system_id: str,
        target_type: str,
        field_id: str,
    ) -> list[ManagementSystemCustomFieldValue]:
        """
        功能描述：
            按条件查询值by字段列表。

        参数：
            management_system_id (str): 管理系统ID，用于限制数据作用域。
            target_type (str): 字符串结果。
            field_id (str): 字段ID。

        返回值：
            list[ManagementSystemCustomFieldValue]: 返回列表形式的结果数据。
        """
        result = await self.db.execute(
            select(ManagementSystemCustomFieldValue)
            .where(
                ManagementSystemCustomFieldValue.management_system_id == management_system_id,
                ManagementSystemCustomFieldValue.target_type == target_type,
                ManagementSystemCustomFieldValue.field_id == field_id,
            )
            .options(selectinload(ManagementSystemCustomFieldValue.field))
            .order_by(ManagementSystemCustomFieldValue.created_at.asc())
        )
        return result.scalars().all()

    async def add(self, item) -> None:
        """
        功能描述：
            新增CustomFieldRepository。

        参数：
            item (Any): 当前处理的实体对象。

        返回值：
            None: 无返回值。
        """
        self.db.add(item)
        await self.db.flush()

    async def save(self) -> None:
        """
        功能描述：
            保存CustomFieldRepository。

        参数：
            无。

        返回值：
            None: 无返回值。
        """
        await self.db.commit()
