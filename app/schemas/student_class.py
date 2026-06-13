from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, field_validator


class StudentClassBase(BaseModel):
    student_id: str
    teaching_class_id: str


class StudentClassCreate(StudentClassBase):
    pass


class StudentClassUpdate(BaseModel):
    status: Optional[str] = None


class TeacherBrief(BaseModel):
    """教师简要信息"""
    id: str
    name: str

    model_config = ConfigDict(from_attributes=True)


class TeachingClassBrief(BaseModel):
    """班级简要信息"""
    id: str
    name: str
    description: Optional[str] = None
    student_count: Optional[int] = None
    teacher: Optional[TeacherBrief] = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator('student_count', mode='before')
    @classmethod
    def default_student_count(cls, v):
        return v if v is not None else 0


class StudentClassResponse(StudentClassBase):
    id: str
    status: str
    joined_at: datetime
    created_at: datetime
    updated_at: datetime
    teaching_class: Optional[TeachingClassBrief] = None

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
