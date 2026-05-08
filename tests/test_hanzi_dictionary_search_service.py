import os
from datetime import datetime
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("MYSQL_HOST", "localhost")
os.environ.setdefault("MYSQL_PORT", "3306")
os.environ.setdefault("MYSQL_USER", "root")
os.environ.setdefault("MYSQL_PASSWORD", "root")
os.environ.setdefault("MYSQL_DB", "charwork")

SEARCH_READY = True

try:
    from app.services.hanzi_dictionary_search_service import HanziDictionarySearchService
    from app.utils.hanzi_dictionary_parser import encode_stroke_unit_key
except ModuleNotFoundError:
    SEARCH_READY = False


class FakeIndices:
    def __init__(self):
        self.exists_response = True
        self.created = []
        self.deleted = []
        self.refreshed = []

    async def exists(self, index: str):
        return self.exists_response

    async def create(self, index: str, body: dict):
        self.created.append((index, body))
        self.exists_response = True

    async def delete(self, index: str):
        self.deleted.append(index)
        self.exists_response = False

    async def refresh(self, index: str):
        self.refreshed.append(index)


class FakeES:
    def __init__(self):
        self.indices = FakeIndices()
        self.count_response = {"count": 1}
        self.search_response = {
            "hits": {
                "total": {"value": 1},
                "hits": [{"_source": {"dictionary_id": "dict-1"}}],
            }
        }
        self.index_calls = []
        self.delete_calls = []
        self.search_calls = []

    async def count(self, index: str):
        return self.count_response

    async def search(self, index: str, body: dict):
        self.search_calls.append((index, body))
        return self.search_response

    async def index(self, **kwargs):
        self.index_calls.append(kwargs)

    async def delete(self, **kwargs):
        self.delete_calls.append(kwargs)


_ES_CLIENT_PATCH = "app.services.base_search_service.get_es_client"


if SEARCH_READY:
    class HanziDictionarySearchServiceTests(unittest.IsolatedAsyncioTestCase):

        def setUp(self):
            from app.services.base_search_service import _ensured_indexes
            _ensured_indexes.clear()

        async def test_search_builds_duplicate_count_filters(self):
            fake_es = FakeES()
            with patch(_ES_CLIENT_PATCH, return_value=fake_es):
                service = HanziDictionarySearchService(AsyncMock())

            result = await service.search(
                skip=20,
                limit=10,
                character="中",
                pinyin=" zhong ",
                stroke_count=5,
                stroke_pattern="横,横,撇",
                keyword="zhong",
            )

            self.assertEqual(result, {"ids": ["dict-1"], "total": 1})
            body = fake_es.search_calls[0][1]
            filters = body["query"]["bool"]["filter"]
            self.assertIn({"term": {"stroke_count": 5}}, filters)
            self.assertIn({"term": {"stroke_units": "横"}}, filters)
            self.assertIn({"term": {"stroke_units": "撇"}}, filters)
            self.assertTrue(any("script" in item for item in filters))
            self.assertEqual(body["from"], 20)
            self.assertEqual(body["size"], 10)

        async def test_build_document_stores_exact_units_and_counts(self):
            fake_es = FakeES()
            with patch(_ES_CLIENT_PATCH, return_value=fake_es):
                service = HanziDictionarySearchService(AsyncMock())

            item = SimpleNamespace(
                id="dict-1",
                character="文",
                pinyin="wen",
                stroke_count=3,
                stroke_pattern="撇,横,横",
                source="strokes_txt",
                updated_at=datetime.utcnow(),
            )

            document = service._build_document(item)

            self.assertEqual(document["stroke_units"], ["撇", "横", "横"])
            self.assertEqual(
                document["stroke_unit_counts"],
                {
                    encode_stroke_unit_key("撇"): 1,
                    encode_stroke_unit_key("横"): 2,
                },
            )

        async def test_reindex_returns_reindex_response(self):
            from app.schemas.search import ReindexResponse
            from unittest.mock import MagicMock
            fake_es = FakeES()
            with patch(_ES_CLIENT_PATCH, return_value=fake_es):
                service = HanziDictionarySearchService(AsyncMock())
                # execute() 是 async，返回值是同步的 result 对象
                mock_result = MagicMock()
                mock_result.scalars.return_value.all.return_value = []
                service.db.execute.return_value = mock_result
                with patch("app.services.base_search_service.async_bulk", return_value=(0, [])):
                    result = await service.reindex()
            self.assertIsInstance(result, ReindexResponse)
else:
    @unittest.skip("当前环境缺少共享字典 ES 检索依赖")
    class HanziDictionarySearchServiceTests(unittest.TestCase):
        def test_skip_when_dependencies_unavailable(self):
            self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
