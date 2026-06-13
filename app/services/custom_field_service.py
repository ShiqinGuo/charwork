"""
为什么这样做：自定义字段是跨课程/作业/学生的通用能力，统一在服务层完成定义校验与值标准化。
特殊逻辑：目标存在性检查与字段类型归一化均用映射动态分派，减少硬编码分支并收敛边界错误。
"""

import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Awaitable, Callable, TypeAlias

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assignment import Assignment
from app.models.course import Course
from app.models.custom_field import ManagementSystemCustomField, ManagementSystemCustomFieldValue
from app.models.management_system import UserManagementSystem
from app.models.student import Student
from app.repositories.custom_field_repo import CustomFieldRepository
from app.schemas.custom_field import (
    ManagementSystemCustomFieldCreate,
    ManagementSystemCustomFieldSearchItem,
    ManagementSystemCustomFieldSearchResponse,
    ManagementSystemCustomFieldValueItem,
    ManagementSystemCustomFieldListResponse,
    ManagementSystemCustomFieldResponse,
    ManagementSystemCustomFieldValueListResponse,
    ManagementSystemCustomFieldValueResponse,
    ManagementSystemCustomFieldValueUpsertRequest,
)


FIELD_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,63}$")

FieldDefinition: TypeAlias = ManagementSystemCustomField | ManagementSystemCustomFieldCreate
TargetExistsChecker: TypeAlias = Callable[[str, str], Awaitable[bool]]
FieldValueNormalizer: TypeAlias = Callable[[FieldDefinition, Any], Any]

ASSIGNMENT_TARGET_TYPE = "assignment"
COURSE_TARGET_TYPE = "course"
STUDENT_TARGET_TYPE = "student"
TEXT_FIELD_TYPE = "text"
NUMBER_FIELD_TYPE = "number"
BOOLEAN_FIELD_TYPE = "boolean"
DATE_FIELD_TYPE = "date"
SELECT_FIELD_TYPE = "select"
JSON_FIELD_TYPE = "json"
FILE_FIELD_TYPE = "file"


@dataclass(slots=True)
class UpsertContext:
    fields: list[ManagementSystemCustomField]
    field_by_id: dict[str, ManagementSystemCustomField]
    existing_values: dict[str, ManagementSystemCustomFieldValue]


