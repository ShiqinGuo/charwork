"""
Redis 缓存工具模块。

提供通用的 JSON 缓存读写、删除和批量失效能力。
所有函数均无状态，Redis 实例由调用方通过 get_redis() 传入。
Redis 不可用时自动降级：cache_get 返回 None，cache_set/cache_delete 静默失败。
"""

import json
import logging
from typing import Any, Optional

from redis.asyncio import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

# 缓存 TTL 配置（秒），按业务域分类
CACHE_TTL_SHORT = 300        # 5 分钟 — 高频变更数据
CACHE_TTL_MEDIUM = 1800      # 30 分钟 — 用户 profile、管理系统 ID
CACHE_TTL_LONG = 3600        # 1 小时 — AI 短期记忆等
CACHE_TTL_STATIC = 86400     # 24 小时 — 字典等静态参考数据

_KEY_SEP = ":"


def build_cache_key(*parts: str) -> str:
    """拼接缓存 key，各段之间用 ":" 连接。"""
    return _KEY_SEP.join(parts)


async def cache_get(redis: Redis, key: str) -> Optional[Any]:
    """
    从 Redis 读取并 JSON 反序列化。

    key 不存在、JSON 解析失败或 Redis 不可用时均返回 None（降级为无缓存）。
    """
    try:
        raw = await redis.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except (RedisError, json.JSONDecodeError) as exc:
        logger.warning("cache_get 失败 key=%s: %s", key, exc)
        return None


async def cache_set(
    redis: Redis,
    key: str,
    value: Any,
    ttl: int = CACHE_TTL_MEDIUM,
) -> None:
    """
    JSON 序列化后写入 Redis，附带 TTL。

    Redis 不可用时静默失败，不影响主流程。
    """
    try:
        payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        await redis.set(key, payload, ex=ttl)
    except (RedisError, TypeError) as exc:
        logger.warning("cache_set 失败 key=%s: %s", key, exc)


async def cache_delete(redis: Redis, key: str) -> None:
    """
    删除单个缓存 key。

    Redis 不可用时静默失败。
    """
    try:
        await redis.delete(key)
    except RedisError as exc:
        logger.warning("cache_delete 失败 key=%s: %s", key, exc)


async def cache_delete_pattern(redis: Redis, pattern: str) -> int:
    """
    按 glob 模式批量失效缓存，使用 SCAN 避免阻塞主线程。

    返回实际删除的 key 数量。
    示例 pattern: "ms:list:user123:*"
    """
    deleted = 0
    try:
        keys_to_delete: list[str] = []
        async for key in redis.scan_iter(match=pattern, count=100):
            keys_to_delete.append(key)
        if keys_to_delete:
            async with redis.pipeline(transaction=False) as pipe:
                for key in keys_to_delete:
                    pipe.delete(key)
                results = await pipe.execute()
            deleted = sum(results)
    except RedisError as exc:
        logger.warning("cache_delete_pattern 失败 pattern=%s: %s", pattern, exc)
    return deleted
