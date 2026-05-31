"""
Celery 数据集导入任务。
"""

import logging

from app.core.celery_app import celery_app
from app.core.database import SyncSessionLocal
from app.services.dataset_import_service import run_dataset_import_sync

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=0)
def run_dataset_import(self, image_paths: list[str], metadata: dict, temp_dir: str):
    task_id = self.request.id
    try:
        return run_dataset_import_sync(
            image_paths=image_paths,
            temp_dir=temp_dir,
            metadata=metadata,
            task_id=task_id,
            db_session_factory=SyncSessionLocal,
        )
    except Exception as exc:
        logger.exception("dataset import failed task=%s", task_id)
        return {"status": "failed", "error": str(exc)}