class CustomFieldService:
    def __init__(self, db: AsyncSession):
        """
        功能描述：
            初始化CustomFieldService并准备运行所需的依赖对象。

        参数：
            db (AsyncSession): 数据库会话，用于执行持久化操作。

        返回值：
            None: 无返回值。
        """
        self.repo = CustomFieldRepository(db)

    async def list_fields(
        self,
        management_system_id: str,
        target_type: str | None = None,
        viewer_role: str | None = None,
        searchable_only: bool = False,
    ) -> ManagementSystemCustomFieldListResponse:
        """
        功能描述：
            按条件查询字段列表。

        参数：
            management_system_id (str): 管理系统ID，用于限制数据作用域。
            target_type (str | None): 字符串结果。
            viewer_role (str | None): 角色信息。
            searchable_only (bool): 布尔值结果。

        返回值：
            ManagementSystemCustomFieldListResponse: 返回列表或分页查询结果。
        """
        items = await self.repo.list_fields(
            management_system_id,
            target_type,
            searchable_only=searchable_only,
        )
        filtered_items = self._filter_fields(items, viewer_role=viewer_role)
        return ManagementSystemCustomFieldListResponse(
            total=len(filtered_items),
            items=[ManagementSystemCustomFieldResponse.model_validate(item) for item in filtered_items],
        )

    async def create_field(
        self,
        management_system_id: str,
        current_user_id: str,
        body: ManagementSystemCustomFieldCreate,
    ) -> ManagementSystemCustomFieldResponse:
        """
        功能描述：
            创建字段并返回结果。

        参数：
            management_system_id (str): 管理系统ID，用于限制数据作用域。
            current_user_id (str): 当前用户ID。
            body (ManagementSystemCustomFieldCreate): 接口请求体对象。

        返回值：
            ManagementSystemCustomFieldResponse: 返回创建后的结果对象。
        """
        self._validate_field_definition(body)
        item = ManagementSystemCustomField(
            management_system_id=management_system_id,
            created_by_user_id=current_user_id,
            name=body.name,
            field_key=body.field_key,
            field_type=body.field_type,
            target_type=body.target_type,
            is_required=body.is_required,
            is_searchable=body.is_searchable,
            default_value=body.default_value,
            options=body.options,
            validation_rules=body.validation_rules,
            visibility_roles=body.visibility_roles,
            sort_order=body.sort_order,
            is_active=body.is_active,
        )
        try:
            created = await self.repo.add_field(item)
        except IntegrityError as exc:
            raise ValueError("字段标识已存在") from exc
        return ManagementSystemCustomFieldResponse.model_validate(created)

    async def list_values(
        self,
        management_system_id: str,
        target_type: str,
        target_id: str,
        viewer_role: str | None = None,
    ) -> ManagementSystemCustomFieldValueListResponse:
        """
        功能描述：
            按条件查询值列表。

        参数：
            management_system_id (str): 管理系统ID，用于限制数据作用域。
            target_type (str): 字符串结果。
            target_id (str): targetID。
            viewer_role (str | None): 角色信息。

        返回值：
            ManagementSystemCustomFieldValueListResponse: 返回列表或分页查询结果。
        """
        await self._ensure_target_exists(management_system_id, target_type, target_id)
        items = await self.repo.list_values(management_system_id, target_type, target_id)
        filtered_items = self._filter_value_items(items, viewer_role=viewer_role)
        return ManagementSystemCustomFieldValueListResponse(
            total=len(filtered_items),
            items=[ManagementSystemCustomFieldValueResponse.model_validate(item) for item in filtered_items],
        )

    async def list_value_map(
        self,
        management_system_id: str,
        target_type: str,
        target_id: str,
        viewer_role: str | None = None,
    ) -> dict[str, Any]:
        """
        功能描述：
            按条件查询值映射列表。

        参数：
            management_system_id (str): 管理系统ID，用于限制数据作用域。
            target_type (str): 字符串结果。
            target_id (str): targetID。
            viewer_role (str | None): 角色信息。

        返回值：
            dict[str, Any]: 返回字典形式的结果数据。
        """
        await self._ensure_target_exists(management_system_id, target_type, target_id)
        items = self._filter_value_items(
            await self.repo.list_values(management_system_id, target_type, target_id),
            viewer_role=viewer_role,
        )
        return {
            item.field.field_key: item.value
            for item in items
            if getattr(item, "field", None) and item.field
        }

    async def list_value_map_for_targets(
        self,
        management_system_id: str,
        target_type: str,
        target_ids: list[str],
        viewer_role: str | None = None,
    ) -> dict[str, dict[str, Any]]:
        """
        功能描述：
            按条件查询值映射fortargets列表。

        参数：
            management_system_id (str): 管理系统ID，用于限制数据作用域。
            target_type (str): 字符串结果。
            target_ids (list[str]): targetID列表。
            viewer_role (str | None): 角色信息。

        返回值：
            dict[str, dict[str, Any]]: 返回字典形式的结果数据。
        """
        items = self._filter_value_items(
            await self.repo.list_values_for_targets(management_system_id, target_type, target_ids),
            viewer_role=viewer_role,
        )
        mapped = {target_id: {} for target_id in target_ids}
        for item in items:
            field = getattr(item, "field", None)
            if not field:
                continue
            mapped.setdefault(item.target_id, {})[field.field_key] = item.value
        return mapped

    async def search_values(
        self,
        management_system_id: str,
        target_type: str,
        field_key: str,
        keyword: str,
        viewer_role: str | None = None,
    ) -> ManagementSystemCustomFieldSearchResponse:
        """
        功能描述：
            检索值。

        参数：
            management_system_id (str): 管理系统ID，用于限制数据作用域。
            target_type (str): 字符串结果。
            field_key (str): 字符串结果。
            keyword (str): 字符串结果。
            viewer_role (str | None): 角色信息。

        返回值：
            ManagementSystemCustomFieldSearchResponse: 返回检索结果。
        """
        normalized_keyword = keyword.strip()
        if not normalized_keyword:
            raise ValueError("检索关键词不能为空")
        field = await self.repo.get_field_by_key(management_system_id, target_type, field_key)
        if not field or not field.is_active:
            raise ValueError("字段不存在")
        if not field.is_searchable:
            raise ValueError("字段未启用检索")
        if not self._field_visible_to_role(field, viewer_role):
            raise ValueError("无权查询该字段")
        items = await self.repo.list_values_by_field(management_system_id, target_type, field.id)
        matched_items = [
            ManagementSystemCustomFieldSearchItem(
                field_id=field.id,
                field_key=field.field_key,
                target_type=field.target_type,
                target_id=item.target_id,
                value=item.value,
            )
            for item in items
            if normalized_keyword.lower() in self._stringify_search_value(item.value).lower()
        ]
        return ManagementSystemCustomFieldSearchResponse(total=len(matched_items), items=matched_items)

    async def upsert_value_map(
        self,
        management_system_id: str,
        target_type: str,
        target_id: str,
        current_user_id: str,
        values: dict[str, Any],
    ) -> dict[str, Any]:
        """
        功能描述：
            新增或更新值映射。

        参数：
            management_system_id (str): 管理系统ID，用于限制数据作用域。
            target_type (str): 字符串结果。
            target_id (str): targetID。
            current_user_id (str): 当前用户ID。
            values (dict[str, Any]): 字典形式的结果数据。

        返回值：
            dict[str, Any]: 返回字典形式的结果数据。
        """
        request_items: list[ManagementSystemCustomFieldValueItem] = []
        for field_key, value in values.items():
            field = await self.repo.get_field_by_key(management_system_id, target_type, field_key)
            if not field:
                raise ValueError(f"字段不存在: {field_key}")
            request_items.append(
                ManagementSystemCustomFieldValueItem(
                    field_id=field.id,
                    value=value,
                )
            )
        await self.upsert_values(
            management_system_id=management_system_id,
            target_type=target_type,
            target_id=target_id,
            current_user_id=current_user_id,
            body=ManagementSystemCustomFieldValueUpsertRequest(values=request_items),
        )
        return await self.list_value_map(management_system_id, target_type, target_id)

    async def upsert_values(
        self,
        management_system_id: str,
        target_type: str,
        target_id: str,
        current_user_id: str,
        body: ManagementSystemCustomFieldValueUpsertRequest,
    ) -> ManagementSystemCustomFieldValueListResponse:
        """
        功能描述：
            新增或更新值。

        参数：
            management_system_id (str): 管理系统ID，用于限制数据作用域。
            target_type (str): 字符串结果。
            target_id (str): targetID。
            current_user_id (str): 当前用户ID。
            body (ManagementSystemCustomFieldValueUpsertRequest): 接口请求体对象。

        返回值：
            ManagementSystemCustomFieldValueListResponse: 返回ManagementSystemCustomFieldValueListResponse类型的处理结果。
        """
        context = await self._load_upsert_context(
            management_system_id=management_system_id,
            target_type=target_type,
            target_id=target_id,
        )
        normalized_values = await self._normalize_upsert_request_values(
            management_system_id=management_system_id,
            target_type=target_type,
            body=body,
            context=context,
        )
        merged_values = self._merge_field_values(context.existing_values, normalized_values)
        self._validate_required_fields(context.fields, merged_values)
        await self._persist_upsert_values(
            management_system_id=management_system_id,
            target_type=target_type,
            target_id=target_id,
            current_user_id=current_user_id,
            normalized_values=normalized_values,
            context=context,
        )
        await self.repo.save()
        return await self.list_values(management_system_id, target_type, target_id)

    def _validate_field_definition(self, body: ManagementSystemCustomFieldCreate) -> None:
        """
        功能描述：
            校验字段definition。

        参数：
            body (ManagementSystemCustomFieldCreate): 接口请求体对象。

        返回值：
            None: 无返回值。
        """
        if not FIELD_KEY_PATTERN.match(body.field_key):
            raise ValueError("字段标识仅支持小写字母、数字与下划线，且需以字母开头")
        self._validate_select_field_definition(body)
        self._validate_default_field_value(body)

    async def _ensure_target_exists(
        self,
        management_system_id: str,
        target_type: str,
        target_id: str,
    ) -> None:
        """
        功能描述：
            确保targetexists存在，必要时自动补齐。

        参数：
            management_system_id (str): 管理系统ID，用于限制数据作用域。
            target_type (str): 字符串结果。
            target_id (str): targetID。

        返回值：
            None: 无返回值。
        """
        checker = self._get_target_exists_checker(target_type)
        if checker is None:
            raise ValueError("不支持的字段目标类型")
        if await checker(management_system_id, target_id):
            return
        raise ValueError("目标对象不存在")

    def _validate_required_fields(
        self,
        fields: list[ManagementSystemCustomField],
        merged_values: dict[str, Any],
    ) -> None:
        """
        功能描述：
            校验required字段。

        参数：
            fields (list[ManagementSystemCustomField]): 列表结果。
            merged_values (dict[str, Any]): 字典形式的结果数据。

        返回值：
            None: 无返回值。
        """
        for field in fields:
            if not field.is_active or not field.is_required:
                continue
            value = merged_values.get(field.id)
            if self._is_empty_value(value):
                raise ValueError(f"字段 {field.name} 为必填")

    @staticmethod
    def _field_visible_to_role(
        field: ManagementSystemCustomField,
        viewer_role: str | None,
    ) -> bool:
        """
        功能描述：
            处理visibleto角色。

        参数：
            field (ManagementSystemCustomField): ManagementSystemCustomField 类型的数据。
            viewer_role (str | None): 角色信息。

        返回值：
            bool: 返回操作是否成功。
        """
        roles = list(getattr(field, "visibility_roles", None) or [])
        if not roles:
            return True
        if viewer_role is None:
            return True
        return viewer_role in roles

    def _filter_fields(
        self,
        fields: list[ManagementSystemCustomField],
        viewer_role: str | None,
    ) -> list[ManagementSystemCustomField]:
        """
        功能描述：
            过滤字段。

        参数：
            fields (list[ManagementSystemCustomField]): 列表结果。
            viewer_role (str | None): 角色信息。

        返回值：
            list[ManagementSystemCustomField]: 返回列表形式的结果数据。
        """
        return [
            field
            for field in fields
            if self._field_visible_to_role(field, viewer_role)
        ]

    def _filter_value_items(
        self,
        items: list[ManagementSystemCustomFieldValue],
        viewer_role: str | None,
    ) -> list[ManagementSystemCustomFieldValue]:
        """
        功能描述：
            过滤值items。

        参数：
            items (list[ManagementSystemCustomFieldValue]): 当前处理的实体对象列表。
            viewer_role (str | None): 角色信息。

        返回值：
            list[ManagementSystemCustomFieldValue]: 返回列表形式的结果数据。
        """
        return [
            item
            for item in items
            if getattr(item, "field", None) and item.field and self._field_visible_to_role(item.field, viewer_role)
        ]

    def _normalize_field_value(
        self,
        field: FieldDefinition,
        value: Any,
    ) -> Any:
        """
        功能描述：
            处理字段值。

        参数：
            field (FieldDefinition): FieldDefinition 类型的数据。
            value (Any): 值。

        返回值：
            Any: 返回Any类型的处理结果。
        """
        if value is None:
            return None
        field_type = self._resolve_enum_value(field.field_type)
        normalizer = self._get_field_value_normalizer(field_type)
        if normalizer is None:
            raise ValueError("不支持的字段类型")
        return normalizer(field, value)

    def _validate_select_field_definition(self, body: ManagementSystemCustomFieldCreate) -> None:
        """
        功能描述：
            校验select字段definition。

        参数：
            body (ManagementSystemCustomFieldCreate): 接口请求体对象。

        返回值：
            None: 无返回值。
        """
        if self._resolve_enum_value(body.field_type) != SELECT_FIELD_TYPE:
            return
        choices = self._extract_select_choices(body.options)
        if choices:
            return
        raise ValueError("下拉字段必须提供可选项")

    def _validate_default_field_value(self, body: ManagementSystemCustomFieldCreate) -> None:
        """
        功能描述：
            校验默认字段值。

        参数：
            body (ManagementSystemCustomFieldCreate): 接口请求体对象。

        返回值：
            None: 无返回值。
        """
        if body.default_value is None:
            return
        self._normalize_field_value(body, body.default_value)

    def _get_target_exists_checker(self, target_type: str) -> TargetExistsChecker | None:
        """
        功能描述：
            按条件获取targetexistschecker。

        参数：
            target_type (str): 字符串结果。

        返回值：
            TargetExistsChecker | None: 返回处理结果对象；无可用结果时返回 None。
        """
        checkers: dict[str, TargetExistsChecker] = {
            ASSIGNMENT_TARGET_TYPE: self._assignment_target_exists,
            COURSE_TARGET_TYPE: self._course_target_exists,
            STUDENT_TARGET_TYPE: self._student_target_exists,
        }
        return checkers.get(target_type)

    def _get_field_value_normalizer(self, field_type: str) -> FieldValueNormalizer | None:
        """
        功能描述：
            按条件获取字段值normalizer。

        参数：
            field_type (str): 字符串结果。

        返回值：
            FieldValueNormalizer | None: 返回处理结果对象；无可用结果时返回 None。
        """
        normalizers: dict[str, FieldValueNormalizer] = {
            TEXT_FIELD_TYPE: self._normalize_text_field_value,
            NUMBER_FIELD_TYPE: self._normalize_number_field_value,
            BOOLEAN_FIELD_TYPE: self._normalize_boolean_field_value,
            DATE_FIELD_TYPE: self._normalize_date_field_value,
            SELECT_FIELD_TYPE: self._normalize_select_field_value,
            JSON_FIELD_TYPE: self._normalize_json_field_value,
            FILE_FIELD_TYPE: self._normalize_file_field_value,
        }
        return normalizers.get(field_type)

    async def _load_upsert_context(
        self,
        management_system_id: str,
        target_type: str,
        target_id: str,
    ) -> UpsertContext:
        """
        功能描述：
            加载upsertcontext。

        参数：
            management_system_id (str): 管理系统ID，用于限制数据作用域。
            target_type (str): 字符串结果。
            target_id (str): targetID。

        返回值：
            UpsertContext: 返回UpsertContext类型的处理结果。
        """
        await self._ensure_target_exists(management_system_id, target_type, target_id)
        fields = await self.repo.list_fields(management_system_id, target_type)
        existing_items = await self.repo.list_values(management_system_id, target_type, target_id)
        return UpsertContext(
            fields=fields,
            field_by_id={field.id: field for field in fields},
            existing_values={item.field_id: item for item in existing_items},
        )

    async def _normalize_upsert_request_values(
        self,
        management_system_id: str,
        target_type: str,
        body: ManagementSystemCustomFieldValueUpsertRequest,
        context: UpsertContext,
    ) -> dict[str, Any]:
        """
        功能描述：
            处理upsert请求值。

        参数：
            management_system_id (str): 管理系统ID，用于限制数据作用域。
            target_type (str): 字符串结果。
            body (ManagementSystemCustomFieldValueUpsertRequest): 接口请求体对象。
            context (UpsertContext): UpsertContext 类型的数据。

        返回值：
            dict[str, Any]: 返回字典形式的结果数据。
        """
        normalized_values: dict[str, Any] = {}
        for value_item in body.values:
            field = await self._get_upsert_field(
                field_id=value_item.field_id,
                management_system_id=management_system_id,
                context=context,
            )
            self._ensure_upsert_field_available(field, target_type)
            normalized_values[field.id] = self._normalize_field_value(field, value_item.value)
        return normalized_values

    async def _get_upsert_field(
        self,
        field_id: str,
        management_system_id: str,
        context: UpsertContext,
    ) -> ManagementSystemCustomField:
        """
        功能描述：
            按条件获取upsert字段。

        参数：
            field_id (str): 字段ID。
            management_system_id (str): 管理系统ID，用于限制数据作用域。
            context (UpsertContext): UpsertContext 类型的数据。

        返回值：
            ManagementSystemCustomField: 返回ManagementSystemCustomField类型的处理结果。
        """
        field = context.field_by_id.get(field_id)
        if field:
            return field
        field = await self.repo.get_field(field_id, management_system_id)
        if not field:
            raise ValueError("字段不存在")
        return field

    def _ensure_upsert_field_available(
        self,
        field: ManagementSystemCustomField,
        target_type: str,
    ) -> None:
        """
        功能描述：
            确保upsert字段available存在，必要时自动补齐。

        参数：
            field (ManagementSystemCustomField): ManagementSystemCustomField 类型的数据。
            target_type (str): 字符串结果。

        返回值：
            None: 无返回值。
        """
        if not field.is_active:
            raise ValueError("字段未启用")
        if self._resolve_enum_value(field.target_type) != target_type:
            raise ValueError("字段目标类型不匹配")

    @staticmethod
    def _merge_field_values(
        existing_values: dict[str, ManagementSystemCustomFieldValue],
        normalized_values: dict[str, Any],
    ) -> dict[str, Any]:
        """
        功能描述：
            合并字段值。

        参数：
            existing_values (dict[str, ManagementSystemCustomFieldValue]): 字典形式的结果数据。
            normalized_values (dict[str, Any]): 字典形式的结果数据。

        返回值：
            dict[str, Any]: 返回字典形式的结果数据。
        """
        merged_values = {
            field_id: item.value
            for field_id, item in existing_values.items()
        }
        merged_values.update(normalized_values)
        return merged_values

    async def _persist_upsert_values(
        self,
        management_system_id: str,
        target_type: str,
        target_id: str,
        current_user_id: str,
        normalized_values: dict[str, Any],
        context: UpsertContext,
    ) -> None:
        """
        功能描述：
            持久化upsert值。

        参数：
            management_system_id (str): 管理系统ID，用于限制数据作用域。
            target_type (str): 字符串结果。
            target_id (str): targetID。
            current_user_id (str): 当前用户ID。
            normalized_values (dict[str, Any]): 字典形式的结果数据。
            context (UpsertContext): UpsertContext 类型的数据。

        返回值：
            None: 无返回值。
        """
        for field_id, normalized_value in normalized_values.items():
            existing = context.existing_values.get(field_id)
            if existing:
                self._update_existing_value(
                    item=existing,
                    management_system_id=management_system_id,
                    target_type=target_type,
                    value=normalized_value,
                    current_user_id=current_user_id,
                )
                continue
            await self.repo.add(
                ManagementSystemCustomFieldValue(
                    field_id=field_id,
                    management_system_id=management_system_id,
                    target_type=target_type,
                    target_id=target_id,
                    value=normalized_value,
                    created_by_user_id=current_user_id,
                )
            )

    @staticmethod
    def _update_existing_value(
        item: ManagementSystemCustomFieldValue,
        management_system_id: str,
        target_type: str,
        value: Any,
        current_user_id: str,
    ) -> None:
        """
        功能描述：
            更新existing值并返回最新结果。

        参数：
            item (ManagementSystemCustomFieldValue): 当前处理的实体对象。
            management_system_id (str): 管理系统ID，用于限制数据作用域。
            target_type (str): 字符串结果。
            value (Any): 值。
            current_user_id (str): 当前用户ID。

        返回值：
            None: 无返回值。
        """
        item.value = value
        item.created_by_user_id = current_user_id
        item.target_type = target_type
        item.management_system_id = management_system_id

    async def _assignment_target_exists(self, management_system_id: str, target_id: str) -> bool:
        """
        功能描述：
            处理targetexists。

        参数：
            management_system_id (str): 管理系统ID，用于限制数据作用域。
            target_id (str): targetID。

        返回值：
            bool: 返回操作是否成功。
        """
        result = await self.repo.db.execute(
            select(Assignment.id).where(
                Assignment.id == target_id,
            )
        )
        return bool(result.scalar())

    async def _course_target_exists(self, management_system_id: str, target_id: str) -> bool:
        """
        功能描述：
            处理targetexists。

        参数：
            management_system_id (str): 管理系统ID，用于限制数据作用域。
            target_id (str): targetID。

        返回值：
            bool: 返回操作是否成功。
        """
        result = await self.repo.db.execute(
            select(Course.id).where(
                Course.id == target_id,
            )
        )
        return bool(result.scalar())

    async def _student_target_exists(self, management_system_id: str, target_id: str) -> bool:
        """
        功能描述：
            处理targetexists。

        参数：
            management_system_id (str): 管理系统ID，用于限制数据作用域。
            target_id (str): targetID。

        返回值：
            bool: 返回操作是否成功。
        """
        result = await self.repo.db.execute(
            select(Student.id)
            .join(UserManagementSystem, UserManagementSystem.user_id == Student.user_id)
            .where(
                Student.id == target_id,
                UserManagementSystem.management_system_id == management_system_id,
            )
        )
        return bool(result.scalar())

    @staticmethod
    def _resolve_enum_value(value: Any) -> str:
        """
        功能描述：
            解析enum值。

        参数：
            value (Any): 值。

        返回值：
            str: 返回str类型的处理结果。
        """
        return str(getattr(value, "value", value))

    @staticmethod
    def _get_validation_rules(field: FieldDefinition) -> dict[str, Any]:
        """
        功能描述：
            按条件获取validationrules。

        参数：
            field (FieldDefinition): FieldDefinition 类型的数据。

        返回值：
            dict[str, Any]: 返回字典形式的结果数据。
        """
        return getattr(field, "validation_rules", None) or {}

    def _normalize_text_field_value(self, field: FieldDefinition, value: Any) -> str:
        """
        功能描述：
            处理文本字段值。

        参数：
            field (FieldDefinition): FieldDefinition 类型的数据。
            value (Any): 值。

        返回值：
            str: 返回str类型的处理结果。
        """
        if not isinstance(value, str):
            raise ValueError(f"字段 {field.name} 必须为文本")
        validation_rules = self._get_validation_rules(field)
        if "min_length" in validation_rules and len(value) < int(validation_rules["min_length"]):
            raise ValueError(f"字段 {field.name} 长度不足")
        if "max_length" in validation_rules and len(value) > int(validation_rules["max_length"]):
            raise ValueError(f"字段 {field.name} 长度超出限制")
        pattern = validation_rules.get("pattern")
        if pattern and not re.match(pattern, value):
            raise ValueError(f"字段 {field.name} 格式不正确")
        return value

    def _normalize_number_field_value(self, field: FieldDefinition, value: Any) -> int | float:
        """
        功能描述：
            处理number字段值。

        参数：
            field (FieldDefinition): FieldDefinition 类型的数据。
            value (Any): 值。

        返回值：
            int | float: 返回int | float类型的处理结果。
        """
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"字段 {field.name} 必须为数字")
        validation_rules = self._get_validation_rules(field)
        minimum = validation_rules.get("min")
        maximum = validation_rules.get("max")
        if minimum is not None and value < minimum:
            raise ValueError(f"字段 {field.name} 小于最小值")
        if maximum is not None and value > maximum:
            raise ValueError(f"字段 {field.name} 超出最大值")
        return value

    @staticmethod
    def _normalize_boolean_field_value(field: FieldDefinition, value: Any) -> bool:
        """
        功能描述：
            处理boolean字段值。

        参数：
            field (FieldDefinition): FieldDefinition 类型的数据。
            value (Any): 值。

        返回值：
            bool: 返回操作是否成功。
        """
        if not isinstance(value, bool):
            raise ValueError(f"字段 {field.name} 必须为布尔值")
        return value

    @staticmethod
    def _normalize_date_field_value(field: FieldDefinition, value: Any) -> str:
        """
        功能描述：
            处理date字段值。

        参数：
            field (FieldDefinition): FieldDefinition 类型的数据。
            value (Any): 值。

        返回值：
            str: 返回str类型的处理结果。
        """
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, date):
            return value.isoformat()
        if isinstance(value, str):
            try:
                datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError(f"字段 {field.name} 日期格式不正确") from exc
            return value
        raise ValueError(f"字段 {field.name} 必须为日期字符串")

    def _normalize_select_field_value(self, field: FieldDefinition, value: Any) -> Any:
        """
        功能描述：
            处理select字段值。

        参数：
            field (FieldDefinition): FieldDefinition 类型的数据。
            value (Any): 值。

        返回值：
            Any: 返回Any类型的处理结果。
        """
        choices = self._extract_select_choices(getattr(field, "options", None))
        if value not in choices:
            raise ValueError(f"字段 {field.name} 取值不在可选项内")
        return value

    @staticmethod
    def _normalize_file_field_value(field: FieldDefinition, value: Any) -> str:
        if not isinstance(value, str):
            raise ValueError(f"字段 {field.name} 必须为文件路径字符串")
        normalized = value.strip()
        if not normalized:
            raise ValueError(f"字段 {field.name} 文件路径不能为空")
        return normalized

    @staticmethod
    def _normalize_json_field_value(field: FieldDefinition, value: Any) -> Any:
        """
        功能描述：
            处理json字段值。

        参数：
            field (FieldDefinition): FieldDefinition 类型的数据。
            value (Any): 值。

        返回值：
            Any: 返回Any类型的处理结果。
        """
        return value

    @staticmethod
    def _extract_select_choices(options: dict[str, Any] | None) -> list[Any]:
        """
        功能描述：
            提取selectchoices。

        参数：
            options (dict[str, Any] | None): 字典形式的结果数据。

        返回值：
            list[Any]: 返回列表形式的结果数据。
        """
        if not options:
            return []
        raw_choices = options.get("choices") or options.get("items") or []
        choices: list[Any] = []
        for item in raw_choices:
            if isinstance(item, dict):
                choices.append(item.get("value"))
            else:
                choices.append(item)
        return [item for item in choices if item is not None]

    @staticmethod
    def _is_empty_value(value: Any) -> bool:
        """
        功能描述：
            处理empty值。

        参数：
            value (Any): 值。

        返回值：
            bool: 返回操作是否成功。
        """
        return value is None or value == "" or value == []

    @staticmethod
    def _stringify_search_value(value: Any) -> str:
        """
        功能描述：
            处理检索值。

        参数：
            value (Any): 值。

        返回值：
            str: 返回str类型的处理结果。
        """
        if value is None:
            return ""
        if isinstance(value, (dict, list)):
            return str(value)
        return str(value)
