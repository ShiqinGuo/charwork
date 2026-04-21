"""
为什么这样做：跨模块检索统一落 ES 全局索引，屏蔽各业务表差异，提供一致检索入口。
特殊逻辑：索引只做召回，最终可见性按当前用户角色与业务归属二次过滤。
"""

import logging
from typing import Optional

from elasticsearch import NotFoundError
from sqlalchemy.ext.asyncio import AsyncSession

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
        self.db = db
        self.es = get_es_client()
        self.index_name = f"{settings.ELASTICSEARCH_INDEX_PREFIX}_global_search"
        self.module_configs = get_enabled_search_module_configs()

    async def ensure_index(self) -> None:
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
                        "title": {"type": "text", "analyzer": "charwork_ngram_analyzer"},
                        "content": {"type": "text", "analyzer": "charwork_ngram_analyzer"},
                    }
                },
            },
        )

    async def ensure_index_with_bootstrap(self) -> ReindexResponse:
        await self.ensure_index()
        return await self.reindex()

    async def _upsert_document(self, doc_id: str, document: SearchDocument) -> None:
        payload = {
            "module": document.module,
            "source_id": document.source_id,
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
        try:
            await self.es.delete(index=self.index_name, id=doc_id, refresh=False)
        except NotFoundError:
            return

    async def reindex(self) -> ReindexResponse:
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
        modules: Optional[list[str]] = None,
        limit: int = 20,
    ) -> CrossSearchResponse:
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
        filter_query: list[dict] = []
        if allowed_modules:
            filter_query.append({"terms": {"module": allowed_modules}})
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
            modules=allowed_modules,
        )
        items = [self._to_search_hit(hit) for hit in hits[:limit]]
        return CrossSearchResponse(keyword=keyword, total=len(items), items=items)

    async def _filter_hits_by_permissions(
        self,
        hits: list[dict],
        current_user: SessionUser,
        modules: list[str] | None,
    ) -> list[dict]:
        if current_user.role == UserRole.ADMIN:
            return self._filter_by_modules(hits, modules)
        if current_user.role == UserRole.TEACHER:
            return self._filter_teacher_hits(hits, current_user.id, modules)
        student = await StudentRepository(self.db).get_by_user_id(current_user.id)
        if not student:
            return []
        course_ids = set(await CourseRepository(self.db).list_ids_for_student(student.id))
        class_ids = set(await TeachingClassRepository(self.db).list_ids_for_student(student.id))
        filtered_hits: list[dict] = []
        for hit in hits:
            source = hit.get("_source", {})
            module = str(source.get("module") or "")
            if modules and module not in modules:
                continue
            if module == "student" and str(source.get("student_user_id") or "") == current_user.id:
                filtered_hits.append(hit)
                continue
            if module == "hanzi" and not source.get("created_by_user_id"):
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

    @staticmethod
    def _filter_by_modules(hits: list[dict], modules: list[str] | None) -> list[dict]:
        if not modules:
            return hits
        return [hit for hit in hits if hit.get("_source", {}).get("module") in modules]

    def _filter_teacher_hits(
        self,
        hits: list[dict],
        teacher_user_id: str,
        modules: list[str] | None,
    ) -> list[dict]:
        filtered_hits: list[dict] = []
        for hit in self._filter_by_modules(hits, modules):
            source = hit.get("_source", {})
            module = str(source.get("module") or "")
            if module in {"assignment", "course", "teaching_class", "discussion"}:
                if str(source.get("teacher_user_id") or "") == teacher_user_id:
                    filtered_hits.append(hit)
                continue
            if module == "student":
                teacher_user_ids = source.get("teacher_user_ids") or []
                if teacher_user_id in teacher_user_ids:
                    filtered_hits.append(hit)
                continue
            if module == "hanzi":
                created_by_user_id = source.get("created_by_user_id")
                if created_by_user_id in {None, "", teacher_user_id}:
                    filtered_hits.append(hit)
        return filtered_hits

    def _normalize_requested_modules(self, modules: Optional[list[str]]) -> list[str] | None:
        available_modules = {config.module for config in self.module_configs.values()}
        if not modules:
            return None
        filtered_modules = [module for module in modules if module in available_modules]
        return filtered_modules or None

    @staticmethod
    def _build_document_id(table: str, source_id: str) -> str:
        return f"{table}_{source_id}"

    def _to_search_hit(self, hit: dict) -> SearchHit:
        source = hit["_source"]
        target_type = str(source.get("target_type") or source["module"])
        return SearchHit(
            module=source["module"],
            id=source["source_id"],
            score=float(hit.get("_score") or 0),
            title=source["title"],
            content=source["content"],
            target_type=target_type,
            url=self._build_hit_url(source["module"], source["source_id"]),
        )

    @staticmethod
    def _build_hit_url(module: str, source_id: str) -> str | None:
        module_to_path = {
            "hanzi": f"/management-systems/default/modules/hanzi/{source_id}",
            "assignment": f"/management-systems/default/modules/assignments/{source_id}",
            "student": f"/management-systems/default/modules/students/{source_id}",
            "course": f"/courses/{source_id}",
            "teaching_class": "/classes",
            "discussion": "/messages",
        }
        return module_to_path.get(module)
