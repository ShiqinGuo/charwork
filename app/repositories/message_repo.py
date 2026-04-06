from typing import List, Optional
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message
from app.schemas.message import MessageCreate


class MessageRepository:
    def __init__(self, db: AsyncSession):
        """
        功能描述：
            初始化MessageRepository并准备运行所需的依赖对象。

        参数：
            db (AsyncSession): 数据库会话，用于执行持久化操作。

        返回值：
            None: 无返回值。
        """
        self.db = db

    async def get(self, id: str) -> Optional[Message]:
        """
        功能描述：
            获取MessageRepository。

        参数：
            id (str): 目标记录ID。

        返回值：
            Optional[Message]: 返回处理结果对象；无可用结果时返回 None。
        """
        result = await self.db.execute(select(Message).where(Message.id == id))
        return result.scalars().first()

    async def list_inbox(
        self,
        user_id: str,
        management_system_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Message]:
        """
        功能描述：
            按条件查询inbox列表。

        参数：
            user_id (str): 用户ID。
            management_system_id (Optional[str]): 管理系统ID，用于限制数据作用域。
            skip (int): 分页偏移量。
            limit (int): 单次查询的最大返回数量。

        返回值：
            List[Message]: 返回列表或分页查询结果。
        """
        query = select(Message).where(Message.receiver_id == user_id)
        if management_system_id:
            query = query.where(
                or_(
                    Message.management_system_id == management_system_id,
                    Message.management_system_id.is_(None),
                )
            )
        result = await self.db.execute(
            query.order_by(Message.created_at.desc()).offset(skip).limit(limit)
        )
        return result.scalars().all()

    async def list_outbox(
        self,
        user_id: str,
        management_system_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Message]:
        """
        功能描述：
            按条件查询outbox列表。

        参数：
            user_id (str): 用户ID。
            management_system_id (Optional[str]): 管理系统ID，用于限制数据作用域。
            skip (int): 分页偏移量。
            limit (int): 单次查询的最大返回数量。

        返回值：
            List[Message]: 返回列表或分页查询结果。
        """
        query = select(Message).where(Message.sender_id == user_id)
        if management_system_id:
            query = query.where(
                or_(
                    Message.management_system_id == management_system_id,
                    Message.management_system_id.is_(None),
                )
            )
        result = await self.db.execute(
            query.order_by(Message.created_at.desc()).offset(skip).limit(limit)
        )
        return result.scalars().all()

    async def create(
        self,
        msg_in: MessageCreate,
        sender_id: str,
        management_system_id: Optional[str] = None,
    ) -> Message:
        """
        功能描述：
            创建MessageRepository。

        参数：
            msg_in (MessageCreate): msg输入对象。
            sender_id (str): 发送者ID。
            management_system_id (Optional[str]): 管理系统ID，用于限制数据作用域。

        返回值：
            Message: 返回Message类型的处理结果。
        """
        payload = msg_in.model_dump()
        payload["sender_id"] = sender_id
        payload["management_system_id"] = management_system_id
        msg = Message(**payload)
        self.db.add(msg)
        await self.db.commit()
        await self.db.refresh(msg)
        return msg

    async def update(self, msg: Message, update_data: dict) -> Message:
        """
        功能描述：
            更新MessageRepository。

        参数：
            msg (Message): Message 类型的数据。
            update_data (dict): 字典形式的结果数据。

        返回值：
            Message: 返回Message类型的处理结果。
        """
        for k, v in update_data.items():
            setattr(msg, k, v)
        await self.db.commit()
        await self.db.refresh(msg)
        return msg
