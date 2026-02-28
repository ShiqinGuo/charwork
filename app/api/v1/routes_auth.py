from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import create_access_token
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.services.user_service import UserService


router = APIRouter()


@router.post("/register")
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
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
    service = UserService(db)
    user = await service.authenticate(body.username, body.password)
    if not user:
        raise HTTPException(status_code=400, detail="用户名或密码错误")
    token = create_access_token(subject=user.id)
    return TokenResponse(access_token=token)
