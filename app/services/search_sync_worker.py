import asyncio
import json
import logging
from typing import Any

import aio_pika

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.services.cross_search_service import CrossSearchService


logger = logging.getLogger(__name__)


class SearchSyncWorker:
    def __init__(self):
        self.allowed_tables = {
            i.strip() for i in settings.SEARCH_SYNC_CANAL_TABLES.split(",") if i.strip()
        }
        self.allowed_schema = settings.SEARCH_SYNC_CANAL_SCHEMA or settings.MYSQL_DB

    async def run(self) -> None:
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
        async with message.process(requeue=False):
            payload = self._parse_json(message.body)
            if payload is None:
                return
            changes = self._extract_changes(payload)
            if not changes:
                return
            async with AsyncSessionLocal() as db:
                service = CrossSearchService(db)
                for table, operation, row in changes:
                    await service.apply_cdc_change(table, operation, row)

    def _parse_json(self, body: bytes) -> dict[str, Any] | list[dict[str, Any]] | None:
        try:
            return json.loads(body.decode("utf-8"))
        except Exception as e:
            logger.error("Canal消息解析失败：%s", str(e))
            return None

    def _extract_changes(self, payload: dict[str, Any] | list[dict[str, Any]]) -> list[tuple[str, str, dict]]:
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
    logging.basicConfig(level=logging.INFO)
    await SearchSyncWorker().run()


if __name__ == "__main__":
    asyncio.run(main())
