"""
数据迁移脚本：将 Submission.image_paths 迁移到 Attachment 表。

此脚本用于将现有系统中存储在 Submission 表的 image_paths 字段数据
迁移到新的 Attachment 表，实现附件管理的统一化。

使用方式：
    python scripts/migrate_image_paths_to_attachments.py
"""

import asyncio
import sys
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.config import settings
from app.models.submission import Submission
from app.models.attachment import Attachment
from app.utils.id_generator import generate_id


async def migrate_image_paths() -> None:
    """
    将 Submission.image_paths 迁移到 Attachment 表。

    遍历所有 Submission 记录，对每个 image_paths 数组中的 URL 创建
    对应的 Attachment 记录，保留原始提交 ID 和管理系统 ID。
    """
    engine = create_async_engine(settings.DATABASE_URL)
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    try:
        async with async_session() as session:
            # 查询所有提交记录
            result = await session.execute(select(Submission))
            submissions = result.scalars().all()

            migrated_count = 0
            attachment_count = 0

            for submission in submissions:
                # 跳过没有 image_paths 的提交
                if not hasattr(submission, "image_paths") or not submission.image_paths:
                    continue

                # 为每个图片 URL 创建 Attachment 记录
                for idx, image_url in enumerate(submission.image_paths):
                    attachment = Attachment(
                        id=generate_id(),
                        owner_type="submission",
                        owner_id=submission.id,
                        file_url=image_url,
                        filename=f"image_{idx + 1}.jpg",
                        file_size=0,  # 未知大小
                        mime_type="image/jpeg",
                        management_system_id=submission.management_system_id,
                    )
                    session.add(attachment)
                    attachment_count += 1

                migrated_count += 1

            # 提交所有变更
            await session.commit()
            print(f"迁移完成：处理了 {migrated_count} 条提交记录，创建了 {attachment_count} 条附件记录")

    except Exception as e:
        print(f"迁移失败：{e}", file=sys.stderr)
        raise
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(migrate_image_paths())
