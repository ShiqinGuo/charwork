from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.import_export import ExportRequest
from app.services.export_service import ExportService


router = APIRouter()


@router.post("/hanzi")
async def export_hanzi(req: ExportRequest, db: AsyncSession = Depends(get_db)):
    """
    功能描述：
        导出汉字。

    参数：
        req (ExportRequest): ExportRequest 类型的数据。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    service = ExportService(db)
    try:
        result = await service.export_hanzi_to_excel(
            fields=req.fields,
            structure=req.structure,
            level=req.level,
            variant=req.variant,
            search=req.search,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出失败：{str(e)}")
