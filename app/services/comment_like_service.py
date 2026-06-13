"""
为什么这样做：点赞采用 Redis Lua 保证单 key 原子切换，降低并发下重复点赞与反复取消的竞态。
特殊逻辑：数据库唯一约束冲突只回滚当前写入，保持接口幂等语义与计数边界不被破坏。
"""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_client import get_redis
from app.repositories.comment_like_repo import CommentLikeRepository
from app.repositories.comment_repo import CommentRepository
from app.schemas.comment import CommentLikeRequest, CommentLikeResponse, LikeAction


LIKE_LUA = """
if ARGV[1] == "like" then
  if redis.call("EXISTS", KEYS[1]) == 1 then
    return 0
  end
  redis.call("SET", KEYS[1], "1")
  return 1
else
  if redis.call("EXISTS", KEYS[1]) == 1 then
    redis.call("DEL", KEYS[1])
    return 1
  end
  return 0
end
"""


class CommentLikeService:
    def __init__(self, db: AsyncSession):
        """
        功能描述：
            初始化CommentLikeService并准备运行所需的依赖对象。

        参数：
            db (AsyncSession): 数据库会话，用于执行持久化操作。

        返回值：
            None: 无返回值。
        """
        self.db = db
        self.like_repo = CommentLikeRepository(db)
        self.comment_repo = CommentRepository(db)
        self.redis = get_redis()

    async def operate_like(self, comment_id: str, body: CommentLikeRequest) -> CommentLikeResponse:
        """
        功能描述：
            处理点赞。

        参数：
            comment_id (str): 评论ID。
            body (CommentLikeRequest): 接口请求体对象。

        返回值：
            CommentLikeResponse: 返回CommentLikeResponse类型的处理结果。
        """
        comment = await self.comment_repo.get(comment_id)
        if not comment:
            raise ValueError("评论不存在")
        action = body.action.value
        key = f"comment:like:{comment_id}:{body.user_id}"
        changed = await self.redis.eval(LIKE_LUA, 1, key, action)
        if action == LikeAction.LIKE.value:
            if changed == 1:
                await self.like_repo.create(comment_id, body.user_id)
                comment.like_count = comment.like_count + 1
                try:
                    await self.db.commit()
                except IntegrityError:
                    await self.db.rollback()
            liked = True
            return CommentLikeResponse(
                comment_id=comment_id,
                user_id=body.user_id,
                action=body.action,
                liked=liked,
            )
        if changed == 1:
            await self.like_repo.delete(comment_id, body.user_id)
            comment.like_count = max(comment.like_count - 1, 0)
            await self.db.commit()
        return CommentLikeResponse(
            comment_id=comment_id,
            user_id=body.user_id,
            action=body.action,
            liked=False,
        )
