from elasticsearch import AsyncElasticsearch

from app.core.config import settings


_es_client: AsyncElasticsearch | None = None


def get_es_client() -> AsyncElasticsearch:
    """
    功能描述：
        按条件获取esclient。

    参数：
        无。

    返回值：
        AsyncElasticsearch: 返回查询到的结果对象。
    """
    global _es_client
    if _es_client is None:
        # 复用进程级客户端，避免每次调用重复握手和连接池初始化。
        _es_client = AsyncElasticsearch(hosts=[settings.ELASTICSEARCH_URL])
    return _es_client
