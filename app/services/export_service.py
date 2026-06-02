import csv
import io
import json
import os
import shutil
import tempfile
import zipfile
from datetime import datetime
from typing import Optional

import pandas as pd
from sqlalchemy import func, select
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

    async def export_dataset_html(
        self,
        dataset_id: str,
        current_user_id: str,
        hanzi_ids: Optional[list[str]] = None,
        character: Optional[str] = None,
        pinyin: Optional[str] = None,
        stroke_pattern: Optional[str] = None,
        format: str = "html+csv",
    ) -> tuple[io.BytesIO, str]:
        """导出数据集，format="html+csv" 导出 index.html + data.csv，"csv" 仅导出 CSV。"""
        dataset = await self.dataset_repo.get(dataset_id, current_user_id)
        if not dataset:
            raise ValueError("数据集不存在")

        if hanzi_ids:
            items = await self._fetch_items_by_ids(hanzi_ids, current_user_id, dataset_id)
        else:
            items = await self.dataset_repo.list_items(
                dataset_id=dataset_id,
                created_by_user_id=current_user_id,
                skip=0, limit=100000,
                character=character,
                pinyin=pinyin,
                stroke_pattern=stroke_pattern,
            )

        if not items:
            raise ValueError("没有符合条件的记录可导出")

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        safe_name = dataset.name.replace("/", "_").replace("\\", "_")[:50]

        # CSV 永远生成，HTML 按格式决定
        want_html = "html" in format
        rows_html_parts: list[str] = []
        csv_lines: list[str] = ["图片URL,汉字,拼音,笔画,笔画模式,结构,字形,等级,来源,备注"]
        for item in items:
            img_url = (item.image_path or "").strip()
            char = item.character or ""
            pinyin = item.pinyin or ""
            stroke_count = str(item.stroke_count) if item.stroke_count else ""
            stroke_pattern = item.stroke_pattern or ""
            structure = getattr(item, "structure", "") or ""
            variant = getattr(item, "variant", "") or ""
            level = getattr(item, "level", "") or ""
            source = item.source or ""
            comment = getattr(item, "comment", "") or ""

            if want_html:
                img_cell = f'<img src="{img_url}" loading="lazy" onerror="this.alt=\'—\'" />' if img_url else "—"
                rows_html_parts.append(
                    f"<tr>"
                    f"<td>{img_cell}</td>"
                    f"<td class=\"char\">{char}</td>"
                    f"<td>{pinyin}</td>"
                    f"<td>{stroke_count}</td>"
                    f"<td>{stroke_pattern}</td>"
                    f"<td>{structure}</td>"
                    f"<td>{variant}</td>"
                    f"<td>{level}</td>"
                    f"<td>{source}</td>"
                    f"<td>{comment}</td>"
                    f"</tr>"
                )

            csv_lines.append(
                ",".join(
                    f'"{v}"'
                    for v in [
                        img_url, char, pinyin, stroke_count, stroke_pattern,
                        structure, variant, level, source, comment,
                    ]
                )
            )

        # 打包 ZIP
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("data.csv", "\n".join(csv_lines).encode("utf-8-sig"))
            if want_html:
                html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{dataset.name} - 数据集导出</title>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:"Microsoft YaHei","PingFang SC",sans-serif;color:#333;background:#fafafa;padding:24px}}
