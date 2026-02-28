import asyncio
from datetime import datetime
import json

from app.core.celery_app import celery_app
from app.services.import_service import ImportService
from redis import Redis
from app.core.config import settings


@celery_app.task(bind=True, name="process_import_data")
def process_import_data(self, zip_file_path: str,
                        level_json_path: str = None,
                        comment_json_path: str = None,
                        output_dir: str = None):

    redis_client = Redis.from_url(settings.REDIS_URL)
    task_id = self.request.id
    task_log_key = f"task_logs:{task_id}"

    async def status_callback(progress: int, message: str):
        if redis_client:
            log_entry = {
                "progress": progress,
                "message": message,
                "timestamp": datetime.now().isoformat()
            }
            redis_client.rpush(task_log_key, json.dumps(log_entry))
            redis_client.expire(task_log_key, 86400)

            self.update_state(state="PROGRESS", meta={"progress": progress, "message": message})

    service = ImportService(output_dir=output_dir)

    try:
        result = asyncio.run(
            service.process_import_task(zip_file_path, level_json_path, comment_json_path, status_callback)
        )
        return result
    except Exception as e:
        if redis_client:
            redis_client.rpush(task_log_key, json.dumps({
                "progress": 0,
                "message": f"错误：{str(e)}",
                "status": "error"
            }))
        raise e
