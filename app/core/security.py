"""
安全与会话管理模块。

提供密码哈希/验证、基于 Redis 的会话令牌（Session Token）创建/读取/吊销等功能。
会话数据以 JSON 形式存储在 Redis 中，支持自动续期和 Lua 原子操作。
"""

import json
import secrets
from typing import Optional

from passlib.context import CryptContext
from pydantic import BaseModel, ValidationError
from redis.exceptions import RedisError

from app.core.config import settings
from app.core.redis_client import get_redis
from app.models.user import User


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SESSION_KEY_PREFIX = "auth:session:"  # Redis 会话键前缀
# 使用 Lua 保证“读取并续期”原子执行，避免并发请求下出现读到旧 TTL 的竞态。
SESSION_FETCH_AND_REFRESH_LUA = """
local value = redis.call("GET", KEYS[1])
if not value then
  return nil
end
redis.call("EXPIRE", KEYS[1], tonumber(ARGV[1]))
return value
"""


class SessionUser(BaseModel):
    """存储在 Redis 会话中的用户信息快照，用于免查库鉴权。"""
    id: str
    email: str
    username: str
    role: str
    is_active: bool


def _build_session_key(token: str) -> str:
    """
    功能描述：
        根据令牌拼接 Redis 会话存储键名。

    参数：
        token (str): 会话令牌字符串。

    返回值：
        str: 完整的 Redis 键名，形如 "auth:session:<token>"。
    """
    return f"{SESSION_KEY_PREFIX}{token}"


def _resolve_session_ttl_seconds(expires_minutes: Optional[int] = None) -> int:
    """
    功能描述：
        将过期分钟数转换为秒数，未指定时使用全局配置的 ACCESS_TOKEN_EXPIRE_MINUTES。

    参数：
        expires_minutes (Optional[int]): 自定义过期时间（分钟），为 None 时使用默认值。

    返回值：
        int: 会话过期时间（秒）。
    """
    return int((expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES) * 60)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    功能描述：
        验证明文密码与数据库中存储的 bcrypt 哈希值是否匹配。

    参数：
        plain_password (str): 用户输入的明文密码。
        hashed_password (str): 数据库中存储的哈希密码。

    返回值：
        bool: 匹配返回 True，否则 False。
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    功能描述：
        对明文密码进行 bcrypt 哈希处理，用于注册或修改密码时存储。

    参数：
        password (str): 明文密码。

    返回值：
        str: bcrypt 哈希后的密码字符串。
    """
    return pwd_context.hash(password)


def build_session_user(user: User | SessionUser) -> SessionUser:
    """
    功能描述：
        将 ORM User 对象或已有 SessionUser 统一转换为 SessionUser 实例，
        用于写入 Redis 会话。

    参数：
        user (User | SessionUser): 数据库用户实体或已有的会话用户对象。

    返回值：
        SessionUser: 会话用户信息。
    """
    if isinstance(user, SessionUser):
        return user
    return SessionUser(
        id=user.id,
        email=user.email,
        username=user.username,
        role=str(user.role),
        is_active=bool(user.is_active),
    )


async def create_access_token(user: User | SessionUser, expires_minutes: Optional[int] = None) -> str:
    """
    功能描述：
        为用户创建会话令牌并写入 Redis，返回令牌字符串。
        使用 secrets.token_urlsafe 生成随机令牌，通过 NX 标志防止碰撞。

    参数：
        user (User | SessionUser): 需要创建会话的用户对象。
        expires_minutes (Optional[int]): 自定义会话过期时间（分钟），为 None 时使用默认值。

    返回值：
        str: 生成的会话令牌字符串。

    异常：
        RuntimeError: 多次重试仍无法生成唯一令牌时抛出。
    """
    redis = get_redis()
    session_user = build_session_user(user)
    ttl_seconds = _resolve_session_ttl_seconds(expires_minutes)
    payload = json.dumps(session_user.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":"))
    # 极端情况下 token 可能碰撞，限定重试次数避免无界循环阻塞登录链路。
    for _ in range(3):
        token = secrets.token_urlsafe(32)
        stored = await redis.set(_build_session_key(token), payload, ex=ttl_seconds, nx=True)
        if stored:
            return token
    raise RuntimeError("生成会话令牌失败")


async def get_session_user(token: str, extend_expire: bool = True) -> SessionUser | None:
    """
    功能描述：
        根据令牌从 Redis 读取会话用户信息。
        当 extend_expire 为 True 时使用 Lua 脚本原子地读取并续期。

    参数：
        token (str): 会话令牌字符串。
        extend_expire (bool): 是否在读取时自动续期会话 TTL，默认 True。

    返回值：
        SessionUser | None: 会话用户信息；令牌无效或已过期时返回 None。
    """
    redis = get_redis()
    key = _build_session_key(token)
    try:
        if extend_expire:
            payload = await redis.eval(
                SESSION_FETCH_AND_REFRESH_LUA,
                1,
                key,
                _resolve_session_ttl_seconds(),
            )
        else:
            payload = await redis.get(key)
    except RedisError:
        raise
    if not payload:
        return None
    try:
        return SessionUser.model_validate_json(payload)
    except ValidationError:
        # 会话结构不合法时立即删除脏数据，避免后续请求反复命中同一坏键。
        await redis.delete(key)
        return None


async def revoke_access_token(token: str) -> None:
    """
    功能描述：
        吊销（删除）指定的会话令牌，用于用户登出场景。

    参数：
        token (str): 要吊销的会话令牌字符串。

    返回值：
        None: 无返回值。
    """
    redis = get_redis()
    await redis.delete(_build_session_key(token))
