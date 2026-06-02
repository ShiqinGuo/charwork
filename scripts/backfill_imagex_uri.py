"""
存量 ImageX URI 回填脚本。

从现有 file_url / image_path 中提取 ImageX URI，回填到 uri 字段。
解析失败的记录跳过（后续自然过期淘汰）。

用法：python scripts/backfill_imagex_uri.py
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, update

from app.core.database import AsyncSessionLocal
from app.models.attachment import Attachment
from app.models.hanzi import Hanzi
from app.services.url_refresh_service import UrlRefreshService


async def backfill_attachment() -> int:
    """回填 attachment 表的 uri 字段。"""
    count = 0
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Attachment.id, Attachment.file_url).where(Attachment.uri.is_(None))
        )
        rows = result.all()
        for row in rows:
            uri = UrlRefreshService.extract_uri_from_url(row.file_url or "")
            if uri:
                await db.execute(
                    update(Attachment)
                    .where(Attachment.id == row.id)
                    .values(uri=uri)
                )
                count += 1
            if count > 0 and count % 100 == 0:
                print(f"  attachment 已回填 {count} 条...")
        await db.commit()
    return count


async def backfill_hanzi() -> int:
    """回填 hanzi 表的 uri 字段。"""
    count = 0
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Hanzi.id, Hanzi.image_path).where(Hanzi.uri.is_(None))
        )
        rows = result.all()
        for row in rows:
            uri = UrlRefreshService.extract_uri_from_url(row.image_path or "")
            if uri:
                await db.execute(
                    update(Hanzi)
                    .where(Hanzi.id == row.id)
                    .values(uri=uri)
                )
                count += 1
            if count > 0 and count % 100 == 0:
                print(f"  hanzi 已回填 {count} 条...")
        await db.commit()
    return count


async def main() -> None:
    print("开始回填 ImageX URI...")
    att_count = await backfill_attachment()
    hanzi_count = await backfill_hanzi()
    print(f"回填完成：attachment={att_count}, hanzi={hanzi_count}")


if __name__ == "__main__":
    asyncio.run(main())
