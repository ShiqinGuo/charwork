import os
import uuid
from fastapi import UploadFile


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


async def save_upload_file(upload_file: UploadFile, target_dir: str) -> str:
    ensure_dir(target_dir)
    suffix = os.path.splitext(upload_file.filename or "")[1]
    file_name = f"{uuid.uuid4().hex}{suffix}"
    file_path = os.path.join(target_dir, file_name)
    content = await upload_file.read()
    with open(file_path, "wb") as f:
        f.write(content)
    return file_path
