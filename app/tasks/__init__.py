"""
Celery 任务聚合入口。

worker 启动时通过自动发现加载该包，并在导入阶段完成任务注册。
"""

from . import ai_feedback_tasks, import_tasks, notification_tasks

__all__ = ["ai_feedback_tasks", "import_tasks", "notification_tasks"]
