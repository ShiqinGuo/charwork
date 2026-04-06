from redis.asyncio import Redis

from app.core.config import settings


_redis: Redis | None = None


def get_redis() -> Redis:
    """
    功能描述：
        按条件获取Redis。

    参数：
        无。

    返回值：
        Redis: 返回查询到的结果对象。
    """
    global _redis
    if _redis is None:
        # decode_responses=True 统一返回字符串，避免上层在 bytes/str 之间反复转换。
        _redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis
