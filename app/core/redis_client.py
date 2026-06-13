"""
Redis 客户端模块。提供全局异步和同步单例。
"""

import redis as sync_redis
from redis.asyncio import Redis

from app.core.config import settings

_async_redis: Redis | None = None
_sync_redis: sync_redis.Redis | None = None


def get_redis() -> Redis:
    """获取全局 Redis 异步客户端。"""
    global _async_redis
    if _async_redis is None:
        _async_redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _async_redis


def get_sync_redis() -> sync_redis.Redis:
    """获取全局 Redis 同步客户端（Celery tasks 使用）。"""
    global _sync_redis
    if _sync_redis is None:
        _sync_redis = sync_redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _sync_redis
