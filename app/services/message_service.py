"""
为什么这样做：消息属于用户私有互动数据，应按收发双方归属校验，而不是依赖管理系统作用域。
特殊逻辑：已读操作只允许接收者本人修改，避免越权请求改写消息状态。
"""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.message_repo import MessageRepository
from app.repositories.user_repo import UserRepository
from app.schemas.message import MessageCreate, MessageResponse


class MessageService:
    def __init__(self, db: AsyncSession):
        """
        功能描述：
            初始化MessageService并准备运行所需的依赖对象。

        参数：
            db (AsyncSession): 数据库会话，用于执行持久化操作。

        返回值：
            None: 无返回值。
        """
        self.repo = MessageRepository(db)
        self.user_repo = UserRepository(db)

    async def send_message(
        self,
        body: MessageCreate,
        sender_id: str,
    ) -> MessageResponse:
        """
        功能描述：
            处理消息。

        参数：
            body (MessageCreate): 接口请求体对象。
            sender_id (str): 发送者ID。
        返回值：
            MessageResponse: 返回MessageResponse类型的处理结果。
        """
        receiver = await self.user_repo.get(body.receiver_id)
        if not receiver:
            raise PermissionError("接收方不存在")
        msg = await self.repo.create(body, sender_id=sender_id)
        return MessageResponse.model_validate(msg)

    async def list_inbox(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 20,
    ) -> dict:
        """
        功能描述：
            按条件查询inbox列表。

        参数：
            user_id (str): 用户ID。
            skip (int): 分页偏移量。
            limit (int): 单次查询的最大返回数量。

        返回值：
            dict: 返回字典形式的结果数据。
        """
        items = await self.repo.list_inbox(user_id, skip, limit)
        return {"items": [MessageResponse.model_validate(i) for i in items]}

    async def list_outbox(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 20,
    ) -> dict:
        """
        功能描述：
            按条件查询outbox列表。

        参数：
            user_id (str): 用户ID。
            skip (int): 分页偏移量。
            limit (int): 单次查询的最大返回数量。

        返回值：
            dict: 返回字典形式的结果数据。
        """
        items = await self.repo.list_outbox(user_id, skip, limit)
        return {"items": [MessageResponse.model_validate(i) for i in items]}

    async def mark_read(
        self,
        id: str,
        current_user_id: str,
    ) -> Optional[MessageResponse]:
        """
        功能描述：
            处理read。

        参数：
            id (str): 目标记录ID。
            current_user_id (str): 当前用户ID。
        返回值：
            Optional[MessageResponse]: 返回处理结果对象；无可用结果时返回 None。
        """
        msg = await self.repo.get(id)
        if not msg:
            return None
        if msg.receiver_id != current_user_id:
            return None
        msg = await self.repo.update(msg, {"is_read": True})
        return MessageResponse.model_validate(msg)
