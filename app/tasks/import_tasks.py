import asyncio
import json
from datetime import datetime

from redis import Redis

from app.core.celery_app import celery_app
from app.core.config import settings
from app.services.import_service import ImportService


TASK_LOG_KEY_PREFIX = "task_logs"
TASK_LOG_TTL_SECONDS = 86400
TASK_PROGRESS_STATE = "PROGRESS"
TASK_ERROR_STATUS = "error"
TASK_ERROR_MESSAGE_PREFIX = "错误："


def _build_task_log_key(task_id: str) -> str:
    """
    功能描述：
        构建任务日志key。

    参数：
        task_id (str): 任务ID。

    返回值：
        str: 返回str类型的处理结果。
    """
    return f"{TASK_LOG_KEY_PREFIX}:{task_id}"


def _build_log_entry(progress: int, message: str, status: str | None = None) -> dict[str, str | int]:
    """
    功能描述：
        构建日志条目。

    参数：
        progress (int): 整数结果。
        message (str): 字符串结果。
        status (str | None): 状态筛选条件或目标状态。

    返回值：
        dict[str, str | int]: 返回字典形式的结果数据。
    """
    log_entry: dict[str, str | int] = {
        "progress": progress,
        "message": message,
        "timestamp": datetime.now().isoformat(),
    }
    if status:
        log_entry["status"] = status
    return log_entry


def _append_task_log(redis_client: Redis | None, task_log_key: str, log_entry: dict[str, str | int]) -> None:
    """
    功能描述：
        处理任务日志。

    参数：
        redis_client (Redis | None): Redis | None 类型的数据。
        task_log_key (str): 字符串结果。
        log_entry (dict[str, str | int]): 字典形式的结果数据。

    返回值：
        None: 无返回值。
    """
    if not redis_client:
        return
    redis_client.rpush(task_log_key, json.dumps(log_entry))
    # 每次写入都续期，确保长任务持续产生日志时不会被中途清理。
    redis_client.expire(task_log_key, TASK_LOG_TTL_SECONDS)


@celery_app.task(bind=True, name="process_import_data")
def process_import_data(
    self,
    zip_file_path: str,
    level_json_path: str = None,
    comment_json_path: str = None,
    output_dir: str = None,
):
    """
    功能描述：
        处理导入数据。

    参数：
        zip_file_path (str): 文件或资源路径。
        level_json_path (str): 文件或资源路径。
        comment_json_path (str): 文件或资源路径。
        output_dir (str): 字符串结果。

    返回值：
        None: 无返回值。
    """
    redis_client = Redis.from_url(settings.REDIS_URL)
    task_id = self.request.id
    task_log_key = _build_task_log_key(task_id)

    async def status_callback(progress: int, message: str) -> None:
        """
        功能描述：
            处理callback。

        参数：
            progress (int): 整数结果。
            message (str): 字符串结果。

        返回值：
            None: 无返回值。
        """
        _append_task_log(redis_client, task_log_key, _build_log_entry(progress, message))
        self.update_state(state=TASK_PROGRESS_STATE, meta={"progress": progress, "message": message})

    service = ImportService(output_dir=output_dir)

    try:
        # Celery 任务函数是同步入口，这里显式托管异步流程，避免事件循环嵌套冲突。
        return asyncio.run(
            service.process_import_task(zip_file_path, level_json_path, comment_json_path, status_callback)
        )
    except Exception as exc:
        _append_task_log(
            redis_client,
            task_log_key,
            _build_log_entry(
                progress=0,
                message=f"{TASK_ERROR_MESSAGE_PREFIX}{exc}",
                status=TASK_ERROR_STATUS,
            ),
        )
        raise exc
