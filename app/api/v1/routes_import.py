import asyncio
import json
import os
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from redis import Redis

from app.core.config import settings
from app.tasks.import_tasks import process_import_data
from app.utils.file_utils import save_upload_file


router = APIRouter()


def get_redis() -> Redis:
    return Redis.from_url(settings.REDIS_URL)


@router.post("/tasks")
async def create_import_task(
    image_zip: UploadFile = File(...),
    json_level: Optional[UploadFile] = File(None),
    json_comment: Optional[UploadFile] = File(None),
):
    if not image_zip.filename:
        raise HTTPException(status_code=400, detail="缺少图片 ZIP 文件")

    upload_dir = os.path.join(settings.MEDIA_ROOT, "uploads", "import")
    zip_path = await save_upload_file(image_zip, upload_dir)

    level_path = None
    comment_path = None
    if json_level and json_level.filename:
        level_path = await save_upload_file(json_level, upload_dir)
    if json_comment and json_comment.filename:
        comment_path = await save_upload_file(json_comment, upload_dir)

    output_dir = os.path.join(settings.MEDIA_ROOT, "import_results")
    task = process_import_data.delay(zip_path, level_path, comment_path, output_dir)
    return {"task_id": task.id}


@router.get("/tasks/{task_id}/logs")
async def get_import_logs(task_id: str):
    redis_client = get_redis()
    key = f"task_logs:{task_id}"
    raw_items = redis_client.lrange(key, 0, -1)
    logs = []
    for item in raw_items:
        try:
            logs.append(json.loads(item))
        except Exception:
            continue
    return {"task_id": task_id, "logs": logs}


@router.get("/tasks/{task_id}/events")
async def stream_import_logs(task_id: str):
    redis_client = get_redis()
    key = f"task_logs:{task_id}"

    async def event_generator():
        last_index = 0
        while True:
            length = redis_client.llen(key)
            if length > last_index:
                items = redis_client.lrange(key, last_index, length - 1)
                last_index = length
                for item in items:
                    yield f"data: {item.decode('utf-8')}\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
