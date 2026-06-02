"""
Celery 异步任务队列配置模块。

基于 RabbitMQ 作为消息代理和结果后端，统一使用 JSON 序列化格式，
确保不同语言/服务端消费任务结果时协议一致。
"""

from datetime import timedelta

from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.REDIS_URL,
)

# 统一使用 JSON 序列化，保证不同语言/服务端消费任务结果时协议一致。
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
)

# ImageX URL 定时刷新 Beat 调度（仅在配置启用时注册）
if settings.URL_REFRESH_ENABLED:
    interval = settings.URL_REFRESH_INTERVAL_MINUTES
    celery_app.conf.beat_schedule = {
        "refresh-imagex-urls": {
            "task": "refresh_imagex_urls",
            "schedule": timedelta(minutes=interval),
            # 过期时间略小于间隔，防止任务堆积
            "options": {"expires": max(60, interval * 60 - 30)},
        },
    }

# 自动发现 app.tasks 包，并通过其聚合导入完成任务注册。
celery_app.autodiscover_tasks(packages=["app.tasks"], related_name=None, force=True)
