"""ImageX URL 刷新 Celery 定时任务。"""

import logging

from app.core.celery_app import celery_app
from app.services.ocr_service import OCRService
from app.services.url_refresh_service import UrlRefreshService

logger = logging.getLogger(__name__)


@celery_app.task(name="refresh_imagex_urls")
def refresh_imagex_urls() -> dict:
    """定时刷新所有表中即将过期的 ImageX 签名 URL。"""
    logger.info("开始执行 ImageX URL 刷新任务")
    ocr = OCRService()
    service = UrlRefreshService(ocr.imagex_service)
    result = service.refresh_all()
    logger.info("ImageX URL 刷新任务完成: %s", result)
    return {"status": "ok", "refreshed": result}
