from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

# 创建异步引擎
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.SQL_ECHO,
    # 长连接场景下主动探活，避免取到被数据库侧回收的失效连接。
    pool_pre_ping=True,
    # 与常见 MySQL wait_timeout 保持安全间隔，降低“服务器已断开连接”错误。
    pool_recycle=3600,
)

# 创建会话工厂
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    # 提交后保留对象状态，避免业务层在同一请求中二次访问触发额外刷新。
    expire_on_commit=False,
    autoflush=False,
)


# 数据模型基类
class Base(DeclarativeBase):
    pass


# 接口框架依赖注入：获取数据库会话
async def get_db():
    """
    功能描述：
        按条件获取数据库。

    参数：
        无。

    返回值：
        None: 无返回值。
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
