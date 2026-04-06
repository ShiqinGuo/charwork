from fastapi import APIRouter, Depends, HTTPException
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_token, get_current_user
from app.core.database import get_db
from app.core.security import SessionUser, create_access_token, revoke_access_token
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.services.user_service import UserService


router = APIRouter()


@router.post("/register")
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """
    功能描述：
        注册routes认证。

    参数：
        body (RegisterRequest): 接口请求体对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    service = UserService(db)
    try:
        user = await service.register(
            username=body.username,
            email=body.email,
            password=body.password,
            role=body.role,
            name=body.name,
            department=body.department,
            class_name=body.class_name,
        )
        return {"id": user.id, "username": user.username, "role": user.role}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"注册失败：{str(e)}")


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    功能描述：
        处理routes认证。

    参数：
        body (LoginRequest): 接口请求体对象。
        db (AsyncSession): 数据库会话，用于执行持久化操作。

    返回值：
        None: 无返回值。
    """
    service = UserService(db)
    user = await service.authenticate(body.username, body.password)
    if not user:
        raise HTTPException(status_code=400, detail="用户名或密码错误")
    try:
        token = await create_access_token(user=user)
    except RedisError as exc:
        raise HTTPException(status_code=503, detail="会话服务不可用") from exc
    return TokenResponse(access_token=token)


@router.get("/me")
async def me(current_user: SessionUser = Depends(get_current_user)):
    """
    功能描述：
        处理routes认证。

    参数：
        current_user (SessionUser): 当前登录用户对象。

    返回值：
        None: 无返回值。
    """
    return {
        "id": current_user.id,
        "email": current_user.email,
        "username": current_user.username,
        "role": current_user.role,
        "is_active": current_user.is_active,
    }


@router.post("/logout")
async def logout(token: str = Depends(get_current_token)):
    """
    功能描述：
        处理routes认证。

    参数：
        token (str): 令牌字符串。

    返回值：
        None: 无返回值。
    """
    try:
        await revoke_access_token(token)
    except RedisError as exc:
        raise HTTPException(status_code=503, detail="会话服务不可用") from exc
    return {"success": True}
