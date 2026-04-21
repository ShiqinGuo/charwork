import csv
import json
import os
import shutil
import tempfile
import zipfile
from datetime import datetime
from typing import Optional

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.repositories.hanzi_dictionary_repo import HanziDatasetRepository
from app.repositories.hanzi_repo import HanziRepository


class ExportService:
    def __init__(self, db: AsyncSession, output_dir: Optional[str] = None):
        self.db = db
        self.repo = HanziRepository(db)
        self.dataset_repo = HanziDatasetRepository(db)
        self.output_dir = output_dir or os.path.join(settings.MEDIA_ROOT, "export_results")

    async def export_hanzi_to_excel(
        self,
        fields: list[str],
        structure: Optional[str] = None,
        level: Optional[str] = None,
        variant: Optional[str] = None,
        search: Optional[str] = None,
        current_user_id: Optional[str] = None,
        character: Optional[str] = None,
        pinyin: Optional[str] = None,
        stroke_count: Optional[int] = None,
        stroke_pattern: Optional[str] = None,
        dataset_id: Optional[str] = None,
        source: Optional[str] = None,
    ) -> dict:
        os.makedirs(self.output_dir, exist_ok=True)
        allowed_fields = {
            "id",
            "dictionary_id",
            "character",
            "image_path",
            "stroke_count",
            "structure",
            "stroke_order",
            "stroke_pattern",
            "pinyin",
            "source",
            "level",
            "comment",
            "variant",
            "standard_image",
            "created_by_user_id",
            "created_at",
            "updated_at",
        }
        selected_fields = [field for field in fields if field in allowed_fields]
        if not selected_fields:
            raise ValueError("导出字段为空或不合法")
        items = await self.repo.get_all(
            skip=0,
            limit=100000,
            structure=structure,
            level=level,
            variant=variant,
            search=search,
            created_by_user_id=current_user_id,
            character=character,
            pinyin=pinyin,
            stroke_count=stroke_count,
            stroke_pattern=stroke_pattern,
            dataset_id=dataset_id,
            source=source,
        )
        rows = []
        for item in items:
            row = {}
            for field in selected_fields:
                value = getattr(item, field, None)
                if isinstance(value, datetime):
                    value = value.isoformat()
                row[field] = value
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

    async def export_dataset_package(self, dataset_id: str, current_user_id: str) -> dict:
        os.makedirs(self.output_dir, exist_ok=True)
        dataset = await self.dataset_repo.get(dataset_id, current_user_id)
        if not dataset:
            raise ValueError("数据集不存在")
        items = await self.repo.get_all(
            skip=0,
            limit=100000,
            created_by_user_id=current_user_id,
            dataset_id=dataset_id,
        )
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        zip_name = f"hanzi_dataset_{dataset.id}_{timestamp}.zip"
        zip_path = os.path.join(self.output_dir, zip_name)
        temp_dir = tempfile.mkdtemp(prefix=f"dataset_{dataset.id}_", dir=self.output_dir)
        images_dir = os.path.join(temp_dir, "images")
        os.makedirs(images_dir, exist_ok=True)
        manifest_rows = []
        try:
            for index, item in enumerate(items, start=1):
                packaged_image = self._copy_image_to_package(item.image_path, images_dir, index)
                manifest_rows.append(
                    {
                        "id": item.id,
                        "dictionary_id": item.dictionary_id,
                        "character": item.character,
                        "pinyin": item.pinyin,
                        "stroke_count": item.stroke_count,
                        "stroke_pattern": item.stroke_pattern,
                        "structure": item.structure,
                        "variant": item.variant,
                        "level": item.level,
                        "source": item.source,
                        "comment": item.comment,
                        "image_path": item.image_path,
                        "package_image_path": packaged_image,
                    }
                )
            manifest_json_path = os.path.join(temp_dir, "manifest.json")
            with open(manifest_json_path, "w", encoding="utf-8") as file:
                json.dump(manifest_rows, file, ensure_ascii=False, indent=2, default=str)
            manifest_csv_path = os.path.join(temp_dir, "manifest.csv")
            with open(manifest_csv_path, "w", encoding="utf-8-sig", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=list(manifest_rows[0].keys()) if manifest_rows else [
                    "id",
                    "dictionary_id",
                    "character",
                    "pinyin",
                    "stroke_count",
                    "stroke_pattern",
                    "structure",
                    "variant",
                    "level",
                    "source",
                    "comment",
                    "image_path",
                    "package_image_path",
                ])
                writer.writeheader()
                writer.writerows(manifest_rows)
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
                for root, _, files in os.walk(temp_dir):
                    for name in files:
                        file_path = os.path.join(root, name)
                        archive.write(file_path, os.path.relpath(file_path, temp_dir))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
        return {
            "file_name": zip_name,
            "file_path": zip_path,
            "file_url": f"/media/export_results/{zip_name}",
            "total": len(manifest_rows),
            "dataset_id": dataset.id,
            "dataset_name": dataset.name,
        }

    def _copy_image_to_package(self, image_path: Optional[str], images_dir: str, index: int) -> Optional[str]:
        resolved_path = self._resolve_image_path(image_path)
        if not resolved_path:
            return None
        _, ext = os.path.splitext(resolved_path)
        ext = ext or ".png"
        target_name = f"{index:04d}_{os.path.basename(resolved_path)}"
        if not target_name.endswith(ext):
            target_name = f"{target_name}{ext}"
        target_path = os.path.join(images_dir, target_name)
        shutil.copy2(resolved_path, target_path)
        return f"images/{target_name}"

    def _resolve_image_path(self, image_path: Optional[str]) -> Optional[str]:
        if not image_path:
            return None
        normalized = image_path.replace("\\", "/")
        candidates = [image_path]
        if normalized.startswith("/media/"):
            candidates.append(os.path.join(settings.MEDIA_ROOT, normalized.removeprefix("/media/").lstrip("/")))
        elif not os.path.isabs(image_path) and "://" not in normalized:
            candidates.append(os.path.join(settings.MEDIA_ROOT, normalized.lstrip("/")))
        for candidate in candidates:
            if candidate and os.path.isfile(candidate):
                return candidate
        return None
