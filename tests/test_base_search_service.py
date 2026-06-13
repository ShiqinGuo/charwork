from app.services.cross_search_service import CrossSearchService
import unittest
from unittest.mock import AsyncMock, patch

from app.services.base_search_service import BaseSearchService, _ensured_indexes


class FakeIndices:
    def __init__(self):
        self.exists_response = False
        self.created = []

    async def exists(self, index: str):
        return self.exists_response

    async def create(self, index: str, body: dict):
        self.created.append(index)


class FakeES:
    def __init__(self):
        self.indices = FakeIndices()


class TestBaseSearchService(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        _ensured_indexes.clear()

    async def test_ensure_index_creates_when_not_exists(self):
        fake_es = FakeES()
        with patch("app.services.base_search_service.get_es_client", return_value=fake_es):
            service = BaseSearchService(AsyncMock())
            service.index_name = "test_index"
            service._create_index = AsyncMock()
            await service.ensure_index()
        self.assertIn("test_index", _ensured_indexes)
        service._create_index.assert_called_once()

    async def test_ensure_index_skips_when_cached(self):
        _ensured_indexes.add("test_index")
        fake_es = FakeES()
        with patch("app.services.base_search_service.get_es_client", return_value=fake_es):
            service = BaseSearchService(AsyncMock())
            service.index_name = "test_index"
            await service.ensure_index()
        self.assertEqual(len(fake_es.indices.created), 0)

    async def test_ensure_index_skips_when_es_reports_exists(self):
        fake_es = FakeES()
        fake_es.indices.exists_response = True
        with patch("app.services.base_search_service.get_es_client", return_value=fake_es):
            service = BaseSearchService(AsyncMock())
            service.index_name = "test_index"
            await service.ensure_index()
        self.assertIn("test_index", _ensured_indexes)
        self.assertEqual(len(fake_es.indices.created), 0)

    async def test_invalidate_index_cache_specific(self):
        _ensured_indexes.add("index_a")
        _ensured_indexes.add("index_b")
        BaseSearchService.invalidate_index_cache("index_a")
        self.assertNotIn("index_a", _ensured_indexes)
        self.assertIn("index_b", _ensured_indexes)

    async def test_invalidate_index_cache_all(self):
        _ensured_indexes.add("index_a")
        _ensured_indexes.add("index_b")
        BaseSearchService.invalidate_index_cache()
        self.assertEqual(len(_ensured_indexes), 0)

    async def test_delete_document_ignores_not_found(self):
        from elasticsearch import NotFoundError
        fake_es = AsyncMock()
        fake_es.delete.side_effect = NotFoundError("", "", 404)
        with patch("app.services.base_search_service.get_es_client", return_value=fake_es):
            service = BaseSearchService(AsyncMock())
            service.index_name = "test_index"
            await service._delete_document("doc-1")  # 不应抛异常

    async def test_index_document_calls_es_index(self):
        fake_es = AsyncMock()
        with patch("app.services.base_search_service.get_es_client", return_value=fake_es):
            service = BaseSearchService(AsyncMock())
            service.index_name = "test_index"
            await service._index_document("doc-1", {"title": "hello"})
        fake_es.index.assert_called_once_with(
            index="test_index", id="doc-1", document={"title": "hello"}, refresh=False
        )

    async def test_bulk_index_returns_counts(self):
        fake_es = AsyncMock()
        with patch("app.services.base_search_service.async_bulk", return_value=(5, [])) as mock_bulk:
            with patch("app.services.base_search_service.get_es_client", return_value=fake_es):
                service = BaseSearchService(AsyncMock())
                service.index_name = "test_index"
                success, failed = await service._bulk_index([{"_op_type": "index"}])
        self.assertEqual(success, 5)
        self.assertEqual(failed, 0)

    async def test_bulk_index_empty_actions(self):
        fake_es = AsyncMock()
        with patch("app.services.base_search_service.get_es_client", return_value=fake_es):
            service = BaseSearchService(AsyncMock())
            service.index_name = "test_index"
            success, failed = await service._bulk_index([])
        self.assertEqual(success, 0)
        self.assertEqual(failed, 0)


if __name__ == "__main__":
    unittest.main()


class TestCrossSearchServiceInheritance(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        _ensured_indexes.clear()

    async def test_inherits_base_search_service(self):
        with patch("app.services.base_search_service.get_es_client", return_value=FakeES()):
            with patch("app.services.cross_search_service.get_enabled_search_module_configs", return_value={}):
                service = CrossSearchService(AsyncMock())
        self.assertIsInstance(service, BaseSearchService)

    async def test_ensure_index_uses_cache(self):
        _ensured_indexes.add("charwork_global_search")
        fake_es = FakeES()
        with patch("app.services.base_search_service.get_es_client", return_value=fake_es):
            with patch("app.services.cross_search_service.get_enabled_search_module_configs", return_value={}):
                service = CrossSearchService(AsyncMock())
                await service.ensure_index()
        self.assertEqual(len(fake_es.indices.created), 0)

    async def test_reindex_uses_bulk_index(self):
        from unittest.mock import MagicMock
        from app.services.search_registry import SearchModuleConfig, SearchDocument

        fake_es = FakeES()
        fake_es.indices.exists_response = True
        doc = SearchDocument(module="test", source_id="1", title="t", content="c")
        config = SearchModuleConfig(
            table="test_table",
            module="test",
            load_all=AsyncMock(return_value=[MagicMock()]),
            load_one=AsyncMock(return_value=MagicMock()),
            build_document=AsyncMock(return_value=doc),
            preload=AsyncMock(return_value={}),
        )
        with patch("app.services.base_search_service.get_es_client", return_value=fake_es):
            with patch("app.services.cross_search_service.get_enabled_search_module_configs", return_value={"test_table": config}):
                with patch("app.services.base_search_service.async_bulk", return_value=(1, [])) as mock_bulk:
                    service = CrossSearchService(AsyncMock())
                    service.index_name = "test_global_search"
                    result = await service.reindex()
        self.assertEqual(result.indexed, 1)
        self.assertEqual(result.failed, 0)
        mock_bulk.assert_called_once()
