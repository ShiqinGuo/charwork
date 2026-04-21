from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attachment import Attachment
from app.schemas.attachment import AttachmentCreate


class AttachmentRepository:
    def __init__(self, db: AsyncSession):
        """
        功能描述：
            初始化AttachmentRepository并准备运行所需的依赖对象。

        参数：
            db (AsyncSession): 数据库会话，用于执行持久化操作。

        返回值：
            None: 无返回值。
        """
        self.db = db

    async def create(self, attachment_in: AttachmentCreate) -> Attachment:
        """
        功能描述：
            创建附件记录。

        参数：
            attachment_in (AttachmentCreate): 附件输入对象。
        返回值：
            Attachment: 返回创建后的附件对象。
        """
        attachment = Attachment(
            owner_type=attachment_in.owner_type,
            owner_id=attachment_in.owner_id,
            file_url=attachment_in.file_url,
            filename=attachment_in.filename,
            file_size=attachment_in.file_size,
            mime_type=attachment_in.mime_type,
        )
        self.db.add(attachment)
        await self.db.commit()
        await self.db.refresh(attachment)
        return attachment

    async def get(self, id: str) -> Optional[Attachment]:
        """
        功能描述：
            按ID获取附件（排除已删除）。

        参数：
            id (str): 附件ID。
        返回值：
            Optional[Attachment]: 返回附件对象；未找到或已删除时返回 None。
        """
        query = select(Attachment).where(
            Attachment.id == id,
            Attachment.deleted_at.is_(None),
        )
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_by_owner(
        self,
        owner_type: str,
        owner_id: str,
    ) -> List[Attachment]:
        """
        功能描述：
            按所有者查询附件（排除已删除）。

        参数：
            owner_type (str): 所有者类型。
            owner_id (str): 所有者ID。
        返回值：
            List[Attachment]: 返回附件列表。
        """
        query = select(Attachment).where(
            Attachment.owner_type == owner_type,
            Attachment.owner_id == owner_id,
            Attachment.deleted_at.is_(None),
        )
        result = await self.db.execute(query)
        return result.scalars().all()

    async def soft_delete(self, attachment: Attachment) -> None:
        """
        功能描述：
            软删除附件。

        参数：
            attachment (Attachment): 待删除的附件对象。

        返回值：
            None: 无返回值。
        """
        from datetime import datetime
        attachment.deleted_at = datetime.utcnow()
        await self.db.commit()

    async def commit(self) -> None:
        """
        功能描述：
            提交事务。

        参数：
            无。

        返回值：
            None: 无返回值。
        """
        await self.db.commit()

    async def refresh(self, attachment: Attachment) -> None:
        """
        功能描述：
            刷新附件对象。

        参数：
            attachment (Attachment): 待刷新的附件对象。

        返回值：
            None: 无返回值。
        """
        await self.db.refresh(attachment)
