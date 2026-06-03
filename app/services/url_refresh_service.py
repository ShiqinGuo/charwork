"""
ImageX URL 定时刷新服务。

遍历配置注册表，对每张表的存量记录调用 GetResourceURL API 重新签名，
更新即将过期的 URL。使用 url_refreshed_at 避免重复刷新近期已签名的记录。
"""

import logging
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from urllib.parse import urlparse

from app.core.config import settings
from app.core.url_refresh_config import URL_REFRESH_TABLE_CONFIG
from app.core.database import AsyncSessionLocal
from volcengine.imagex.v2.imagex_service import ImagexService

logger = logging.getLogger(__name__)

# URL 签名有效期（鉴权未生效时实际约 30 分钟）
_IMAGEX_URL_TTL = 2592000

# 刷新阈值：距上次刷新超过 15 分钟即重新签名（保证在 30 分钟过期前续签）
_REFRESH_THRESHOLD_MINUTES = 15

# URI 提取正则：匹配 /{uri}~{tpl}.{format} 格式
_URI_PATTERN = re.compile(r"/(.+?)~[^/]+?\.[\w]+$")


class UrlRefreshService:
    """ImageX URL 刷新服务"""

    def __init__(self, imagex_service: ImagexService):
        self._imagex = imagex_service

    def refresh_all(self) -> dict[str, int]:
        """同步入口（供 Celery task 调用），遍历注册表刷新所有启用表。"""
        import asyncio

        return asyncio.run(self._refresh_all_async())

    async def _refresh_all_async(self) -> dict[str, int]:
        """异步实现，逐表刷新。"""
        results: dict[str, int] = {}
        async with AsyncSessionLocal() as db:
            for model_cls, cfg in URL_REFRESH_TABLE_CONFIG.items():
                if not cfg.get("enabled", True):
                    continue
                tablename = model_cls.__tablename__
                try:
                    count = await self._refresh_table(db, model_cls, cfg)
                    results[tablename] = count
                except Exception:
                    logger.exception("刷新表 %s 的 ImageX URL 失败", tablename)
                    results[tablename] = -1
            return results

    async def _refresh_table(
        self,
        db: AsyncSession,
        model_cls: type,
        cfg: dict[str, object],
    ) -> int:
        url_field = str(cfg["url_field"])
        uri_field = str(cfg["uri_field"])
        batch_size = settings.URL_REFRESH_BATCH_SIZE
        refreshed = 0

        uri_col = getattr(model_cls, uri_field)
        refreshed_at_col = getattr(model_cls, "url_refreshed_at")
        domains = [d.strip() for d in settings.URL_REFRESH_DOMAINS.split(",") if d.strip()]

        # 只刷超过 15 分钟未刷新的记录，避免同一轮反复签
        threshold = datetime.now(timezone.utc) - timedelta(minutes=_REFRESH_THRESHOLD_MINUTES)
        # 每轮处理的批量大小，避免一次性加载过多 ORM 对象导致 MemoryError
        chunk_size = min(batch_size, 200)

        while True:
            result = await db.execute(
                select(model_cls)
                .where(uri_col.isnot(None))
                .where(
                    (refreshed_at_col.is_(None)) | (refreshed_at_col < threshold)
                )
                .limit(chunk_size)
            )
            rows = result.scalars().all()
            if not rows:
                break

            for row in rows:
                uri_val = getattr(row, uri_field)
                if not uri_val:
                    continue

                current_url = getattr(row, url_field, "") or ""
                if domains and not any(d in current_url for d in domains):
                    continue

                try:
                    new_url = self._get_resource_url(uri_val)
                    if new_url:
                        await db.execute(
                            update(model_cls)
                            .where(model_cls.id == row.id)
                            .values(
                                **{
                                    url_field: new_url,
                                    "url_refreshed_at": datetime.now(timezone.utc),
                                }
                            )
                        )
                        refreshed += 1
                except Exception:
                    logger.exception(
                        "刷新 %s id=%s 的 URL 失败", model_cls.__tablename__, row.id
                    )

            await db.commit()

        logger.info("表 %s 刷新完成，共刷新 %d 条", model_cls.__tablename__, refreshed)
        return refreshed

    def _get_resource_url(self, uri: str) -> str:
        """调用 veImageX GetResourceURL API 生成新签名 URL。"""
        params = {
            "ServiceId": settings.VOLCENGINE_SERVICE_ID,
            "Domain": settings.IMAGEX_DEFAULT_DOMAIN,
            "URI": uri,
            "Tpl": settings.IMAGEX_TEMPLATE_ID,
            "Proto": "https",
            "Format": "jpeg",
            "Timestamp": _IMAGEX_URL_TTL,
        }
        result = self._imagex.get_resource_url(params)
        return result.get("Result", {}).get("URL", "")

    @staticmethod
    def extract_uri_from_url(url: str) -> str | None:
        """从 ImageX 签名 URL 中提取 URI，用于存量数据回填。"""
        if not url:
            return None
        parsed = urlparse(url)
        path = parsed.path.lstrip("/")
        if not path:
            return None
        match = _URI_PATTERN.search("/" + path)
        if match:
            return match.group(1)
        return None
