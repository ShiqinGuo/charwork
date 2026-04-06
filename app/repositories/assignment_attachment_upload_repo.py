from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assignment_attachment_upload import AssignmentAttachmentUpload


class AssignmentAttachmentUploadRepository:
    def __init__(self, db: AsyncSession):
        """
        功能描述：
            初始化AssignmentAttachmentUploadRepository并准备运行所需的依赖对象。

        参数：
            db (AsyncSession): 数据库会话，用于执行持久化操作。

        返回值：
            None: 无返回值。
        """
        self.db = db

    async def create(self, item: AssignmentAttachmentUpload) -> AssignmentAttachmentUpload:
        """
        功能描述：
            创建AssignmentAttachmentUploadRepository。

        参数：
            item (AssignmentAttachmentUpload): 当前处理的实体对象。

        返回值：
            AssignmentAttachmentUpload: 返回AssignmentAttachmentUpload类型的处理结果。
        """
        self.db.add(item)
        await self.db.commit()
        await self.db.refresh(item)
        return item

    async def list_by_assignment(
        self,
        assignment_id: str,
        management_system_id: str,
    ) -> list[AssignmentAttachmentUpload]:
        """
        功能描述：
            按条件查询by作业列表。

        参数：
            assignment_id (str): 作业ID。
            management_system_id (str): 管理系统ID，用于限制数据作用域。

        返回值：
            list[AssignmentAttachmentUpload]: 返回列表形式的结果数据。
        """
        result = await self.db.execute(
            select(AssignmentAttachmentUpload).where(
                AssignmentAttachmentUpload.assignment_id == assignment_id,
                AssignmentAttachmentUpload.management_system_id == management_system_id,
            )
        )
        return list(result.scalars().all())

    async def list_by_file_keys(
        self,
        management_system_id: str,
        file_keys: Sequence[str],
    ) -> list[AssignmentAttachmentUpload]:
        """
        功能描述：
            按条件查询by文件keys列表。

        参数：
            management_system_id (str): 管理系统ID，用于限制数据作用域。
            file_keys (Sequence[str]): 文件对象或文件标识。

        返回值：
            list[AssignmentAttachmentUpload]: 返回列表形式的结果数据。
        """
        if not file_keys:
            return []
        result = await self.db.execute(
            select(AssignmentAttachmentUpload).where(
                AssignmentAttachmentUpload.management_system_id == management_system_id,
                AssignmentAttachmentUpload.file_key.in_(list(file_keys)),
            )
        )
        return list(result.scalars().all())

    async def save(self) -> None:
        """
        功能描述：
            保存AssignmentAttachmentUploadRepository。

        参数：
            无。

        返回值：
            None: 无返回值。
        """
        await self.db.commit()
