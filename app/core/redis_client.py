"""
Redis 异步客户端模块。

提供全局单例 Redis 客户端，用于会话存储、缓存等功能。
"""

from redis.asyncio import Redis

from app.core.config import settings


_redis: Redis | None = None


def get_redis() -> Redis:
    """
    功能描述：
        获取全局 Redis 异步客户端单例。
        decode_responses=True 统一返回字符串，避免上层在 bytes/str 之间反复转换。

    参数：
        无。

    返回值：
        Redis: Redis 异步客户端实例。
    """
    global _redis
    if _redis is None:
        # decode_responses=True 统一返回字符串，避免上层在 bytes/str 之间反复转换。
        _redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis
