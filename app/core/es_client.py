from elasticsearch import AsyncElasticsearch

from app.core.config import settings


_es_client: AsyncElasticsearch | None = None


def get_es_client() -> AsyncElasticsearch:
    global _es_client
    if _es_client is None:
        _es_client = AsyncElasticsearch(hosts=[settings.ELASTICSEARCH_URL])
    return _es_client
