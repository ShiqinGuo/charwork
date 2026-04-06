"""
为什么这样做：作业附件先以临时资源入库，再在作业保存时统一做“绑定/解绑”同步，避免前端分步上传造成脏引用。
特殊逻辑：附件目录按 management_system_id 分桶，文件键统一相对 MEDIA_ROOT 存储，保证跨环境路径稳定。
"""

import os
from collections.abc import Iterable
from mimetypes import guess_type

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.assignment_attachment_upload import AssignmentAttachmentUpload
from app.repositories.assignment_attachment_upload_repo import AssignmentAttachmentUploadRepository
from app.schemas.assignment import AssignmentAttachmentUploadResponse
from app.utils.file_utils import save_upload_file


class AssignmentAttachmentUploadService:
    def __init__(self, db: AsyncSession):
        """
        功能描述：
            初始化AssignmentAttachmentUploadService并准备运行所需的依赖对象。

        参数：
            db (AsyncSession): 数据库会话，用于执行持久化操作。

        返回值：
            None: 无返回值。
        """
        self.repo = AssignmentAttachmentUploadRepository(db)

    async def upload_attachment(
        self,
        upload_file: UploadFile,
        management_system_id: str,
        uploaded_by_user_id: str,
    ) -> AssignmentAttachmentUploadResponse:
        """
        功能描述：
            上传附件。

        参数：
            upload_file (UploadFile): 文件对象或文件标识。
            management_system_id (str): 管理系统ID，用于限制数据作用域。
            uploaded_by_user_id (str): 上传操作对应的用户ID。

        返回值：
            AssignmentAttachmentUploadResponse: 返回AssignmentAttachmentUploadResponse类型的处理结果。
        """
        if not upload_file.filename:
            raise ValueError("缺少附件文件名")
        target_dir = os.path.join(settings.MEDIA_ROOT, "uploads", "assignments", management_system_id)
        file_path = await save_upload_file(upload_file, target_dir)
        file_key = os.path.relpath(file_path, settings.MEDIA_ROOT).replace("\\", "/")
        media_type = upload_file.content_type or guess_type(upload_file.filename)[0]
        item = await self.repo.create(
            AssignmentAttachmentUpload(
                management_system_id=management_system_id,
                uploaded_by_user_id=uploaded_by_user_id,
                name=upload_file.filename,
                file_key=file_key,
                url=f"/media/{file_key}",
                media_type=media_type,
                size=os.path.getsize(file_path),
                is_temporary=True,
            )
        )
        return AssignmentAttachmentUploadResponse.model_validate(item)

    async def sync_assignment_uploads(
        self,
        assignment_id: str,
        management_system_id: str,
        file_keys: Iterable[str],
    ) -> None:
        """
        功能描述：
            同步作业uploads。

        参数：
            assignment_id (str): 作业ID。
            management_system_id (str): 管理系统ID，用于限制数据作用域。
            file_keys (Iterable[str]): 文件对象或文件标识。

        返回值：
            None: 无返回值。
        """
        normalized_file_keys = sorted({file_key for file_key in file_keys if file_key})
        existing_items = await self.repo.list_by_assignment(assignment_id, management_system_id)
        existing_by_key = {item.file_key: item for item in existing_items}
        uploaded_items = await self._require_uploaded_items(management_system_id, normalized_file_keys)
        changed = False
        for file_key, item in existing_by_key.items():
            if file_key not in normalized_file_keys:
                item.assignment_id = None
                item.is_temporary = True
                changed = True
        for item in uploaded_items:
            if item.assignment_id != assignment_id or item.is_temporary:
                item.assignment_id = assignment_id
                item.is_temporary = False
                changed = True
        if changed:
            await self.repo.save()

    async def validate_uploads(
        self,
        management_system_id: str,
        file_keys: Iterable[str],
    ) -> None:
        """
        功能描述：
            校验uploads。

        参数：
            management_system_id (str): 管理系统ID，用于限制数据作用域。
            file_keys (Iterable[str]): 文件对象或文件标识。

        返回值：
            None: 无返回值。
        """
        normalized_file_keys = sorted({file_key for file_key in file_keys if file_key})
        await self._require_uploaded_items(management_system_id, normalized_file_keys)

    async def _require_uploaded_items(
        self,
        management_system_id: str,
        normalized_file_keys: list[str],
    ) -> list[AssignmentAttachmentUpload]:
        """
        功能描述：
            处理uploadeditems。

        参数：
            management_system_id (str): 管理系统ID，用于限制数据作用域。
            normalized_file_keys (list[str]): 文件对象或文件标识。

        返回值：
            list[AssignmentAttachmentUpload]: 返回列表形式的结果数据。
        """
        uploaded_items = await self.repo.list_by_file_keys(management_system_id, normalized_file_keys)
        uploaded_by_key = {item.file_key: item for item in uploaded_items}
        missing_file_keys = sorted(set(normalized_file_keys) - set(uploaded_by_key))
        if missing_file_keys:
            raise ValueError("存在未上传或不可访问的作业附件")
        return uploaded_items
