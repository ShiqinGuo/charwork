from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from elasticsearch import NotFoundError

from app.core.config import settings
from app.core.es_client import get_es_client
from app.models.assignment import Assignment
from app.models.comment import Comment
from app.models.hanzi import Hanzi
from app.models.student import Student
from app.schemas.search import CrossSearchResponse, SearchHit, ReindexResponse


class CrossSearchService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.es = get_es_client()
        self.index_name = f"{settings.ELASTICSEARCH_INDEX_PREFIX}_global_search"

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
                                "token_chars": ["letter", "digit", "ideographic"],
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
        count_response = await self.es.count(index=self.index_name)
        total = int(count_response.get("count", 0))
        if total > 0:
            return ReindexResponse(status="skipped", indexed=0)
        return await self.reindex()

    async def _upsert_document(self, doc_id: str, module: str, source_id: str, title: str, content: str) -> None:
        await self.es.index(
            index=self.index_name,
            id=doc_id,
            document={
                "module": module,
                "source_id": source_id,
                "title": title,
                "content": content,
            },
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
        hanzi_items = (await self.db.execute(select(Hanzi))).scalars().all()
        for item in hanzi_items:
            await self._upsert_document(
                doc_id=f"hanzi_{item.id}",
                module="hanzi",
                source_id=item.id,
                title=item.character,
                content=f"{item.character} {item.pinyin or ''} {item.comment or ''}",
            )
            indexed += 1
        assignment_items = (await self.db.execute(select(Assignment))).scalars().all()
        for item in assignment_items:
            await self._upsert_document(
                doc_id=f"assignment_{item.id}",
                module="assignment",
                source_id=item.id,
                title=item.title,
                content=f"{item.title} {item.description or ''}",
            )
            indexed += 1
        comment_items = (await self.db.execute(select(Comment))).scalars().all()
        for item in comment_items:
            await self._upsert_document(
                doc_id=f"comment_{item.id}",
                module="discussion",
                source_id=item.id,
                title=str(item.target_type),
                content=item.content,
            )
            indexed += 1
        student_items = (await self.db.execute(select(Student))).scalars().all()
        for item in student_items:
            await self._upsert_document(
                doc_id=f"student_{item.id}",
                module="student",
                source_id=item.id,
                title=item.name,
                content=f"{item.name} {item.class_name or ''}",
            )
            indexed += 1
        await self.es.indices.refresh(index=self.index_name)
        return ReindexResponse(status="success", indexed=indexed)

    async def apply_cdc_change(self, table: str, operation: str, data: dict) -> None:
        await self.ensure_index()
        operation = (operation or "").lower()
        source_id = data.get("id")
        if not source_id:
            return
        if table == "assignment":
            doc_id = f"assignment_{source_id}"
            if operation == "delete":
                await self._delete_document(doc_id)
            else:
                await self._upsert_document(
                    doc_id=doc_id,
                    module="assignment",
                    source_id=str(source_id),
                    title=str(data.get("title") or ""),
                    content=f"{data.get('title') or ''} {data.get('description') or ''}",
                )
        elif table == "comment":
            doc_id = f"comment_{source_id}"
            if operation == "delete":
                await self._delete_document(doc_id)
            else:
                await self._upsert_document(
                    doc_id=doc_id,
                    module="discussion",
                    source_id=str(source_id),
                    title=str(data.get("target_type") or ""),
                    content=str(data.get("content") or ""),
                )
        elif table == "hanzi":
            doc_id = f"hanzi_{source_id}"
            if operation == "delete":
                await self._delete_document(doc_id)
            else:
                await self._upsert_document(
                    doc_id=doc_id,
                    module="hanzi",
                    source_id=str(source_id),
                    title=str(data.get("character") or ""),
                    content=f"{data.get('character') or ''} {data.get('pinyin') or ''} {data.get('comment') or ''}",
                )
        elif table == "student":
            doc_id = f"student_{source_id}"
            if operation == "delete":
                await self._delete_document(doc_id)
            else:
                await self._upsert_document(
                    doc_id=doc_id,
                    module="student",
                    source_id=str(source_id),
                    title=str(data.get("name") or ""),
                    content=f"{data.get('name') or ''} {data.get('class_name') or ''}",
                )

    async def search(
        self,
        keyword: str,
        modules: Optional[list[str]] = None,
        limit: int = 20,
    ) -> CrossSearchResponse:
        await self.ensure_index()
        must = [
            {
                "multi_match": {
                    "query": keyword,
                    "fields": ["title^2", "content"],
                }
            }
        ]
        filter_query = []
        if modules:
            filter_query.append({"terms": {"module": modules}})
        response = await self.es.search(
            index=self.index_name,
            body={
                "query": {
                    "bool": {
                        "must": must,
                        "filter": filter_query,
                    }
                },
                "size": limit,
            },
        )
        hits = response.get("hits", {}).get("hits", [])
        items = [
            SearchHit(
                module=hit["_source"]["module"],
                id=hit["_source"]["source_id"],
                score=float(hit.get("_score") or 0),
                title=hit["_source"]["title"],
                content=hit["_source"]["content"],
            )
            for hit in hits
        ]
        return CrossSearchResponse(keyword=keyword, total=len(items), items=items)
