"""
为什么这样做：全局 ThreadPoolExecutor 供各 service 复用，避免每次调用创建/销毁线程池的开销。
特殊逻辑：lazy init + max_workers 可配置，OCR/导入/导出等同步阻塞操作统一走此池。
"""

import os
from concurrent.futures import ThreadPoolExecutor

_upload_executor: ThreadPoolExecutor | None = None


def get_upload_executor(max_workers: int | None = None) -> ThreadPoolExecutor:
    global _upload_executor
    if _upload_executor is None:
        workers = max_workers or int(os.environ.get("UPLOAD_THREAD_POOL_SIZE", "20"))
        _upload_executor = ThreadPoolExecutor(max_workers=workers)
    return _upload_executor


def shutdown_executor() -> None:
    global _upload_executor
    if _upload_executor:
        _upload_executor.shutdown(wait=True)
        _upload_executor = None
