from typing import Optional

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.management_system import ManagementSystem, UserManagementSystem
from app.models.user import User


class ManagementSystemRepository:
    def __init__(self, db: AsyncSession):
        """
        功能描述：
            初始化ManagementSystemRepository并准备运行所需的依赖对象。

        参数：
            db (AsyncSession): 数据库会话，用于执行持久化操作。

        返回值：
            None: 无返回值。
        """
        self.db = db

    async def get(self, id: str) -> Optional[ManagementSystem]:
        """
        功能描述：
            获取ManagementSystemRepository。

        参数：
            id (str): 目标记录ID。

        返回值：
            Optional[ManagementSystem]: 返回处理结果对象；无可用结果时返回 None。
        """
        result = await self.db.execute(
            select(ManagementSystem)
            .where(ManagementSystem.id == id)
            .options(
                selectinload(ManagementSystem.owner_user).selectinload(User.teacher_profile),
                selectinload(ManagementSystem.owner_user).selectinload(User.student_profile),
            )
        )
        return result.scalars().first()

    async def get_accessible(self, id: str, user_id: str) -> Optional[ManagementSystem]:
        """
        功能描述：
            按条件获取accessible。

        参数：
            id (str): 目标记录ID。
            user_id (str): 用户ID。

        返回值：
            Optional[ManagementSystem]: 返回查询到的结果对象；未命中时返回 None。
        """
        result = await self.db.execute(
            select(ManagementSystem)
            # 通过关联表约束“可访问”语义，避免误把系统拥有关系与可见关系混为一类条件。
            .join(UserManagementSystem, UserManagementSystem.management_system_id == ManagementSystem.id)
            .where(ManagementSystem.id == id, UserManagementSystem.user_id == user_id)
            .options(
                selectinload(ManagementSystem.owner_user).selectinload(User.teacher_profile),
                selectinload(ManagementSystem.owner_user).selectinload(User.student_profile),
            )
        )
        return result.scalars().first()

    async def get_owned(self, id: str, user_id: str) -> Optional[ManagementSystem]:
        """
        功能描述：
            按条件获取owned。

        参数：
            id (str): 目标记录ID。
            user_id (str): 用户ID。

        返回值：
            Optional[ManagementSystem]: 返回查询到的结果对象；未命中时返回 None。
        """
        result = await self.db.execute(
            select(ManagementSystem)
            .where(ManagementSystem.id == id, ManagementSystem.owner_user_id == user_id)
            .options(
                selectinload(ManagementSystem.owner_user).selectinload(User.teacher_profile),
                selectinload(ManagementSystem.owner_user).selectinload(User.student_profile),
            )
        )
        return result.scalars().first()

    async def list_accessible(self, user_id: str, skip: int = 0, limit: int = 20) -> list[ManagementSystem]:
        """
        功能描述：
            按条件查询accessible列表。

        参数：
            user_id (str): 用户ID。
            skip (int): 分页偏移量。
            limit (int): 单次查询的最大返回数量。

        返回值：
            list[ManagementSystem]: 返回列表形式的结果数据。
        """
        result = await self.db.execute(
            select(ManagementSystem)
            .join(UserManagementSystem, UserManagementSystem.management_system_id == ManagementSystem.id)
            .where(UserManagementSystem.user_id == user_id)
            .options(
                selectinload(ManagementSystem.owner_user).selectinload(User.teacher_profile),
                selectinload(ManagementSystem.owner_user).selectinload(User.student_profile),
            )
            # 默认系统优先保证前端入口稳定，其次按更新时间倒序让“最近使用”更靠前。
            .order_by(ManagementSystem.is_default.desc(), ManagementSystem.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

    async def count_accessible(self, user_id: str) -> int:
        """
        功能描述：
            统计accessible数量。

        参数：
            user_id (str): 用户ID。

        返回值：
            int: 返回统计结果。
        """
        result = await self.db.execute(
            select(func.count()).select_from(UserManagementSystem).where(UserManagementSystem.user_id == user_id)
        )
        return int(result.scalar() or 0)

    async def get_link(self, user_id: str, management_system_id: str) -> Optional[UserManagementSystem]:
        """
        功能描述：
            按条件获取link。

        参数：
            user_id (str): 用户ID。
            management_system_id (str): 管理系统ID，用于限制数据作用域。

        返回值：
            Optional[UserManagementSystem]: 返回查询到的结果对象；未命中时返回 None。
        """
        result = await self.db.execute(
            select(UserManagementSystem).where(
                UserManagementSystem.user_id == user_id,
                UserManagementSystem.management_system_id == management_system_id,
            )
        )
        return result.scalars().first()

    async def get_default_for_user(self, user_id: str, preset_key: str) -> Optional[ManagementSystem]:
        """
        功能描述：
            按条件获取默认for用户。

        参数：
            user_id (str): 用户ID。
            preset_key (str): 字符串结果。

        返回值：
            Optional[ManagementSystem]: 返回查询到的结果对象；未命中时返回 None。
        """
        result = await self.db.execute(
            select(ManagementSystem)
            .join(UserManagementSystem, UserManagementSystem.management_system_id == ManagementSystem.id)
            .where(
                UserManagementSystem.user_id == user_id,
                ManagementSystem.is_default.is_(True),
                ManagementSystem.preset_key == preset_key,
            )
            .options(
                selectinload(ManagementSystem.owner_user).selectinload(User.teacher_profile),
                selectinload(ManagementSystem.owner_user).selectinload(User.student_profile),
            )
        )
        return result.scalars().first()

    async def get_owner_preset_system(self, owner_user_id: str, preset_key: str) -> Optional[ManagementSystem]:
        """
        功能描述：
            按条件获取归属preset系统。

        参数：
            owner_user_id (str): 归属用户ID。
            preset_key (str): 字符串结果。

        返回值：
            Optional[ManagementSystem]: 返回查询到的结果对象；未命中时返回 None。
        """
        result = await self.db.execute(
            select(ManagementSystem)
            .where(
                ManagementSystem.owner_user_id == owner_user_id,
                ManagementSystem.preset_key == preset_key,
            )
            .options(
                selectinload(ManagementSystem.owner_user).selectinload(User.teacher_profile),
                selectinload(ManagementSystem.owner_user).selectinload(User.student_profile),
            )
        )
        return result.scalars().first()

    async def list_user_ids_missing_default(self, preset_key: str) -> list[str]:
        # 使用相关子查询直接在数据库侧找“缺默认系统”用户，避免全量拉取后在应用层二次比对。
        """
        功能描述：
            按条件查询用户标识列表missing默认列表。

        参数：
            preset_key (str): 字符串结果。

        返回值：
            list[str]: 返回列表形式的结果数据。
        """
        default_exists = exists(
            select(UserManagementSystem.id)
            .join(ManagementSystem, UserManagementSystem.management_system_id == ManagementSystem.id)
            .where(
                UserManagementSystem.user_id == User.id,
                ManagementSystem.is_default.is_(True),
                ManagementSystem.preset_key == preset_key,
            )
        )
        result = await self.db.execute(select(User.id).where(~default_exists))
        return list(result.scalars().all())

    async def add_system(self, system: ManagementSystem) -> ManagementSystem:
        """
        功能描述：
            新增系统。

        参数：
            system (ManagementSystem): ManagementSystem 类型的数据。

        返回值：
            ManagementSystem: 返回ManagementSystem类型的处理结果。
        """
        self.db.add(system)
        await self.db.flush()
        return system

    async def add_link(self, link: UserManagementSystem) -> UserManagementSystem:
        """
        功能描述：
            新增link。

        参数：
            link (UserManagementSystem): UserManagementSystem 类型的数据。

        返回值：
            UserManagementSystem: 返回UserManagementSystem类型的处理结果。
        """
        self.db.add(link)
        await self.db.flush()
        return link

    async def save(self) -> None:
        """
        功能描述：
            保存ManagementSystemRepository。

        参数：
            无。

        返回值：
            None: 无返回值。
        """
        await self.db.commit()

    async def rollback(self) -> None:
        """
        功能描述：
            处理ManagementSystemRepository。

        参数：
            无。

        返回值：
            None: 无返回值。
        """
        await self.db.rollback()
