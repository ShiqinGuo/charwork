"""
ES 搜索服务基类，封装索引管理、文档操作、ensure_index 缓存等公共逻辑。
"""

import logging

from elasticsearch import NotFoundError
from elasticsearch.helpers import async_bulk
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.es_client import get_es_client
from app.schemas.search import ReindexResponse


logger = logging.getLogger(__name__)

_ensured_indexes: set[str] = set()


class BaseSearchService:
    REINDEX_BULK_CHUNK_SIZE: int = 500

    def __init__(self, db: AsyncSession):
        self.db = db
        self.es = get_es_client()
        self.index_name: str = ""

    async def ensure_index(self) -> None:
        if self.index_name in _ensured_indexes:
            return
        exists = await self.es.indices.exists(index=self.index_name)
        if exists:
            _ensured_indexes.add(self.index_name)
            return
        await self._create_index()
        _ensured_indexes.add(self.index_name)

    async def _create_index(self) -> None:
        raise NotImplementedError

    async def ensure_index_with_bootstrap(self) -> ReindexResponse | int:
        await self.ensure_index()
        return await self.reindex()

    async def _delete_document(self, doc_id: str) -> None:
        try:
            await self.es.delete(index=self.index_name, id=doc_id, refresh=False)
        except NotFoundError:
            return

    async def _index_document(self, doc_id: str, document: dict, refresh: bool = False) -> None:
        await self.es.index(index=self.index_name, id=doc_id, document=document, refresh=refresh)

    async def _bulk_index(self, actions: list[dict]) -> tuple[int, int]:
        if not actions:
            return 0, 0
        success, errors = await async_bulk(
            self.es, actions,
            chunk_size=self.REINDEX_BULK_CHUNK_SIZE,
            refresh=False,
            raise_on_error=False,
        )
        return success, len(errors)

    async def reindex(self) -> ReindexResponse | int:
        raise NotImplementedError

    async def _refresh_index_safe(self) -> None:
        """安全刷新索引，失败时仅记录日志。"""
        try:
            await self.es.indices.refresh(index=self.index_name)
        except Exception:
            logger.exception("ES refresh 索引失败: %s", self.index_name)

    def _build_reindex_response(self, indexed: int, failed: int) -> ReindexResponse:
        status = "success" if failed == 0 else "partial"
        return ReindexResponse(status=status, indexed=indexed, failed=failed)

    @classmethod
    def invalidate_index_cache(cls, index_name: str | None = None) -> None:
        if index_name:
            _ensured_indexes.discard(index_name)
        else:
            _ensured_indexes.clear()
