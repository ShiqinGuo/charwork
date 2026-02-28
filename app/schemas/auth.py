from typing import Literal, Optional
from pydantic import BaseModel


class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    role: Literal["teacher", "student"]
    name: str
    department: Optional[str] = None
    class_name: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
