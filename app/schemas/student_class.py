from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class StudentClassBase(BaseModel):
    student_id: str
    teaching_class_id: str


class StudentClassCreate(StudentClassBase):
    pass


class StudentClassUpdate(BaseModel):
    status: Optional[str] = None


class StudentClassResponse(StudentClassBase):
    id: str
    status: str
    joined_at: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StudentClassListResponse(BaseModel):
    total: int
    items: list[StudentClassResponse]


class StudentClassJoinResponse(BaseModel):
    id: str
    teaching_class_id: str
    class_name: str
    teacher_name: str
    joined_at: datetime
    status: str

    model_config = ConfigDict(from_attributes=True)
