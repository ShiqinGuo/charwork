from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_teacher, get_current_user
from app.core.database import get_db
from app.core.security import SessionUser
from app.models.teacher import Teacher
from app.schemas.import_export import ExportRequest
from app.services.export_service import ExportService


router = APIRouter()


@router.post("/hanzi")
async def export_hanzi(
    req: ExportRequest,
    current_user: SessionUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
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
            character=req.character,
            pinyin=req.pinyin,
            stroke_count=req.stroke_count,
            stroke_pattern=req.stroke_pattern,
            dataset_id=req.dataset_id,
            source=req.source,
            structure=req.structure,
            level=req.level,
            variant=req.variant,
            search=req.search,
            current_user_id=current_user.id,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出失败：{str(e)}")


@router.post("/hanzi-datasets/{dataset_id}")
async def export_hanzi_dataset(
    dataset_id: str,
    current_user: SessionUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ExportService(db)
    try:
        return await service.export_dataset_package(dataset_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导出失败：{str(e)}")


@router.get("/assignments")
async def export_assignments(
    course_id: str | None = Query(None),
    status: str | None = Query(None),
    current_teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """导出作业列表 Excel"""
    result = await ExportService(db).export_assignments(
        teacher_id=current_teacher.id, course_id=course_id, status=status,
    )
    return FileResponse(
        result["file_path"],
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="assignments.xlsx"
        )


@router.get("/students")
async def export_students(
    course_id: str | None = Query(None),
    class_id: str | None = Query(None),
    current_teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """导出学生列表 Excel"""
    result = await ExportService(db).export_students(
        teacher_id=current_teacher.id, course_id=course_id, class_id=class_id,
    )
    return FileResponse(
        result["file_path"],
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="students.xlsx"
        )


@router.get("/submissions")
async def export_submissions(
    assignment_id: str = Query(...),
    student_id: str | None = Query(None),
    status: str | None = Query(None),
    current_teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    """导出提交记录 Excel"""
    result = await ExportService(db).export_submissions(
        assignment_id=assignment_id, student_id=student_id, status=status,
    )
    return FileResponse(
        result["file_path"],
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="submissions.xlsx"
        )
