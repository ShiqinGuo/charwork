"""
为什么这样做：管理系统配置以常量模板生成，保证默认系统与自定义系统共享同一配置基线。
特殊逻辑：配置归一化按层合并并保留未知键，兼顾前向扩展；默认系统初始化对并发冲突做回滚兜底。
"""

from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.management_system import ManagementSystem, ManagementSystemAccessRole, UserManagementSystem
from app.models.user import User, UserRole
from app.repositories.management_system_repo import ManagementSystemRepository
from app.repositories.user_repo import UserRepository
from app.schemas.management_system import (
    ManagementSystemCreate,
    ManagementSystemListResponse,
    ManagementSystemOwner,
    ManagementSystemResponse,
    ManagementSystemUpdate,
)


DEFAULT_MANAGEMENT_SYSTEM_PRESET_KEY = "builtin_hanzi_default"
DEFAULT_MANAGEMENT_SYSTEM_NAME = "默认汉字管理系统"
DEFAULT_MANAGEMENT_SYSTEM_DESCRIPTION = "系统自动初始化的默认汉字教学与管理入口"
DEFAULT_MANAGEMENT_SYSTEM_TYPE = "hanzi"
DEFAULT_MODULE_CONFIGS = (
    {"key": "hanzi", "name": "汉字管理", "enabled": True, "path": "/teacher/characters"},
    {"key": "assignments", "name": "作业管理", "enabled": True, "path": "/teacher/assignments"},
    {"key": "students", "name": "学生管理", "enabled": True, "path": "/teacher/students"},
)
DEFAULT_NAVIGATION_KEYS = ("hanzi", "assignments", "students")
DEFAULT_HOME_ENTRY = "hanzi"
DEFAULT_CUSTOM_FIELD_TARGETS = ("course", "assignment", "student")
DEFAULT_DISPLAY_CONFIG = {
    "title": DEFAULT_MANAGEMENT_SYSTEM_NAME,
    "theme": "default",
}


def _copy_module_configs() -> list[dict[str, object]]:
    """
    功能描述：
        处理moduleconfigs。

    参数：
        无。

    返回值：
        list[dict[str, object]]: 返回列表形式的结果数据。
    """
    return [dict(module) for module in DEFAULT_MODULE_CONFIGS]


def _build_extensions_config() -> dict[str, dict[str, object]]:
    """
    功能描述：
        构建extensionsconfig。

    参数：
        无。

    返回值：
        dict[str, dict[str, object]]: 返回字典形式的结果数据。
    """
    return {
        "custom_fields": {
            "enabled": True,
            "targets": list(DEFAULT_CUSTOM_FIELD_TARGETS),
        }
    }


def _build_display_config(*, builtin: bool) -> dict[str, object]:
    """
    功能描述：
        构建displayconfig。

    参数：
        builtin (bool): 布尔值结果。

    返回值：
        dict[str, object]: 返回字典形式的结果数据。
    """
    return {
        **DEFAULT_DISPLAY_CONFIG,
        "builtin": builtin,
    }


def build_builtin_hanzi_system_config() -> dict[str, object]:
    """
    功能描述：
        构建builtin汉字系统config。

    参数：
        无。

    返回值：
        dict[str, object]: 返回字典形式的结果数据。
    """
    return {
        "modules": _copy_module_configs(),
        "navigation": list(DEFAULT_NAVIGATION_KEYS),
        "home_entry": DEFAULT_HOME_ENTRY,
        "extensions": _build_extensions_config(),
        "display": _build_display_config(builtin=True),
    }


def build_custom_system_config() -> dict[str, object]:
    """
    功能描述：
        构建自定义系统config。

    参数：
        无。

    返回值：
        dict[str, object]: 返回字典形式的结果数据。
    """
    config = build_builtin_hanzi_system_config()
    config["display"] = _build_display_config(builtin=False)
    return config


def normalize_management_system_config(config: Optional[dict[str, object]]) -> dict[str, object]:
    """
    功能描述：
        处理管理系统config。

    参数：
        config (Optional[dict[str, object]]): 字典形式的结果数据。

    返回值：
        dict[str, object]: 返回字典形式的结果数据。
    """
    normalized = build_custom_system_config()
    incoming = config or {}
    normalized["modules"] = incoming.get("modules", normalized["modules"])
    normalized["navigation"] = incoming.get("navigation", normalized["navigation"])
    normalized["home_entry"] = incoming.get("home_entry", normalized["home_entry"])
    normalized["display"] = {
        **normalized["display"],
        **incoming.get("display", {}),
    }
    normalized["extensions"] = {
        **normalized["extensions"],
        **incoming.get("extensions", {}),
    }
    normalized["extensions"]["custom_fields"] = {
        **build_custom_system_config()["extensions"]["custom_fields"],
        **normalized["extensions"].get("custom_fields", {}),
    }
    for key, value in incoming.items():
        if key not in normalized:
            normalized[key] = value
    return normalized


