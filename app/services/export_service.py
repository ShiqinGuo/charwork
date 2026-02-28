import os
from datetime import datetime
from typing import Optional

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.repositories.hanzi_repo import HanziRepository


class ExportService:
    def __init__(self, db: AsyncSession, output_dir: Optional[str] = None):
        self.db = db
        self.repo = HanziRepository(db)
        self.output_dir = output_dir or os.path.join(settings.MEDIA_ROOT, "export_results")

    async def export_hanzi_to_excel(
        self,
        fields: list[str],
        structure: Optional[str] = None,
        level: Optional[str] = None,
        variant: Optional[str] = None,
        search: Optional[str] = None,
    ) -> dict:
        os.makedirs(self.output_dir, exist_ok=True)

        allowed_fields = {
            "id",
            "character",
            "image_path",
            "stroke_count",
            "structure",
            "stroke_order",
            "pinyin",
            "level",
            "comment",
            "variant",
            "standard_image",
            "created_at",
            "updated_at",
        }

        selected_fields = [f for f in fields if f in allowed_fields]
        if not selected_fields:
            raise ValueError("导出字段为空或不合法")

        items = await self.repo.get_all(0, 100000, structure, level, variant, search)

        rows = []
        for item in items:
            row = {}
            for f in selected_fields:
                value = getattr(item, f, None)
                if isinstance(value, (datetime, )):
                    value = value.isoformat()
                row[f] = value
            rows.append(row)

        df = pd.DataFrame(rows)
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        file_name = f"hanzi_export_{timestamp}.xlsx"
        file_path = os.path.join(self.output_dir, file_name)
        df.to_excel(file_path, index=False)

        return {
            "file_name": file_name,
            "file_path": file_path,
            "file_url": f"/media/export_results/{file_name}",
            "total": len(rows),
        }
