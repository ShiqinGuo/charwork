from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class StudentBase(BaseModel):
    user_id: str
    name: str
    class_name: Optional[str] = None


class StudentCreate(StudentBase):
    pass


class StudentUpdate(BaseModel):
    name: Optional[str] = None
    class_name: Optional[str] = None


class StudentResponse(StudentBase):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
