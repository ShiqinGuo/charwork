"""
数据集导入 API：提交任务 + 查询进度。
"""

import os
import shutil
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_teacher
from app.core.database import get_db
from app.models.teacher import Teacher
from app.services.dataset_import_service import get_import_progress
from app.tasks.dataset_import_tasks import run_dataset_import

router = APIRouter()

TEMP_ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..", "temp", "dataset_import")


@router.post("/submit")
async def submit_dataset_import(
    files: list[UploadFile] = File(...),
    dataset_name: str = Form(...),
    level: str = Form(""),
    batch_no: str = Form(""),
    teacher: Teacher = Depends(get_current_teacher),
):
    task_id = uuid.uuid4().hex[:12]
    temp_dir = os.path.join(TEMP_ROOT, task_id)
    os.makedirs(temp_dir, exist_ok=True)

    image_paths: list[str] = []
    for f in files:
        safe_name = f.filename or uuid.uuid4().hex[:8]
        file_path = os.path.join(temp_dir, safe_name)
        with open(file_path, "wb") as buf:
            content = await f.read()
            buf.write(content)
        image_paths.append(file_path)

    metadata = {
        "name": dataset_name,
        "level": level,
        "batch_no": batch_no,
        "user_id": teacher.user_id,
    }

    run_dataset_import.apply_async(
        args=[image_paths, metadata, temp_dir], task_id=task_id
    )

    return {"task_id": task_id, "total": len(image_paths)}


@router.get("/status/{task_id}")
async def get_import_status(task_id: str):
    progress = get_import_progress(task_id)
    if progress is None:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")
    return progress
