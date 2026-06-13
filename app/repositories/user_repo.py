from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    def __init__(self, db: AsyncSession):
        """
        功能描述：
            初始化UserRepository并准备运行所需的依赖对象。

        参数：
            db (AsyncSession): 数据库会话，用于执行持久化操作。

        返回值：
            None: 无返回值。
        """
        self.db = db

    async def get(self, id: str) -> Optional[User]:
        """
        功能描述：
            获取UserRepository。

        参数：
            id (str): 目标记录ID。

        返回值：
            Optional[User]: 返回处理结果对象；无可用结果时返回 None。
        """
        result = await self.db.execute(select(User).where(User.id == id))
        return result.scalars().first()

    async def get_by_username(self, username: str) -> Optional[User]:
        """
        功能描述：
            按条件获取byusername。

        参数：
            username (str): 字符串结果。

        返回值：
            Optional[User]: 返回查询到的结果对象；未命中时返回 None。
        """
        result = await self.db.execute(select(User).where(User.username == username))
        return result.scalars().first()

    async def get_by_email(self, email: str) -> Optional[User]:
        """
        功能描述：
            按条件获取byemail。

        参数：
            email (str): 字符串结果。

        返回值：
            Optional[User]: 返回查询到的结果对象；未命中时返回 None。
        """
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalars().first()

    async def create(self, user: User) -> User:
        """
        功能描述：
            创建UserRepository。

        参数：
            user (User): User 类型的数据。

        返回值：
            User: 返回User类型的处理结果。
        """
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user
