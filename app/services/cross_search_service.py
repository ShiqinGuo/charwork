"""
为什么这样做：跨模块检索统一落 ES 全局索引，屏蔽各业务表差异，提供一致检索入口。
特殊逻辑：索引分析器与权限过滤都在服务层集中控制；学生命中结果需二次按课程/班级边界裁剪。
"""

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from elasticsearch import NotFoundError

from app.core.config import settings
from app.core.es_client import get_es_client
from app.core.security import SessionUser
from app.models.user import UserRole
from app.repositories.course_repo import CourseRepository
from app.repositories.student_repo import StudentRepository
from app.repositories.teaching_class_repo import TeachingClassRepository
from app.schemas.search import CrossSearchResponse, SearchHit, ReindexResponse
from app.services.search_registry import SearchDocument, get_enabled_search_module_configs


logger = logging.getLogger(__name__)


class CrossSearchService:
    def __init__(self, db: AsyncSession):
        """
        功能描述：
            初始化CrossSearchService并准备运行所需的依赖对象。

        参数：
            db (AsyncSession): 数据库会话，用于执行持久化操作。

        返回值：
            None: 无返回值。
        """
        self.db = db
        self.es = get_es_client()
        self.index_name = f"{settings.ELASTICSEARCH_INDEX_PREFIX}_global_search"
        self.module_configs = get_enabled_search_module_configs()

    async def ensure_index(self) -> None:
        """
        功能描述：
            确保索引存在，必要时自动补齐。

        参数：
            无。

        返回值：
            None: 无返回值。
        """
        exists = await self.es.indices.exists(index=self.index_name)
        if exists:
            return
        await self.es.indices.create(
            index=self.index_name,
            body={
                "settings": {
                    "analysis": {
                        "analyzer": {
                            "charwork_ngram_analyzer": {
                                "tokenizer": "charwork_ngram_tokenizer",
                                "filter": ["lowercase"],
                            }
                        },
                        "tokenizer": {
                            "charwork_ngram_tokenizer": {
                                "type": "ngram",
                                "min_gram": 1,
                                "max_gram": 2,
                                "token_chars": ["letter", "digit"],
                            }
                        },
                    }
                },
                "mappings": {
                    "properties": {
                        "module": {"type": "keyword"},
                        "source_id": {"type": "keyword"},
                        "management_system_ids": {"type": "keyword"},
                        "title": {"type": "text", "analyzer": "charwork_ngram_analyzer"},
                        "content": {"type": "text", "analyzer": "charwork_ngram_analyzer"},
                    }
                },
            },
        )

    async def ensure_index_with_bootstrap(self) -> ReindexResponse:
        """
        功能描述：
            确保索引withbootstrap存在，必要时自动补齐。

        参数：
            无。

        返回值：
            ReindexResponse: 返回ReindexResponse类型的处理结果。
        """
        await self.ensure_index()
        return await self.reindex()

    async def _upsert_document(self, doc_id: str, document: SearchDocument) -> None:
        """
        功能描述：
            新增或更新document。

        参数：
            doc_id (str): docID。
            document (SearchDocument): SearchDocument 类型的数据。

        返回值：
            None: 无返回值。
        """
        payload = {
            "module": document.module,
            "source_id": document.source_id,
            "management_system_ids": document.management_system_ids,
            "title": document.title,
            "content": document.content,
        }
        payload.update(document.extra_fields)
        await self.es.index(
            index=self.index_name,
            id=doc_id,
            document=payload,
            refresh=False,
        )

    async def _delete_document(self, doc_id: str) -> None:
        """
        功能描述：
            删除document。

        参数：
            doc_id (str): docID。

        返回值：
            None: 无返回值。
        """
        try:
            await self.es.delete(index=self.index_name, id=doc_id, refresh=False)
        except NotFoundError:
            return

    async def reindex(self) -> ReindexResponse:
        """
        功能描述：
            处理CrossSearchService。

        参数：
            无。

        返回值：
            ReindexResponse: 返回ReindexResponse类型的处理结果。
        """
        await self.ensure_index()
        indexed = 0
        for table, config in self.module_configs.items():
            items = await config.load_all(self.db)
            for item in items:
                document = await config.build_document(self.db, item)
                if not document:
                    continue
                await self._upsert_document(self._build_document_id(table, document.source_id), document)
                indexed += 1
        await self.es.indices.refresh(index=self.index_name)
        return ReindexResponse(status="success", indexed=indexed)

    async def apply_cdc_change(self, table: str, operation: str, data: dict) -> None:
        """
        功能描述：
            处理cdcchange。

        参数：
            table (str): 字符串结果。
            operation (str): 字符串结果。
            data (dict): 字典形式的结果数据。

        返回值：
            None: 无返回值。
        """
        await self.ensure_index()
        operation = (operation or "").lower()
        source_id = data.get("id")
        if not source_id:
            return
        config = self.module_configs.get(table)
        if not config:
            logger.warning("跨模块检索收到未注册或未启用的表变更：%s", table)
            return
        doc_id = self._build_document_id(table, str(source_id))
        if operation == "delete":
            await self._delete_document(doc_id)
            return
        item = await config.load_one(self.db, str(source_id))
        if not item:
            await self._delete_document(doc_id)
            return
        document = await config.build_document(self.db, item)
        if not document:
            await self._delete_document(doc_id)
            return
        await self._upsert_document(doc_id, document)

    async def search(
        self,
        keyword: str,
        current_user: SessionUser,
        management_system_id: str,
        modules: Optional[list[str]] = None,
        limit: int = 20,
    ) -> CrossSearchResponse:
        """
        功能描述：
            检索CrossSearchService。

        参数：
            keyword (str): 字符串结果。
            current_user (SessionUser): 当前登录用户对象。
            management_system_id (str): 管理系统ID，用于限制数据作用域。
            modules (Optional[list[str]]): 列表结果。
            limit (int): 单次查询的最大返回数量。

        返回值：
            CrossSearchResponse: 返回CrossSearchResponse类型的处理结果。
        """
        await self.ensure_index()
        allowed_modules = self._normalize_requested_modules(modules)
        must = [
            {
                "multi_match": {
                    "query": keyword,
                    "fields": ["title^2", "content"],
                }
            }
        ]
        filter_query = [{"term": {"management_system_ids": management_system_id}}]
        if allowed_modules:
            filter_query.append({"terms": {"module": allowed_modules}})
        # ES 先按更宽松的条件召回候选结果，再由业务权限过滤做二次裁剪，避免因索引字段不足漏召回。
        response = await self.es.search(
            index=self.index_name,
            body={
                "query": {
                    "bool": {
                        "must": must,
                        "filter": filter_query,
                    }
                },
                "size": min(max(limit * 5, limit), 100),
            },
        )
        hits = response.get("hits", {}).get("hits", [])
        hits = await self._filter_hits_by_permissions(
            hits=hits,
            current_user=current_user,
            management_system_id=management_system_id,
            modules=allowed_modules,
        )
        items = [
            self._to_search_hit(hit)
            for hit in hits[:limit]
        ]
        return CrossSearchResponse(keyword=keyword, total=len(items), items=items)

    async def _filter_hits_by_permissions(
        self,
        hits: list[dict],
        current_user: SessionUser,
        management_system_id: str,
        modules: list[str] | None,
    ) -> list[dict]:
        """
        功能描述：
            过滤hitsbypermissions。

        参数：
            hits (list[dict]): 列表结果。
            current_user (SessionUser): 当前登录用户对象。
            management_system_id (str): 管理系统ID，用于限制数据作用域。
            modules (list[str] | None): 列表结果。

        返回值：
            list[dict]: 返回列表形式的结果数据。
        """
        if current_user.role != UserRole.STUDENT:
            if not modules:
                return hits
            return [hit for hit in hits if hit.get("_source", {}).get("module") in modules]
        # 学生权限依赖实际入班与选课关系，不能只看检索索引中的模块字段。
        student = await StudentRepository(self.db).get_by_user_id(current_user.id)
        if not student:
            return []
        course_ids = set(await CourseRepository(self.db).list_ids_for_student(student.id, management_system_id))
        class_ids = set(await TeachingClassRepository(self.db).list_ids_for_student(student.id, management_system_id))
        filtered_hits: list[dict] = []
        for hit in hits:
            source = hit.get("_source", {})
            module = str(source.get("module") or "")
            if modules and module not in modules:
                continue
            if module == "hanzi":
                # 汉字条目是共享基础数据，学生在当前管理系统下默认可见。
                filtered_hits.append(hit)
                continue
            if module == "assignment" and str(source.get("course_id") or "") in course_ids:
                filtered_hits.append(hit)
                continue
            if module == "course" and str(source.get("source_id") or "") in course_ids:
                filtered_hits.append(hit)
                continue
            if module == "teaching_class" and str(source.get("source_id") or "") in class_ids:
                filtered_hits.append(hit)
                continue
            if module == "discussion" and str(source.get("course_id") or "") in course_ids:
                filtered_hits.append(hit)
        return filtered_hits

    def _normalize_requested_modules(self, modules: Optional[list[str]]) -> list[str] | None:
        """
        功能描述：
            处理requestedmodules。

        参数：
            modules (Optional[list[str]]): 列表结果。

        返回值：
            list[str] | None: 返回列表形式的结果数据。
        """
        available_modules = {config.module for config in self.module_configs.values()}
        if not modules:
            return None
        filtered_modules = [module for module in modules if module in available_modules]
        return filtered_modules or None

    @staticmethod
    def _build_document_id(table: str, source_id: str) -> str:
        """
        功能描述：
            构建document标识。

        参数：
            table (str): 字符串结果。
            source_id (str): sourceID。

        返回值：
            str: 返回str类型的处理结果。
        """
        return f"{table}_{source_id}"

    @staticmethod
    def _to_search_hit(hit: dict) -> SearchHit:
        """
        功能描述：
            将输入数据转换为检索hit。

        参数：
            hit (dict): 字典形式的结果数据。

        返回值：
            SearchHit: 返回SearchHit类型的处理结果。
        """
        source = hit["_source"]
        return SearchHit(
            module=source["module"],
            id=source["source_id"],
            score=float(hit.get("_score") or 0),
            title=source["title"],
            content=source["content"],
        )
