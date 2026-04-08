"""
Elasticsearch 异步客户端模块。

提供全局单例 ES 客户端，用于全文搜索、日志查询等功能。
"""

from elasticsearch import AsyncElasticsearch

from app.core.config import settings


_es_client: AsyncElasticsearch | None = None


def get_es_client() -> AsyncElasticsearch:
    """
    功能描述：
        获取全局 Elasticsearch 异步客户端单例。
        复用进程级客户端，避免每次调用重复握手和连接池初始化。

    参数：
        无。

    返回值：
        AsyncElasticsearch: Elasticsearch 异步客户端实例。
    """
    global _es_client
    if _es_client is None:
        # 复用进程级客户端，避免每次调用重复握手和连接池初始化。
        _es_client = AsyncElasticsearch(hosts=[settings.ELASTICSEARCH_URL])
    return _es_client
