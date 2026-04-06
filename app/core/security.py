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
SESSION_KEY_PREFIX = "auth:session:"
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
    id: str
    email: str
    username: str
    role: str
    is_active: bool


def _build_session_key(token: str) -> str:
    """
    功能描述：
        构建sessionkey。

    参数：
        token (str): 令牌字符串。

    返回值：
        str: 返回str类型的处理结果。
    """
    return f"{SESSION_KEY_PREFIX}{token}"


def _resolve_session_ttl_seconds(expires_minutes: Optional[int] = None) -> int:
    """
    功能描述：
        解析sessionttlseconds。

    参数：
        expires_minutes (Optional[int]): 整数结果。

    返回值：
        int: 返回int类型的处理结果。
    """
    return int((expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES) * 60)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    功能描述：
        处理密码。

    参数：
        plain_password (str): 字符串结果。
        hashed_password (str): 字符串结果。

    返回值：
        bool: 返回操作是否成功。
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    功能描述：
        按条件获取密码hash。

    参数：
        password (str): 字符串结果。

    返回值：
        str: 返回查询到的结果对象。
    """
    return pwd_context.hash(password)


def build_session_user(user: User | SessionUser) -> SessionUser:
    """
    功能描述：
        构建session用户。

    参数：
        user (User | SessionUser): User | SessionUser 类型的数据。

    返回值：
        SessionUser: 返回构建后的结果对象。
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
        创建access令牌并返回结果。

    参数：
        user (User | SessionUser): User | SessionUser 类型的数据。
        expires_minutes (Optional[int]): 整数结果。

    返回值：
        str: 返回创建后的结果对象。
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
        按条件获取session用户。

    参数：
        token (str): 令牌字符串。
        extend_expire (bool): 布尔值结果。

    返回值：
        SessionUser | None: 返回查询到的结果对象；未命中时返回 None。
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
        处理access令牌。

    参数：
        token (str): 令牌字符串。

    返回值：
        None: 无返回值。
    """
    redis = get_redis()
    await redis.delete(_build_session_key(token))
