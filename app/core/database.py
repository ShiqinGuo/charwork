"""
数据库引擎与会话管理模块。

基于 SQLAlchemy 异步引擎（AsyncEngine）创建全局连接池和会话工厂，
并提供 FastAPI 依赖注入用的 get_db 生成器。
"""

import sys

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool
from app.core.config import settings

ENGINE_OPTIONS = {
    "echo": settings.SQL_ECHO,
}

if sys.platform == "win32" and settings.ENVIRONMENT == "dev":
    # Windows 下 Celery 任务通过 asyncio.run 创建临时事件循环时，
    # aiomysql 连接池可能在回收旧连接时命中已关闭的 loop。
    ENGINE_OPTIONS["poolclass"] = NullPool
else:
    # 长连接场景下主动探活，避免取到被数据库侧回收的失效连接。
    ENGINE_OPTIONS["pool_pre_ping"] = True
    # 与常见 MySQL wait_timeout 保持安全间隔，降低“服务器已断开连接”错误。
    ENGINE_OPTIONS["pool_recycle"] = 3600

# 创建异步引擎
engine = create_async_engine(
    settings.DATABASE_URL,
    **ENGINE_OPTIONS,
)

# 创建会话工厂
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    # 提交后保留对象状态，避免业务层在同一请求中二次访问触发额外刷新。
    expire_on_commit=False,
    autoflush=False,
)


# 数据模型基类（所有 ORM Model 需继承此类）
class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类，项目中所有数据模型的公共父类。"""
    pass


# 接口框架依赖注入：获取数据库会话
async def get_db():
    """
    功能描述：
        FastAPI 依赖注入入口，为每个请求提供一个独立的异步数据库会话。
        请求结束后自动关闭会话。

    参数：
        无。

    返回值：
        AsyncSession: 通过 yield 返回异步数据库会话实例。
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
