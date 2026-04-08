"""
Celery 异步任务队列配置模块。

基于 Redis 作为消息代理和结果后端，统一使用 JSON 序列化格式，
确保不同语言/服务端消费任务结果时协议一致。
"""

from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

# 统一使用 JSON 序列化，保证不同语言/服务端消费任务结果时协议一致。
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
)
