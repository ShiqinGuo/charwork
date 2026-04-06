"""
为什么这样做：消息发送先校验接收方是否在当前管理系统作用域，避免跨系统误投递。
特殊逻辑：已读操作增加接收者与管理系统双边界校验，确保越权请求不会改写消息状态。
"""

from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.management_system_repo import ManagementSystemRepository
from app.repositories.message_repo import MessageRepository
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
        self.management_system_repo = ManagementSystemRepository(db)

    async def send_message(
        self,
        body: MessageCreate,
        sender_id: str,
        management_system_id: str,
    ) -> MessageResponse:
        """
        功能描述：
            处理消息。

        参数：
            body (MessageCreate): 接口请求体对象。
            sender_id (str): 发送者ID。
            management_system_id (str): 管理系统ID，用于限制数据作用域。

        返回值：
            MessageResponse: 返回MessageResponse类型的处理结果。
        """
        receiver_scope = await self.management_system_repo.get_accessible(management_system_id, body.receiver_id)
        if not receiver_scope:
            raise PermissionError("接收方不在当前管理系统作用域内")
        msg = await self.repo.create(body, sender_id=sender_id, management_system_id=management_system_id)
        return MessageResponse.model_validate(msg)

    async def list_inbox(
        self,
        user_id: str,
        management_system_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> dict:
        """
        功能描述：
            按条件查询inbox列表。

        参数：
            user_id (str): 用户ID。
            management_system_id (Optional[str]): 管理系统ID，用于限制数据作用域。
            skip (int): 分页偏移量。
            limit (int): 单次查询的最大返回数量。

        返回值：
            dict: 返回字典形式的结果数据。
        """
        items = await self.repo.list_inbox(user_id, management_system_id, skip, limit)
        return {"items": [MessageResponse.model_validate(i) for i in items]}

    async def list_outbox(
        self,
        user_id: str,
        management_system_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> dict:
        """
        功能描述：
            按条件查询outbox列表。

        参数：
            user_id (str): 用户ID。
            management_system_id (Optional[str]): 管理系统ID，用于限制数据作用域。
            skip (int): 分页偏移量。
            limit (int): 单次查询的最大返回数量。

        返回值：
            dict: 返回字典形式的结果数据。
        """
        items = await self.repo.list_outbox(user_id, management_system_id, skip, limit)
        return {"items": [MessageResponse.model_validate(i) for i in items]}

    async def mark_read(
        self,
        id: str,
        current_user_id: str,
        management_system_id: Optional[str] = None,
    ) -> Optional[MessageResponse]:
        """
        功能描述：
            处理read。

        参数：
            id (str): 目标记录ID。
            current_user_id (str): 当前用户ID。
            management_system_id (Optional[str]): 管理系统ID，用于限制数据作用域。

        返回值：
            Optional[MessageResponse]: 返回处理结果对象；无可用结果时返回 None。
        """
        msg = await self.repo.get(id)
        if not msg:
            return None
        if msg.receiver_id != current_user_id:
            return None
        if management_system_id and msg.management_system_id and msg.management_system_id != management_system_id:
            return None
        msg = await self.repo.update(msg, {"is_read": True})
        return MessageResponse.model_validate(msg)
