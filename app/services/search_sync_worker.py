"""
为什么这样做：同步 worker 只消费配置允许的表，降低 CDC 噪声对检索链路的影响。
特殊逻辑：消息解析后按“共享字典/跨模块检索”分流处理，并对 schema 与操作类型做边界过滤。
"""

import asyncio
import json
import logging
from typing import Any

import aio_pika

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.services.hanzi_dictionary_search_service import HanziDictionarySearchService


logger = logging.getLogger(__name__)
DICTIONARY_SEARCH_TABLE = "hanzi_dictionary"


def get_configured_search_sync_tables() -> set[str]:
    return {item.strip() for item in settings.SEARCH_SYNC_CANAL_TABLES.split(",") if item.strip()}


class SearchSyncWorker:
    def __init__(self):
        """
        功能描述：
            初始化SearchSyncWorker并准备运行所需的依赖对象。

        参数：
            无。

        返回值：
            None: 无返回值。
        """
        self.allowed_tables = get_configured_search_sync_tables()
        self.unregistered_tables = self.allowed_tables - {DICTIONARY_SEARCH_TABLE}
        self.allowed_schema = settings.SEARCH_SYNC_CANAL_SCHEMA or settings.MYSQL_DB
        for table in sorted(self.unregistered_tables):
            logger.warning("检索同步监听配置了未注册表：%s", table)

    async def run(self) -> None:
        """
        功能描述：
            处理SearchSyncWorker。

        参数：
            无。

        返回值：
            None: 无返回值。
        """
        if not settings.SEARCH_SYNC_ENABLED:
            logger.info("检索同步监听已禁用")
            return
        connection = await aio_pika.connect_robust(settings.SEARCH_SYNC_RABBITMQ_URL)
        async with connection:
            channel = await connection.channel()
            await channel.set_qos(prefetch_count=settings.SEARCH_SYNC_RABBITMQ_PREFETCH)
            queue = await channel.declare_queue(settings.SEARCH_SYNC_RABBITMQ_QUEUE, durable=True)
            await queue.consume(self._on_message, no_ack=False)
            logger.info("检索同步监听启动，queue=%s", settings.SEARCH_SYNC_RABBITMQ_QUEUE)
            await asyncio.Future()

    async def _on_message(self, message: aio_pika.IncomingMessage) -> None:
        """
        功能描述：
            处理消息。

        参数：
            message (aio_pika.IncomingMessage): aio_pika.IncomingMessage 类型的数据。

        返回值：
            None: 无返回值。
        """
        async with message.process(requeue=False):
            payload = self._parse_json(message.body)
            if payload is None:
                return
            changes = self._extract_changes(payload)
            if not changes:
                return
            async with AsyncSessionLocal() as db:
                hanzi_dictionary_search_service = HanziDictionarySearchService(db)
                for table, operation, row in changes:
                    if table == DICTIONARY_SEARCH_TABLE:
                        await hanzi_dictionary_search_service.apply_cdc_change(operation, row)

    def _parse_json(self, body: bytes) -> dict[str, Any] | list[dict[str, Any]] | None:
        """
        功能描述：
            解析json。

        参数：
            body (bytes): 接口请求体对象。

        返回值：
            dict[str, Any] | list[dict[str, Any]] | None: 返回字典形式的结果数据。
        """
        try:
            return json.loads(body.decode("utf-8"))
        except Exception as e:
            logger.error("Canal消息解析失败：%s", str(e))
            return None

    def _extract_changes(self, payload: dict[str, Any] | list[dict[str, Any]]) -> list[tuple[str, str, dict]]:
        """
        功能描述：
            提取changes。

        参数：
            payload (dict[str, Any] | list[dict[str, Any]]): 待处理的原始数据载荷。

        返回值：
            list[tuple[str, str, dict]]: 返回列表形式的结果数据。
        """
        if isinstance(payload, list):
            changes: list[tuple[str, str, dict]] = []
            for item in payload:
                changes.extend(self._extract_changes(item))
            return changes
        database = str(payload.get("database") or "")
        table = str(payload.get("table") or "")
        if self.allowed_schema and database and database != self.allowed_schema:
            return []
        if table not in self.allowed_tables:
            return []
        if payload.get("isDdl"):
            return []
        operation = str(payload.get("type") or "").lower()
        if operation not in {"insert", "update", "delete"}:
            return []
        rows = payload.get("data") or []
        if not isinstance(rows, list):
            return []
        return [(table, operation, row) for row in rows if isinstance(row, dict)]


async def main() -> None:
    """
    功能描述：
        处理检索同步工作器。

    参数：
        无。

    返回值：
        None: 无返回值。
    """
    logging.basicConfig(level=logging.INFO)
    await SearchSyncWorker().run()


if __name__ == "__main__":
    asyncio.run(main())
