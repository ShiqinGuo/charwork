import os
from datetime import datetime
from io import BytesIO
from typing import Any, Optional

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.management_system_record import ManagementSystemRecord
from app.models.user import User
from app.repositories.management_system_record_repo import ManagementSystemRecordRepository
from app.schemas.management_system import (
    ManagementSystemExportRequest,
    ManagementSystemImportError,
    ManagementSystemImportResponse,
    ManagementSystemRecordCreate,
    ManagementSystemRecordListResponse,
    ManagementSystemRecordResponse,
    ManagementSystemRecordUpdate,
)
from app.services.management_system_service import ManagementSystemService, normalize_management_system_config


class ManagementSystemRecordService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = ManagementSystemRecordRepository(db)
        self.management_system_service = ManagementSystemService(db)
        self.output_dir = os.path.join(settings.MEDIA_ROOT, "export_results")

    async def list_records(
        self,
        management_system_id: str,
        current_user: User,
        skip: int,
        limit: int,
        keyword: Optional[str] = None,
    ) -> ManagementSystemRecordListResponse:
        await self._ensure_owned_system(management_system_id, current_user)
        items = await self.repo.list_by_system(management_system_id, current_user.id, skip, limit, keyword)
        total = await self.repo.count_by_system(management_system_id, current_user.id, keyword)
        return ManagementSystemRecordListResponse(
            total=total,
            items=[self._to_response(item) for item in items],
        )

    async def get_record(self, management_system_id: str, record_id: str,
                         current_user: User) -> Optional[ManagementSystemRecordResponse]:
        await self._ensure_owned_system(management_system_id, current_user)
        item = await self.repo.get(record_id, management_system_id, current_user.id)
        if not item:
            return None
        return self._to_response(item)

    async def create_record(
        self,
        management_system_id: str,
        body: ManagementSystemRecordCreate,
        current_user: User,
    ) -> ManagementSystemRecordResponse:
        system = await self._ensure_owned_system(management_system_id, current_user)
        normalized_data = self._normalize_record_data(system.config, body.data)
        record = ManagementSystemRecord(
            management_system_id=management_system_id,
            owner_user_id=current_user.id,
            title=body.title or self._build_record_title(normalized_data),
            data=normalized_data,
            remark=body.remark,
        )
        await self.repo.add(record)
        await self.repo.save()
        await self.db.refresh(record)
        return self._to_response(record)

    async def update_record(
        self,
        management_system_id: str,
        record_id: str,
        body: ManagementSystemRecordUpdate,
        current_user: User,
    ) -> Optional[ManagementSystemRecordResponse]:
        system = await self._ensure_owned_system(management_system_id, current_user)
        record = await self.repo.get(record_id, management_system_id, current_user.id)
        if not record:
            return None
        if body.data is not None:
            record.data = self._normalize_record_data(system.config, body.data)
        if body.title is not None:
            record.title = body.title
        elif body.data is not None:
            record.title = self._build_record_title(record.data)
        if body.remark is not None:
            record.remark = body.remark
        await self.repo.save()
        await self.db.refresh(record)
        return self._to_response(record)

    async def delete_record(self, management_system_id: str, record_id: str, current_user: User) -> bool:
        await self._ensure_owned_system(management_system_id, current_user)
        record = await self.repo.get(record_id, management_system_id, current_user.id)
        if not record:
            return False
        await self.repo.delete(record)
        await self.repo.save()
        return True

    async def export_template(self, management_system_id: str, current_user: User) -> BytesIO:
        system = await self._ensure_owned_system(management_system_id, current_user)
        config = normalize_management_system_config(system.config)
        field_definitions = [
            item for item in config.get("field_definitions", [])
            if item.get("enabled") and item.get("field_key") not in {"create_time", "update_time", "is_deleted"}
        ]
        columns = [item["name"] for item in field_definitions]
        mapping_row = {item["name"]: item["field_key"] for item in field_definitions}
        df = pd.DataFrame([mapping_row])
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="template")
            if columns:
                pd.DataFrame(columns=columns).to_excel(writer, index=False, sheet_name="data")
        buffer.seek(0)
        return buffer

    async def import_records(
        self,
        management_system_id: str,
        current_user: User,
        file_path: str,
    ) -> ManagementSystemImportResponse:
        system = await self._ensure_owned_system(management_system_id, current_user)
        config = normalize_management_system_config(system.config)
        field_definitions = [
            item for item in config.get("field_definitions", [])
            if item.get("enabled") and item.get("field_key") not in {"create_time", "update_time", "is_deleted"}
        ]
        field_map = {item["name"]: item for item in field_definitions}
        df = pd.read_excel(file_path, sheet_name="data")
        success_count = 0
        errors: list[ManagementSystemImportError] = []
        for index, row in df.iterrows():
            raw_data: dict[str, Any] = {}
            for display_name, field_definition in field_map.items():
                if display_name not in row.index:
                    continue
                raw_data[field_definition["field_key"]] = row[display_name]
            try:
                normalized = self._normalize_record_data(config, raw_data)
                record = ManagementSystemRecord(
                    management_system_id=management_system_id,
                    owner_user_id=current_user.id,
                    title=self._build_record_title(normalized),
                    data=normalized,
                )
                await self.repo.add(record)
                success_count += 1
            except ValueError as exc:
                errors.append(ManagementSystemImportError(row=index + 2, message=str(exc)))
        await self.repo.save()
        return ManagementSystemImportResponse(
            success_count=success_count,
            failure_count=len(errors),
            errors=errors,
        )

    async def export_records(
        self,
        management_system_id: str,
        current_user: User,
        body: ManagementSystemExportRequest,
    ) -> BytesIO:
        system = await self._ensure_owned_system(management_system_id, current_user)
        config = normalize_management_system_config(system.config)
        field_definitions = {
            item["field_key"]: item
            for item in config.get("field_definitions", [])
            if item.get("enabled")
        }
        selected_keys = [key for key in body.field_keys if key in field_definitions]
        if not selected_keys:
            selected_keys = list(config.get("list_config", {}).get("visible_field_keys", []))
        if not selected_keys:
            raise ValueError("请选择至少一个导出字段")
        items = await self.repo.list_by_system(management_system_id, current_user.id, 0, 100000, None)
        rows = []
        for item in items:
            row = {}
            for key in selected_keys:
                field_name = field_definitions[key]["name"]
                row[field_name] = item.data.get(key)
            rows.append(row)
        buffer = BytesIO()
        pd.DataFrame(rows).to_excel(buffer, index=False)
        buffer.seek(0)
        return buffer

    async def _ensure_owned_system(self, management_system_id: str, current_user: User):
        system = await self.management_system_service.get_system_detail(management_system_id, current_user)
        if not system:
            raise ValueError("管理系统不存在")
        if system.owner_user_id != current_user.id:
            raise PermissionError("仅可访问自己的管理系统")
        return system

    def _normalize_record_data(self, config: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
        normalized_config = normalize_management_system_config(config)
        field_definitions = [
            item for item in normalized_config.get("field_definitions", [])
            if item.get("enabled")
        ]
        result: dict[str, Any] = {}
        for item in field_definitions:
            field_key = item["field_key"]
            if field_key in {"create_time", "update_time"}:
                result[field_key] = datetime.now().isoformat()
                continue
            if field_key == "is_deleted":
                result[field_key] = False
                continue
            raw_value = data.get(field_key)
            value = self._coerce_value(item["field_type"], raw_value)
            if item.get("is_required") and (value is None or value == ""):
                raise ValueError(f"字段 {item['name']} 为必填")
            result[field_key] = value
        return result

    @staticmethod
    def _coerce_value(field_type: str, value: Any) -> Any:
        if pd.isna(value):
            return None
        if field_type == "number":
            return float(value) if value not in (None, "") else None
        if field_type == "boolean":
            if isinstance(value, bool):
                return value
            return str(value).strip().lower() in {"1", "true", "yes", "是"}
        if field_type == "date":
            if isinstance(value, datetime):
                return value.isoformat()
            return str(value) if value not in (None, "") else None
        if field_type == "json":
            if isinstance(value, dict):
                return value
            return {"value": value} if value not in (None, "") else None
        return str(value) if value not in (None, "") else None

    @staticmethod
    def _build_record_title(data: dict[str, Any]) -> str:
        for key in ("title", "name", "character", "code"):
            value = data.get(key)
            if value:
                return str(value)
        return "未命名记录"

    @staticmethod
    def _to_response(item: ManagementSystemRecord) -> ManagementSystemRecordResponse:
        return ManagementSystemRecordResponse(
            id=item.id,
            management_system_id=item.management_system_id,
            owner_user_id=item.owner_user_id,
            title=item.title,
            data=item.data,
            remark=item.remark,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