h1{{font-size:20px;margin-bottom:4px}}
.meta{{color:#999;font-size:13px;margin-bottom:20px}}
table{{border-collapse:collapse;width:100%;background:#fff;border-radius:6px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.06)}}
th{{background:#2d2d2d;color:#fff;font-weight:600;font-size:13px;padding:10px 12px;text-align:left;white-space:nowrap}}
td{{padding:8px 12px;border-bottom:1px solid #eee;font-size:14px;vertical-align:middle}}
tr:nth-child(even) td{{background:#f9f9f9}}
.char{{font-family:"Noto Serif SC",serif;font-size:22px;font-weight:600}}
img{{width:60px;height:60px;object-fit:contain;border-radius:4px;border:1px solid #e5e5e5;display:block}}
</style>
</head>
<body>
<h1>{dataset.name}</h1>
<p class="meta">导出时间：{datetime.now().strftime("%Y-%m-%d %H:%M")}　共 {len(items)} 条</p>
<table>
<thead><tr>
<th>图片</th><th>汉字</th><th>拼音</th><th>笔画</th><th>笔画模式</th>
<th>结构</th><th>字形</th><th>等级</th><th>来源</th><th>备注</th>
</tr></thead>
<tbody>
{chr(10).join(rows_html_parts)}
</tbody>
</table>
</body>
</html>"""
                zf.writestr("index.html", html.encode("utf-8"))
        zip_buf.seek(0)

        filename = f"{safe_name}_{timestamp}.zip"
        return zip_buf, filename

    async def _fetch_items_by_ids(
        self, hanzi_ids: list[str], current_user_id: str, dataset_id: str
    ) -> list:
        """按 ID 列表获取条目，验证归属权限。"""
        from app.models.hanzi import Hanzi
        from app.models.hanzi_dictionary import DatasetHanziRelation
        from sqlalchemy import or_

        if not hanzi_ids:
            return []
        result = await self.db.execute(
            select(Hanzi)
            .join(DatasetHanziRelation, DatasetHanziRelation.hanzi_id == Hanzi.id)
            .where(
                DatasetHanziRelation.dataset_id == dataset_id,
                Hanzi.id.in_(hanzi_ids),
                or_(Hanzi.created_by_user_id == current_user_id,
                    Hanzi.created_by_user_id.is_(None)),
            )
        )
        return result.scalars().all()



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

    async def export_assignments(
        self, teacher_id: str, course_id: str | None = None,
        status: str | None = None,
    ) -> dict:
        """导出作业列表 Excel。"""
        import pandas as pd
        from sqlalchemy import func
        from app.repositories.assignment_repo import AssignmentRepository
        from app.models.submission import Submission

        os.makedirs(self.output_dir, exist_ok=True)
        repo = AssignmentRepository(self.db)
        items = await repo.get_all(0, 100000, teacher_id, status, course_id, None)
        rows = []
        for a in items:
            sub_stats = await self.db.execute(
                select(func.count(), func.avg(Submission.score))
                .where(Submission.assignment_id == a.id)
            )
            count, avg_score = sub_stats.first()
            rows.append({
                "标题": a.title, "状态": a.status,
                "截止时间": a.due_date.strftime("%Y-%m-%d %H:%M") if a.due_date else "",
                "提交人数": count or 0,
                "平均分": round(float(avg_score), 1) if avg_score else "",
            })
        df = pd.DataFrame(rows)
        filename = f"assignments_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
        filepath = os.path.join(self.output_dir, filename)
        df.to_excel(filepath, index=False)
        return {"file_name": filename, "file_path": filepath,
                "file_url": f"/media/export_results/{filename}", "total": len(rows)}

    async def export_students(
        self, teacher_id: str, course_id: str | None = None,
        class_id: str | None = None,
    ) -> dict:
        """导出学生列表 Excel。"""
        import pandas as pd
        from app.repositories.student_repo import StudentRepository
        from app.models.submission import Submission

        os.makedirs(self.output_dir, exist_ok=True)
        student_repo = StudentRepository(self.db)
        students = await student_repo.get_all(0, 100000, teacher_id=teacher_id)
        rows = []
        for s in students:
            sub_stats = await self.db.execute(
                select(func.count(), func.avg(Submission.score))
                .where(Submission.student_id == s.id)
            )
            count, avg_score = sub_stats.first()
            rows.append({
                "姓名": s.name, "班级": s.class_name or "",
                "提交次数": count or 0,
                "平均分": round(float(avg_score), 1) if avg_score else "",
            })
        df = pd.DataFrame(rows)
        filename = f"students_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
        filepath = os.path.join(self.output_dir, filename)
        df.to_excel(filepath, index=False)
        return {"file_name": filename, "file_path": filepath,
                "file_url": f"/media/export_results/{filename}", "total": len(rows)}

    async def export_submissions(
        self, assignment_id: str, student_id: str | None = None,
        status: str | None = None,
    ) -> dict:
        """导出提交记录 Excel。"""
        import pandas as pd
        from app.repositories.submission_repo import SubmissionRepository
        from app.repositories.assignment_repo import AssignmentRepository

        os.makedirs(self.output_dir, exist_ok=True)
        sub_repo = SubmissionRepository(self.db)
        items = await sub_repo.get_all_by_assignment(assignment_id, 0, 100000, student_id)
        assignment = await AssignmentRepository(self.db).get(assignment_id)
        rows = []
        for sub in items:
            if status and sub.status != status:
                continue
            rows.append({
                "学生": getattr(getattr(sub, "student", None), "name", ""),
                "作业": assignment.title if assignment else "",
                "得分": sub.score, "评语": sub.teacher_feedback or "",
                "提交时间": sub.submitted_at.strftime("%Y-%m-%d %H:%M") if sub.submitted_at else "",
                "状态": sub.status,
            })
        df = pd.DataFrame(rows)
        filename = f"submissions_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
        filepath = os.path.join(self.output_dir, filename)
        df.to_excel(filepath, index=False)
        return {"file_name": filename, "file_path": filepath,
                "file_url": f"/media/export_results/{filename}", "total": len(rows)}
