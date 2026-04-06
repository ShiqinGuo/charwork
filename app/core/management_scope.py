from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, Header, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.repositories.management_system_repo import ManagementSystemRepository
from app.services.management_system_service import ManagementSystemService


@dataclass
class ManagementScope:
    management_system_id: str
    source: str


async def get_management_scope(
    management_system_id: Optional[str] = Query(default=None),
    x_management_system_id: Optional[str] = Header(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ManagementScope:
    # Query 参数优先于 Header，便于接口调试时显式覆盖客户端默认上下文。
    """
    功能描述：
        按条件获取管理作用域。

    参数：
        management_system_id (Optional[str]): 管理系统ID，用于限制数据作用域。
        x_management_system_id (Optional[str]): x管理系统ID。
        current_user (User): 当前登录用户对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        ManagementScope: 返回查询到的结果对象。
    """
    target_id = management_system_id or x_management_system_id
    if target_id:
        item = await ManagementSystemRepository(db).get_accessible(target_id, current_user.id)
        if not item:
            raise HTTPException(status_code=403, detail="无权访问该管理系统")
        return ManagementScope(management_system_id=item.id, source="explicit")

    # 未显式指定时回退到默认管理系统，确保所有接口都有稳定的作用域。
    default_item = await ManagementSystemService(db).get_default_system(current_user)
    return ManagementScope(management_system_id=default_item.id, source="default")
