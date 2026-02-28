from typing import Any, Optional

from fastapi import APIRouter
from pydantic import BaseModel
import logging


logger = logging.getLogger("frontend")
router = APIRouter()


class FrontendLog(BaseModel):
    level: str = "info"
    message: str
    meta: Optional[dict[str, Any]] = None


@router.post("/")
async def report_log(body: FrontendLog):
    level = body.level.lower()
    if level == "error":
        logger.error(body.message, extra={"meta": body.meta})
    elif level == "warning":
        logger.warning(body.message, extra={"meta": body.meta})
    else:
        logger.info(body.message, extra={"meta": body.meta})
    return {"status": "ok"}
