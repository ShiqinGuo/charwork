from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class TeacherBase(BaseModel):
    user_id: str
    name: str
    department: Optional[str] = None


class TeacherCreate(TeacherBase):
    pass


class TeacherUpdate(BaseModel):
    name: Optional[str] = None
    department: Optional[str] = None


class TeacherResponse(TeacherBase):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