class ManagementSystemService:
    def __init__(self, db: AsyncSession):
        """
        功能描述：
            初始化ManagementSystemService并准备运行所需的依赖对象。

        参数：
            db (AsyncSession): 数据库会话，用于执行持久化操作。

        返回值：
            None: 无返回值。
        """
        self.repo = ManagementSystemRepository(db)
        self.user_repo = UserRepository(db)

    async def list_my_systems(
        self,
        current_user: User,
        skip: int = 0,
        limit: int = 20,
    ) -> ManagementSystemListResponse:
        """
        功能描述：
            按条件查询mysystems列表。

        参数：
            current_user (User): 当前登录用户对象。
            skip (int): 分页偏移量。
            limit (int): 单次查询的最大返回数量。

        返回值：
            ManagementSystemListResponse: 返回列表或分页查询结果。
        """
        await self.ensure_default_system_entity(current_user)
        items = await self.repo.list_accessible(current_user.id, skip, limit)
        total = await self.repo.count_accessible(current_user.id)
        return ManagementSystemListResponse(
            total=total,
            items=[self._to_response(item, current_user.id) for item in items],
        )

    async def get_system_detail(self, management_system_id: str,
                                current_user: User) -> Optional[ManagementSystemResponse]:
        """
        功能描述：
            按条件获取系统detail。

        参数：
            management_system_id (str): 管理系统ID，用于限制数据作用域。
            current_user (User): 当前登录用户对象。

        返回值：
            Optional[ManagementSystemResponse]: 返回查询到的结果对象；未命中时返回 None。
        """
        await self.ensure_default_system_entity(current_user)
        item = await self.repo.get_accessible(management_system_id, current_user.id)
        if not item:
            return None
        return self._to_response(item, current_user.id)

    async def get_default_system(self, current_user: User) -> ManagementSystemResponse:
        """
        功能描述：
            按条件获取默认系统。

        参数：
            current_user (User): 当前登录用户对象。

        返回值：
            ManagementSystemResponse: 返回查询到的结果对象。
        """
        item = await self.ensure_default_system_entity(current_user)
        return self._to_response(item, current_user.id)

    async def create_custom_system(
        self,
        current_user: User,
        system_in: ManagementSystemCreate,
    ) -> ManagementSystemResponse:
        """
        功能描述：
            创建自定义系统并返回结果。

        参数：
            current_user (User): 当前登录用户对象。
            system_in (ManagementSystemCreate): 系统输入对象。

        返回值：
            ManagementSystemResponse: 返回创建后的结果对象。
        """
        if current_user.role != UserRole.TEACHER:
            raise PermissionError("仅教师可创建自定义管理系统")

        config = normalize_management_system_config(system_in.config)
        management_system = ManagementSystem(
            owner_user_id=current_user.id,
            name=system_in.name,
            description=system_in.description,
            system_type=system_in.system_type,
            preset_key=None,
            is_default=False,
            config=config,
        )

        await self.repo.add_system(management_system)
        await self.repo.add_link(
            UserManagementSystem(
                user_id=current_user.id,
                management_system_id=management_system.id,
                access_role=ManagementSystemAccessRole.OWNER,
            )
        )
        await self.repo.save()

        created = await self.repo.get(management_system.id)
        return self._to_response(created, current_user.id)

    async def update_custom_system(
        self,
        management_system_id: str,
        current_user: User,
        system_in: ManagementSystemUpdate,
    ) -> Optional[ManagementSystemResponse]:
        """
        功能描述：
            更新自定义系统并返回最新结果。

        参数：
            management_system_id (str): 管理系统ID，用于限制数据作用域。
            current_user (User): 当前登录用户对象。
            system_in (ManagementSystemUpdate): 系统输入对象。

        返回值：
            Optional[ManagementSystemResponse]: 返回更新后的结果对象；未命中时返回 None。
        """
        if current_user.role != UserRole.TEACHER:
            raise PermissionError("仅教师可编辑自定义管理系统")

        management_system = await self.repo.get(management_system_id)
        if not management_system:
            return None

        if management_system.owner_user_id != current_user.id:
            raise PermissionError("仅可维护本人创建的管理系统")

        if management_system.is_default:
            raise ValueError("默认汉字管理系统不支持编辑")

        update_data = system_in.model_dump(exclude_unset=True)
        if "config" in update_data:
            update_data["config"] = normalize_management_system_config(update_data["config"])
        for key, value in update_data.items():
            setattr(management_system, key, value)

        await self.repo.save()
        updated = await self.repo.get(management_system.id)
        return self._to_response(updated, current_user.id)

    async def ensure_default_system_entity(self, user: User, commit: bool = True) -> ManagementSystem:
        """
        功能描述：
            确保默认系统entity存在，必要时自动补齐。

        参数：
            user (User): User 类型的数据。
            commit (bool): 布尔值结果。

        返回值：
            ManagementSystem: 返回ManagementSystem类型的处理结果。
        """
        existing = await self.repo.get_default_for_user(user.id, DEFAULT_MANAGEMENT_SYSTEM_PRESET_KEY)
        if existing:
            return existing

        try:
            candidate = await self.repo.get_owner_preset_system(user.id, DEFAULT_MANAGEMENT_SYSTEM_PRESET_KEY)
            if not candidate:
                candidate = await self.repo.add_system(
                    ManagementSystem(
                        owner_user_id=user.id,
                        name=DEFAULT_MANAGEMENT_SYSTEM_NAME,
                        description=DEFAULT_MANAGEMENT_SYSTEM_DESCRIPTION,
                        system_type=DEFAULT_MANAGEMENT_SYSTEM_TYPE,
                        preset_key=DEFAULT_MANAGEMENT_SYSTEM_PRESET_KEY,
                        is_default=True,
                        config=build_builtin_hanzi_system_config(),
                    )
                )

            link = await self.repo.get_link(user.id, candidate.id)
            if not link:
                await self.repo.add_link(
                    UserManagementSystem(
                        user_id=user.id,
                        management_system_id=candidate.id,
                        access_role=ManagementSystemAccessRole.OWNER,
                    )
                )

            if commit:
                await self.repo.save()
        except IntegrityError:
            await self.repo.rollback()

        ensured = await self.repo.get_default_for_user(user.id, DEFAULT_MANAGEMENT_SYSTEM_PRESET_KEY)
        if ensured:
            return ensured

        raise ValueError("默认汉字管理系统初始化失败")

    async def backfill_default_systems(self) -> int:
        """
        功能描述：
            处理默认systems。

        参数：
            无。

        返回值：
            int: 返回int类型的处理结果。
        """
        user_ids = await self.repo.list_user_ids_missing_default(DEFAULT_MANAGEMENT_SYSTEM_PRESET_KEY)
        compensated = 0
        for user_id in user_ids:
            user = await self.user_repo.get(user_id)
            if not user:
                continue
            await self.ensure_default_system_entity(user)
            compensated += 1
        return compensated

    def _to_response(self, item: ManagementSystem, current_user_id: str) -> ManagementSystemResponse:
        """
        功能描述：
            将输入数据转换为响应。

        参数：
            item (ManagementSystem): 当前处理的实体对象。
            current_user_id (str): 当前用户ID。

        返回值：
            ManagementSystemResponse: 返回ManagementSystemResponse类型的处理结果。
        """
        return ManagementSystemResponse(
            id=item.id,
            name=item.name,
            description=item.description,
            system_type=item.system_type,
            config=normalize_management_system_config(item.config),
            preset_key=item.preset_key,
            is_default=item.is_default,
            owner_user_id=item.owner_user_id,
            owner=ManagementSystemOwner(
                id=item.owner_user.id,
                username=item.owner_user.username,
                role=item.owner_user.role.value if hasattr(
                    item.owner_user.role, "value") else str(
                    item.owner_user.role),
                display_name=self._get_user_display_name(item.owner_user),
            ),
            is_owner=item.owner_user_id == current_user_id,
            can_edit=item.owner_user_id == current_user_id and not item.is_default,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )

    @staticmethod
    def _get_user_display_name(user: User) -> str:
        """
        功能描述：
            按条件获取用户displayname。

        参数：
            user (User): User 类型的数据。

        返回值：
            str: 返回str类型的处理结果。
        """
        teacher_profile = getattr(user, "teacher_profile", None)
        if teacher_profile and teacher_profile.name:
            return teacher_profile.name
        student_profile = getattr(user, "student_profile", None)
        if student_profile and student_profile.name:
            return student_profile.name
        return user.username
