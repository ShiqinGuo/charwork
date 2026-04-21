"""
附件业务逻辑层。

处理附件上传、查询、删除等业务操作，集成文件存储和数据持久化。
"""

import os
from typing import List
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import ATTACHMENT_OWNER_TYPES
from app.repositories.attachment_repo import AttachmentRepository
from app.schemas.attachment import AttachmentCreate, AttachmentResponse
from app.services.ocr_service import OCRService


class AttachmentService:
    def __init__(self, db: AsyncSession):
        """
        功能描述：
            初始化AttachmentService并准备运行所需的依赖对象。

        参数：
            db (AsyncSession): 数据库会话，用于执行持久化操作。

        返回值：
            None: 无返回值。
        """
        self.db = db
        self.repo = AttachmentRepository(db)
        self.ocr_service = OCRService()

    def validate_owner_type(self, owner_type: str) -> bool:
        """
        功能描述：
            验证所有者类型是否支持。

        参数：
            owner_type (str): 所有者类型。

        返回值：
            bool: 类型有效返回 True，否则返回 False。
        """
        return owner_type in ATTACHMENT_OWNER_TYPES

    async def upload_attachment(
        self,
        file: UploadFile,
        owner_type: str,
        owner_id: str,
        management_system_id: str,
    ) -> AttachmentResponse:
        """
        功能描述：
            上传文件到云存储并创建附件记录。

        参数：
            file (UploadFile): 上传的文件对象。
            owner_type (str): 所有者类型。
            owner_id (str): 所有者ID。
            management_system_id (str): 管理系统ID。

        返回值：
            AttachmentResponse: 返回创建后的附件响应对象。
        """
        if not self.validate_owner_type(owner_type):
            raise ValueError(f"不支持的所有者类型: {owner_type}")

        # 保存临时文件
        from app.core.config import settings
        temp_dir = settings.TEMP_DIR
        os.makedirs(temp_dir, exist_ok=True)

        temp_file_path = os.path.join(temp_dir, file.filename)
        try:
            content = await file.read()
            with open(temp_file_path, "wb") as f:
                f.write(content)

            # 调用 OCRService 上传到云存储
            upload_result = await self.ocr_service.upload_image(temp_file_path)
            file_url = upload_result.get("image_url", "")

            # 获取文件大小
            file_size = len(content)

            # 创建附件记录
            attachment_in = AttachmentCreate(
                owner_type=owner_type,
                owner_id=owner_id,
                file_url=file_url,
                filename=file.filename,
                file_size=file_size,
                mime_type=file.content_type or "application/octet-stream",
            )
            attachment = await self.repo.create(attachment_in, management_system_id)

            return AttachmentResponse.model_validate(attachment)
        finally:
            # 删除临时文件
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)

    async def get_attachments_by_owner(
        self,
        owner_type: str,
        owner_id: str,
        management_system_id: str,
    ) -> List[AttachmentResponse]:
        """
        功能描述：
            按所有者查询附件。

        参数：
            owner_type (str): 所有者类型。
            owner_id (str): 所有者ID。
            management_system_id (str): 管理系统ID。

        返回值：
            List[AttachmentResponse]: 返回附件响应列表。
        """
        attachments = await self.repo.get_by_owner(
            owner_type=owner_type,
            owner_id=owner_id,
            management_system_id=management_system_id,
        )
        return [AttachmentResponse.model_validate(a) for a in attachments]

    async def delete_attachment(
        self,
        attachment_id: str,
        management_system_id: str,
    ) -> None:
        """
        功能描述：
            软删除附件。

        参数：
            attachment_id (str): 附件ID。
            management_system_id (str): 管理系统ID。

        返回值：
            None: 无返回值。
        """
        attachment = await self.repo.get(attachment_id, management_system_id)
        if not attachment:
            raise ValueError(f"附件不存在: {attachment_id}")

        await self.repo.soft_delete(attachment)
