import os
import uuid
from fastapi import UploadFile


def ensure_dir(path: str) -> None:
    """
    功能描述：
        确保dir存在，必要时自动补齐。

    参数：
        path (str): 文件或资源路径。

    返回值：
        None: 无返回值。
    """
    os.makedirs(path, exist_ok=True)


async def save_upload_file(upload_file: UploadFile, target_dir: str) -> str:
    """
    功能描述：
        保存上传文件。

    参数：
        upload_file (UploadFile): 文件对象或文件标识。
        target_dir (str): 字符串结果。

    返回值：
        str: 返回str类型的处理结果。
    """
    ensure_dir(target_dir)
    suffix = os.path.splitext(upload_file.filename or "")[1]
    file_name = f"{uuid.uuid4().hex}{suffix}"
    file_path = os.path.join(target_dir, file_name)
    content = await upload_file.read()
    with open(file_path, "wb") as f:
        f.write(content)
    return file_path
