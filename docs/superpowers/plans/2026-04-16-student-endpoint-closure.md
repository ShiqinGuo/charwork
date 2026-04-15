# 学生端功能闭环实现计划

> **对于代理工作者：** 推荐使用 superpowers:subagent-driven-development 或 superpowers:executing-plans 来逐个任务执行此计划。步骤使用复选框 (`- [ ]`) 语法来追踪进度。

**目标：** 实现学生端完整的功能闭环，从加入班级到查看反馈的完整学习路径。

**架构：** 分三个阶段实现，第一阶段实现核心学习路径（班级加入、作业查看、提交、反馈查看），第二阶段实现个人中心，第三阶段集成协作功能。采用 TDD 方式，每个接口先写测试再实现。

**技术栈：** FastAPI、SQLAlchemy、Pydantic、pytest

---

## 文件结构

### 新增文件
- `app/models/student_class.py` - StudentClass 数据模型
- `app/schemas/student_class.py` - StudentClass 相关 Schema
- `app/repositories/student_class_repo.py` - StudentClass 仓储层
- `app/services/student_class_service.py` - StudentClass 业务逻辑
- `app/api/v1/routes_student_classes.py` - 学生班级相关路由
- `tests/test_student_classes.py` - 学生班级相关测试

### 修改文件
- `app/main.py` - 注册新路由
- `app/models/__init__.py` - 导出 StudentClass 模型
- `app/services/student_service.py` - 扩展学生服务
- `app/schemas/student.py` - 扩展学生 Schema
- `alembic/versions/` - 数据库迁移文件

---

## 第一阶段：核心学习路径

### Task 1: 创建 StudentClass 数据模型

**文件：**
- Create: `app/models/student_class.py`
- Modify: `app/models/__init__.py`

- [ ] **Step 1: 编写 StudentClass 模型**

```python
# app/models/student_class.py
from typing import Optional
from enum import Enum as PyEnum
from sqlalchemy import String, ForeignKey, DateTime, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.utils.id_generator import generate_id


class StudentClassStatus(str, PyEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class StudentClass(Base):
    __tablename__ = "student_class"
    __table_args__ = (
        UniqueConstraint("student_id", "teaching_class_id", name="uq_student_class"),
    )

    id: Mapped[str] = mapped_column(String(50), primary_key=True, default=generate_id)
    student_id: Mapped[str] = mapped_column(String(50), ForeignKey("student.id"), nullable=False, index=True)
    teaching_class_id: Mapped[str] = mapped_column(String(50), ForeignKey("teaching_class.id"), nullable=False, index=True)
    status: Mapped[StudentClassStatus] = mapped_column(
        String(20),
        nullable=False,
        default=StudentClassStatus.ACTIVE,
    )
    joined_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
    created_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[DateTime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    student: Mapped["Student"] = relationship("Student", back_populates="student_classes")  # noqa
    teaching_class: Mapped["TeachingClass"] = relationship("TeachingClass", back_populates="student_classes")  # noqa

    def __repr__(self):
        return f"<StudentClass(student_id='{self.student_id}', teaching_class_id='{self.teaching_class_id}')>"
```

- [ ] **Step 2: 更新 Student 模型关系**

在 `app/models/student.py` 中添加：

```python
student_classes: Mapped[list["StudentClass"]] = relationship("StudentClass", back_populates="student")  # noqa
```

- [ ] **Step 3: 更新 TeachingClass 模型关系**

在 `app/models/teaching_class.py` 中添加：

```python
student_classes: Mapped[list["StudentClass"]] = relationship("StudentClass", back_populates="teaching_class")  # noqa
```

- [ ] **Step 4: 更新 __init__.py**

```python
# app/models/__init__.py
from app.models.student_class import StudentClass, StudentClassStatus

__all__ = ["StudentClass", "StudentClassStatus"]
```

- [ ] **Step 5: 创建数据库迁移**

运行：`alembic revision --autogenerate -m "add student_class table"`

验证迁移文件包含 StudentClass 表定义

- [ ] **Step 6: 应用迁移**

运行：`alembic upgrade head`

验证数据库中存在 student_class 表

- [ ] **Step 7: 提交**

```bash
git add app/models/student_class.py app/models/student.py app/models/teaching_class.py app/models/__init__.py alembic/versions/
git commit -m "feat: add StudentClass model for student-class relationship"
```

---

### Task 2: 创建 StudentClass Schema

**文件：**
- Create: `app/schemas/student_class.py`

- [ ] **Step 1: 编写 StudentClass Schema**

```python
# app/schemas/student_class.py
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
    """学生加入班级的响应"""
    id: str
    teaching_class_id: str
    class_name: str
    teacher_name: str
    joined_at: datetime
    status: str

    model_config = ConfigDict(from_attributes=True)
```

- [ ] **Step 2: 提交**

```bash
git add app/schemas/student_class.py
git commit -m "feat: add StudentClass schemas"
```

---

### Task 3: 创建 StudentClass 仓储层

**文件：**
- Create: `app/repositories/student_class_repo.py`

- [ ] **Step 1: 编写 StudentClassRepository**

```python
# app/repositories/student_class_repo.py
from typing import Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.student_class import StudentClass, StudentClassStatus
from app.models.teaching_class import TeachingClass
from app.models.teacher import Teacher
from app.models.user import User


class StudentClassRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, id: str) -> Optional[StudentClass]:
        """按 ID 获取学生班级关系"""
        result = await self.db.execute(select(StudentClass).where(StudentClass.id == id))
        return result.scalars().first()

    async def get_by_student_and_class(self, student_id: str, teaching_class_id: str) -> Optional[StudentClass]:
        """按学生 ID 和班级 ID 获取关系"""
        result = await self.db.execute(
            select(StudentClass).where(
                and_(
                    StudentClass.student_id == student_id,
                    StudentClass.teaching_class_id == teaching_class_id,
                )
            )
        )
        return result.scalars().first()

    async def list_by_student(self, student_id: str, skip: int = 0, limit: int = 20) -> tuple[list[StudentClass], int]:
        """获取学生加入的所有班级"""
        # 获取总数
        count_result = await self.db.execute(
            select(StudentClass).where(StudentClass.student_id == student_id)
        )
        total = len(count_result.scalars().all())

        # 获取分页数据
        result = await self.db.execute(
            select(StudentClass)
            .where(StudentClass.student_id == student_id)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all(), total

    async def create(self, student_id: str, teaching_class_id: str) -> StudentClass:
        """创建学生班级关系"""
        student_class = StudentClass(
            student_id=student_id,
            teaching_class_id=teaching_class_id,
            status=StudentClassStatus.ACTIVE,
        )
        self.db.add(student_class)
        await self.db.flush()
        return student_class

    async def update(self, id: str, status: str) -> Optional[StudentClass]:
        """更新学生班级关系状态"""
        student_class = await self.get(id)
        if not student_class:
            return None
        student_class.status = status
        await self.db.flush()
        return student_class

    async def delete(self, id: str) -> bool:
        """删除学生班级关系"""
        student_class = await self.get(id)
        if not student_class:
            return False
        await self.db.delete(student_class)
        await self.db.flush()
        return True

    async def get_class_info_with_teacher(self, student_class_id: str) -> Optional[dict]:
        """获取班级信息及教师信息（用于加入班级响应）"""
        result = await self.db.execute(
            select(StudentClass, TeachingClass, Teacher, User).join(
                TeachingClass, StudentClass.teaching_class_id == TeachingClass.id
            ).join(
                Teacher, TeachingClass.teacher_id == Teacher.id
            ).join(
                User, Teacher.user_id == User.id
            ).where(StudentClass.id == student_class_id)
        )
        row = result.first()
        if not row:
            return None
        student_class, teaching_class, teacher, user = row
        return {
            "student_class": student_class,
            "teaching_class": teaching_class,
            "teacher_name": user.name,
        }
```

- [ ] **Step 2: 提交**

```bash
git add app/repositories/student_class_repo.py
git commit -m "feat: add StudentClassRepository"
```

---

### Task 4: 创建 StudentClass 服务层

**文件：**
- Create: `app/services/student_class_service.py`

- [ ] **Step 1: 编写 StudentClassService**

```python
# app/services/student_class_service.py
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.student_class_repo import StudentClassRepository
from app.repositories.teaching_class_repo import TeachingClassRepository
from app.schemas.student_class import StudentClassResponse, StudentClassListResponse, StudentClassJoinResponse


class StudentClassService:
    def __init__(self, db: AsyncSession):
        self.repo = StudentClassRepository(db)
        self.teaching_class_repo = TeachingClassRepository(db)

    async def join_class(self, student_id: str, teaching_class_id: str) -> StudentClassJoinResponse:
        """学生加入班级"""
        # 检查学生是否已加入
        existing = await self.repo.get_by_student_and_class(student_id, teaching_class_id)
        if existing:
            raise ValueError("学生已加入该班级")

        # 检查班级是否存在
        teaching_class = await self.teaching_class_repo.get(teaching_class_id)
        if not teaching_class:
            raise ValueError("班级不存在")

        # 创建关系
        student_class = await self.repo.create(student_id, teaching_class_id)
        await self.repo.db.commit()

        # 获取完整信息
        info = await self.repo.get_class_info_with_teacher(student_class.id)
        return StudentClassJoinResponse(
            id=student_class.id,
            teaching_class_id=info["teaching_class"].id,
            class_name=info["teaching_class"].name,
            teacher_name=info["teacher_name"],
            joined_at=student_class.joined_at,
            status=student_class.status,
        )

    async def list_student_classes(self, student_id: str, skip: int = 0, limit: int = 20) -> StudentClassListResponse:
        """获取学生加入的班级列表"""
        student_classes, total = await self.repo.list_by_student(student_id, skip, limit)
        items = [StudentClassResponse.model_validate(sc) for sc in student_classes]
        return StudentClassListResponse(total=total, items=items)

    async def get_student_class(self, student_class_id: str) -> Optional[StudentClassResponse]:
        """获取学生班级关系详情"""
        student_class = await self.repo.get(student_class_id)
        return StudentClassResponse.model_validate(student_class) if student_class else None
```

- [ ] **Step 2: 提交**

```bash
git add app/services/student_class_service.py
git commit -m "feat: add StudentClassService"
```

---

### Task 5: 创建学生班级路由 - 加入班级接口

**文件：**
- Create: `app/api/v1/routes_student_classes.py`
- Modify: `app/main.py`

- [ ] **Step 1: 编写加入班级接口测试**

```python
# tests/test_student_classes.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.student import Student
from app.models.teacher import Teacher
from app.models.teaching_class import TeachingClass
from app.models.user import User
from app.models.management_system import ManagementSystem
from app.core.database import AsyncSessionLocal


@pytest.fixture
async def setup_test_data():
    """设置测试数据"""
    async with AsyncSessionLocal() as db:
        # 创建管理系统
        ms = ManagementSystem(name="test_system")
        db.add(ms)
        await db.flush()

        # 创建用户
        student_user = User(name="student1", email="student1@test.com")
        teacher_user = User(name="teacher1", email="teacher1@test.com")
        db.add_all([student_user, teacher_user])
        await db.flush()

        # 创建学生和教师
        student = Student(user_id=student_user.id, name="student1")
        teacher = Teacher(user_id=teacher_user.id, name="teacher1", management_system_id=ms.id)
        db.add_all([student, teacher])
        await db.flush()

        # 创建班级
        teaching_class = TeachingClass(
            management_system_id=ms.id,
            teacher_id=teacher.id,
            name="test_class",
        )
        db.add(teaching_class)
        await db.commit()

        return {
            "student_id": student.id,
            "teacher_id": teacher.id,
            "teaching_class_id": teaching_class.id,
            "student_user_id": student_user.id,
        }


@pytest.mark.asyncio
async def test_join_class_success(setup_test_data):
    """测试学生成功加入班级"""
    data = await setup_test_data
    
    client = TestClient(app)
    response = client.post(
        f"/api/v1/students/me/join-class",
        json={"teaching_class_id": data["teaching_class_id"]},
        headers={"Authorization": f"Bearer {data['student_user_id']}"},
    )
    
    assert response.status_code == 201
    result = response.json()
    assert result["teaching_class_id"] == data["teaching_class_id"]
    assert result["status"] == "active"


@pytest.mark.asyncio
async def test_join_class_duplicate(setup_test_data):
    """测试学生重复加入班级"""
    data = await setup_test_data
    
    client = TestClient(app)
    # 第一次加入
    client.post(
        f"/api/v1/students/me/join-class",
        json={"teaching_class_id": data["teaching_class_id"]},
        headers={"Authorization": f"Bearer {data['student_user_id']}"},
    )
    
    # 第二次加入应该失败
    response = client.post(
        f"/api/v1/students/me/join-class",
        json={"teaching_class_id": data["teaching_class_id"]},
        headers={"Authorization": f"Bearer {data['student_user_id']}"},
    )
    
    assert response.status_code == 409
```

- [ ] **Step 2: 运行测试验证失败**

运行：`pytest tests/test_student_classes.py::test_join_class_success -v`

预期：FAIL - 路由不存在

- [ ] **Step 3: 编写加入班级接口**

```python
# app/api/v1/routes_student_classes.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_student
from app.core.database import get_db
from app.models.student import Student
from app.schemas.student_class import StudentClassJoinResponse
from app.services.student_class_service import StudentClassService


router = APIRouter()


@router.post("/me/join-class", response_model=StudentClassJoinResponse, status_code=status.HTTP_201_CREATED)
async def join_class(
    body: dict,
    current_student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """
    学生加入班级
    
    参数：
        body: {"teaching_class_id": "string"}
        current_student: 当前学生
        db: 数据库会话
    
    返回：
        StudentClassJoinResponse
    """
    teaching_class_id = body.get("teaching_class_id")
    if not teaching_class_id:
        raise HTTPException(status_code=400, detail="teaching_class_id 不能为空")
    
    try:
        return await StudentClassService(db).join_class(current_student.id, teaching_class_id)
    except ValueError as exc:
        if "已加入" in str(exc):
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        raise HTTPException(status_code=404, detail=str(exc)) from exc
```

- [ ] **Step 4: 在 main.py 中注册路由**

在 `app/main.py` 的 ROUTER_CONFIGS 中添加：

```python
(routes_student_classes.router, f"{settings.API_V1_STR}/students", ["student-classes"]),
```

并在导入部分添加：

```python
from app.api.v1 import routes_student_classes
```

- [ ] **Step 5: 运行测试验证通过**

运行：`pytest tests/test_student_classes.py::test_join_class_success -v`

预期：PASS

- [ ] **Step 6: 运行所有加入班级测试**

运行：`pytest tests/test_student_classes.py -k join_class -v`

预期：所有测试通过

- [ ] **Step 7: 提交**

```bash
git add app/api/v1/routes_student_classes.py app/main.py tests/test_student_classes.py
git commit -m "feat: add join-class endpoint for students"
```

---

### Task 6: 创建学生班级路由 - 查看班级列表接口

**文件：**
- Modify: `app/api/v1/routes_student_classes.py`
- Modify: `tests/test_student_classes.py`

- [ ] **Step 1: 编写查看班级列表测试**

在 `tests/test_student_classes.py` 中添加：

```python
@pytest.mark.asyncio
async def test_list_student_classes(setup_test_data):
    """测试查看学生加入的班级列表"""
    data = await setup_test_data
    
    client = TestClient(app)
    # 先加入班级
    client.post(
        f"/api/v1/students/me/join-class",
        json={"teaching_class_id": data["teaching_class_id"]},
        headers={"Authorization": f"Bearer {data['student_user_id']}"},
    )
    
    # 查看班级列表
    response = client.get(
        "/api/v1/students/me/classes",
        headers={"Authorization": f"Bearer {data['student_user_id']}"},
    )
    
    assert response.status_code == 200
    result = response.json()
    assert result["total"] == 1
    assert len(result["items"]) == 1
    assert result["items"][0]["teaching_class_id"] == data["teaching_class_id"]
```

- [ ] **Step 2: 运行测试验证失败**

运行：`pytest tests/test_student_classes.py::test_list_student_classes -v`

预期：FAIL

- [ ] **Step 3: 实现查看班级列表接口**

在 `app/api/v1/routes_student_classes.py` 中添加：

```python
from typing import Optional
from fastapi import Query

@router.get("/me/classes")
async def list_student_classes(
    skip: Optional[int] = Query(0, ge=0),
    limit: Optional[int] = Query(20, ge=1, le=100),
    current_student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """
    查看学生加入的班级列表
    
    参数：
        skip: 分页偏移量
        limit: 每页数量
        current_student: 当前学生
        db: 数据库会话
    
    返回：
        班级列表
    """
    return await StudentClassService(db).list_student_classes(current_student.id, skip, limit)
```

- [ ] **Step 4: 运行测试验证通过**

运行：`pytest tests/test_student_classes.py::test_list_student_classes -v`

预期：PASS

- [ ] **Step 5: 提交**

```bash
git add app/api/v1/routes_student_classes.py tests/test_student_classes.py
git commit -m "feat: add list-classes endpoint for students"
```

---

### Task 7: 创建学生班级路由 - 查看班级详情接口

**文件：**
- Modify: `app/api/v1/routes_student_classes.py`
- Modify: `app/services/student_class_service.py`
- Modify: `tests/test_student_classes.py`

- [ ] **Step 1: 扩展 StudentClassService 获取班级详情**

在 `app/services/student_class_service.py` 中添加方法：

```python
async def get_class_detail(self, student_id: str, teaching_class_id: str) -> dict:
    """获取班级详情（需要验证学生已加入）"""
    # 验证学生已加入班级
    student_class = await self.repo.get_by_student_and_class(student_id, teaching_class_id)
    if not student_class:
        raise ValueError("学生未加入该班级")
    
    # 获取班级信息
    teaching_class = await self.teaching_class_repo.get(teaching_class_id)
    if not teaching_class:
        raise ValueError("班级不存在")
    
    # 获取教师信息
    teacher = await self.teaching_class_repo.db.execute(
        select(Teacher).where(Teacher.id == teaching_class.teacher_id)
    )
    teacher_obj = teacher.scalars().first()
    
    # 获取教师用户信息
    user = await self.teaching_class_repo.db.execute(
        select(User).where(User.id == teacher_obj.user_id)
    )
    user_obj = user.scalars().first()
    
    return {
        "id": teaching_class.id,
        "name": teaching_class.name,
        "description": teaching_class.description,
        "teacher_id": teacher_obj.id,
        "teacher_name": user_obj.name,
        "member_count": 0,  # TODO: 从数据库查询
        "assignment_count": 0,  # TODO: 从数据库查询
        "joined_at": student_class.joined_at,
        "status": student_class.status,
    }
```

- [ ] **Step 2: 编写查看班级详情测试**

在 `tests/test_student_classes.py` 中添加：

```python
@pytest.mark.asyncio
async def test_get_class_detail(setup_test_data):
    """测试查看班级详情"""
    data = await setup_test_data
    
    client = TestClient(app)
    # 先加入班级
    client.post(
        f"/api/v1/students/me/join-class",
        json={"teaching_class_id": data["teaching_class_id"]},
        headers={"Authorization": f"Bearer {data['student_user_id']}"},
    )
    
    # 查看班级详情
    response = client.get(
        f"/api/v1/students/me/classes/{data['teaching_class_id']}",
        headers={"Authorization": f"Bearer {data['student_user_id']}"},
    )
    
    assert response.status_code == 200
    result = response.json()
    assert result["id"] == data["teaching_class_id"]
    assert result["name"] == "test_class"


@pytest.mark.asyncio
async def test_get_class_detail_not_joined(setup_test_data):
    """测试查看未加入班级的详情应该失败"""
    data = await setup_test_data
    
    client = TestClient(app)
    response = client.get(
        f"/api/v1/students/me/classes/{data['teaching_class_id']}",
        headers={"Authorization": f"Bearer {data['student_user_id']}"},
    )
    
    assert response.status_code == 403
```

- [ ] **Step 3: 运行测试验证失败**

运行：`pytest tests/test_student_classes.py::test_get_class_detail -v`

预期：FAIL

- [ ] **Step 4: 实现查看班级详情接口**

在 `app/api/v1/routes_student_classes.py` 中添加：

```python
@router.get("/me/classes/{class_id}")
async def get_class_detail(
    class_id: str,
    current_student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """
    查看班级详情
    
    参数：
        class_id: 班级 ID
        current_student: 当前学生
        db: 数据库会话
    
    返回：
        班级详情
    """
    try:
        return await StudentClassService(db).get_class_detail(current_student.id, class_id)
    except ValueError as exc:
        if "未加入" in str(exc):
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        raise HTTPException(status_code=404, detail=str(exc)) from exc
```

- [ ] **Step 5: 运行测试验证通过**

运行：`pytest tests/test_student_classes.py -k "test_get_class_detail" -v`

预期：所有测试通过

- [ ] **Step 6: 提交**

```bash
git add app/api/v1/routes_student_classes.py app/services/student_class_service.py tests/test_student_classes.py
git commit -m "feat: add get-class-detail endpoint for students"
```

---

### Task 8: 创建学生班级路由 - 查看班级成员接口

**文件：**
- Modify: `app/api/v1/routes_student_classes.py`
- Modify: `app/services/student_class_service.py`

- [ ] **Step 1: 扩展 StudentClassService 获取班级成员**

在 `app/services/student_class_service.py` 中添加方法：

```python
async def get_class_members(self, student_id: str, teaching_class_id: str, skip: int = 0, limit: int = 20) -> dict:
    """获取班级成员列表（需要验证学生已加入）"""
    # 验证学生已加入班级
    student_class = await self.repo.get_by_student_and_class(student_id, teaching_class_id)
    if not student_class:
        raise ValueError("学生未加入该班级")
    
    # 获取班级成员
    from sqlalchemy import select
    from app.models.student_class import StudentClass
    from app.models.student import Student
    from app.models.user import User
    
    result = await self.repo.db.execute(
        select(Student, User).join(
            StudentClass, Student.id == StudentClass.student_id
        ).join(
            User, Student.user_id == User.id
        ).where(StudentClass.teaching_class_id == teaching_class_id)
        .offset(skip)
        .limit(limit)
    )
    
    members = []
    for student, user in result:
        members.append({
            "id": student.id,
            "name": user.name,
            "joined_at": student.created_at,
        })
    
    # 获取总数
    count_result = await self.repo.db.execute(
        select(StudentClass).where(StudentClass.teaching_class_id == teaching_class_id)
    )
    total = len(count_result.scalars().all())
    
    return {"total": total, "items": members}
```

- [ ] **Step 2: 实现查看班级成员接口**

在 `app/api/v1/routes_student_classes.py` 中添加：

```python
@router.get("/me/classes/{class_id}/members")
async def get_class_members(
    class_id: str,
    skip: Optional[int] = Query(0, ge=0),
    limit: Optional[int] = Query(20, ge=1, le=100),
    current_student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """
    查看班级成员列表
    
    参数：
        class_id: 班级 ID
        skip: 分页偏移量
        limit: 每页数量
        current_student: 当前学生
        db: 数据库会话
    
    返回：
        班级成员列表
    """
    try:
        return await StudentClassService(db).get_class_members(current_student.id, class_id, skip, limit)
    except ValueError as exc:
        if "未加入" in str(exc):
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        raise HTTPException(status_code=404, detail=str(exc)) from exc
```

- [ ] **Step 3: 编写测试**

在 `tests/test_student_classes.py` 中添加：

```python
@pytest.mark.asyncio
async def test_get_class_members(setup_test_data):
    """测试查看班级成员列表"""
    data = await setup_test_data
    
    client = TestClient(app)
    # 先加入班级
    client.post(
        f"/api/v1/students/me/join-class",
        json={"teaching_class_id": data["teaching_class_id"]},
        headers={"Authorization": f"Bearer {data['student_user_id']}"},
    )
    
    # 查看班级成员
    response = client.get(
        f"/api/v1/students/me/classes/{data['teaching_class_id']}/members",
        headers={"Authorization": f"Bearer {data['student_user_id']}"},
    )
    
    assert response.status_code == 200
    result = response.json()
    assert result["total"] >= 1
    assert len(result["items"]) >= 1
```

- [ ] **Step 4: 运行测试验证通过**

运行：`pytest tests/test_student_classes.py::test_get_class_members -v`

预期：PASS

- [ ] **Step 5: 提交**

```bash
git add app/api/v1/routes_student_classes.py app/services/student_class_service.py tests/test_student_classes.py
git commit -m "feat: add get-class-members endpoint for students"
```

---

### Task 9: 创建作业查看接口 - 查看班级作业列表

**文件：**
- Modify: `app/api/v1/routes_student_classes.py`
- Modify: `app/services/student_class_service.py`

- [ ] **Step 1: 扩展 StudentClassService 获取班级作业**

在 `app/services/student_class_service.py` 中添加方法：

```python
async def get_class_assignments(self, student_id: str, teaching_class_id: str, status: Optional[str] = None, skip: int = 0, limit: int = 20) -> dict:
    """获取班级作业列表"""
    # 验证学生已加入班级
    student_class = await self.repo.get_by_student_and_class(student_id, teaching_class_id)
    if not student_class:
        raise ValueError("学生未加入该班级")
    
    from sqlalchemy import select, and_
    from app.models.assignment import Assignment
    from app.models.submission import Submission
    
    # 构建查询
    query = select(Assignment).where(Assignment.teaching_class_id == teaching_class_id)
    
    # 获取总数
    count_result = await self.repo.db.execute(query)
    total = len(count_result.scalars().all())
    
    # 获取分页数据
    result = await self.repo.db.execute(
        query.order_by(Assignment.deadline).offset(skip).limit(limit)
    )
    assignments = result.scalars().all()
    
    # 获取学生的提交状态
    items = []
    for assignment in assignments:
        submission_result = await self.repo.db.execute(
            select(Submission).where(
                and_(
                    Submission.assignment_id == assignment.id,
                    Submission.student_id == student_id,
                )
            )
        )
        submission = submission_result.scalars().first()
        
        submission_status = "not_submitted"
        submission_id = None
        if submission:
            submission_status = "graded" if submission.graded_at else "submitted"
            submission_id = submission.id
        
        items.append({
            "id": assignment.id,
            "title": assignment.title,
            "description": assignment.description,
            "deadline": assignment.deadline,
            "created_at": assignment.created_at,
            "submission_status": submission_status,
            "submission_id": submission_id,
        })
    
    return {"total": total, "items": items}
```

- [ ] **Step 2: 实现查看班级作业列表接口**

在 `app/api/v1/routes_student_classes.py` 中添加：

```python
@router.get("/me/classes/{class_id}/assignments")
async def get_class_assignments(
    class_id: str,
    status: Optional[str] = Query(None),
    sort_by: Optional[str] = Query("deadline"),
    skip: Optional[int] = Query(0, ge=0),
    limit: Optional[int] = Query(20, ge=1, le=100),
    current_student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """
    查看班级作业列表
    
    参数：
        class_id: 班级 ID
        status: 筛选状态 (not_submitted|submitted|graded)
        sort_by: 排序字段 (deadline|created_at)
        skip: 分页偏移量
        limit: 每页数量
        current_student: 当前学生
        db: 数据库会话
    
    返回：
        班级作业列表
    """
    try:
        return await StudentClassService(db).get_class_assignments(current_student.id, class_id, status, skip, limit)
    except ValueError as exc:
        if "未加入" in str(exc):
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        raise HTTPException(status_code=404, detail=str(exc)) from exc
```

- [ ] **Step 3: 编写测试**

在 `tests/test_student_classes.py` 中添加：

```python
@pytest.mark.asyncio
async def test_get_class_assignments(setup_test_data):
    """测试查看班级作业列表"""
    data = await setup_test_data
    
    client = TestClient(app)
    # 先加入班级
    client.post(
        f"/api/v1/students/me/join-class",
        json={"teaching_class_id": data["teaching_class_id"]},
        headers={"Authorization": f"Bearer {data['student_user_id']}"},
    )
    
    # 查看班级作业
    response = client.get(
        f"/api/v1/students/me/classes/{data['teaching_class_id']}/assignments",
        headers={"Authorization": f"Bearer {data['student_user_id']}"},
    )
    
    assert response.status_code == 200
    result = response.json()
    assert "total" in result
    assert "items" in result
```

- [ ] **Step 4: 运行测试验证通过**

运行：`pytest tests/test_student_classes.py::test_get_class_assignments -v`

预期：PASS

- [ ] **Step 5: 提交**

```bash
git add app/api/v1/routes_student_classes.py app/services/student_class_service.py tests/test_student_classes.py
git commit -m "feat: add get-class-assignments endpoint for students"
```

---

### Task 10: 创建作业详情接口

**文件：**
- Modify: `app/api/v1/routes_student_classes.py`
- Modify: `app/services/student_class_service.py`

- [ ] **Step 1: 扩展 StudentClassService 获取作业详情**

在 `app/services/student_class_service.py` 中添加方法：

```python
async def get_assignment_detail(self, student_id: str, assignment_id: str) -> dict:
    """获取作业详情（需要验证学生已加入该班级）"""
    from sqlalchemy import select
    from app.models.assignment import Assignment
    from app.models.submission import Submission
    
    # 获取作业
    assignment_result = await self.repo.db.execute(
        select(Assignment).where(Assignment.id == assignment_id)
    )
    assignment = assignment_result.scalars().first()
    if not assignment:
        raise ValueError("作业不存在")
    
    # 验证学生已加入班级
    student_class = await self.repo.get_by_student_and_class(student_id, assignment.teaching_class_id)
    if not student_class:
        raise ValueError("学生未加入该班级")
    
    # 获取学生的提交
    submission_result = await self.repo.db.execute(
        select(Submission).where(
            and_(
                Submission.assignment_id == assignment_id,
                Submission.student_id == student_id,
            )
        )
    )
    submission = submission_result.scalars().first()
    
    submission_data = None
    if submission:
        submission_data = {
            "id": submission.id,
            "status": "graded" if submission.graded_at else "submitted",
            "submitted_at": submission.submitted_at,
            "content": submission.content,
            "score": submission.score,
        }
    
    return {
        "id": assignment.id,
        "title": assignment.title,
        "description": assignment.description,
        "requirements": assignment.requirements,
        "deadline": assignment.deadline,
        "created_at": assignment.created_at,
        "attachments": [],  # TODO: 获取附件
        "submission": submission_data,
    }
```

- [ ] **Step 2: 实现作业详情接口**

在 `app/api/v1/routes_student_classes.py` 中添加：

```python
@router.get("/me/assignments/{assignment_id}")
async def get_assignment_detail(
    assignment_id: str,
    current_student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """
    查看作业详情
    
    参数：
        assignment_id: 作业 ID
        current_student: 当前学生
        db: 数据库会话
    
    返回：
        作业详情
    """
    try:
        return await StudentClassService(db).get_assignment_detail(current_student.id, assignment_id)
    except ValueError as exc:
        if "未加入" in str(exc):
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        raise HTTPException(status_code=404, detail=str(exc)) from exc
```

- [ ] **Step 3: 编写测试并验证通过**

运行：`pytest tests/test_student_classes.py -k assignment -v`

预期：所有测试通过

- [ ] **Step 4: 提交**

```bash
git add app/api/v1/routes_student_classes.py app/services/student_class_service.py tests/test_student_classes.py
git commit -m "feat: add get-assignment-detail endpoint for students"
```

---

### Task 11: 创建提交查看接口

**文件：**
- Modify: `app/api/v1/routes_student_classes.py`
- Modify: `app/services/student_class_service.py`

- [ ] **Step 1: 扩展 StudentClassService 获取提交列表和详情**

在 `app/services/student_class_service.py` 中添加方法：

```python
async def get_student_submissions(self, student_id: str, class_id: Optional[str] = None, skip: int = 0, limit: int = 20) -> dict:
    """获取学生的提交列表"""
    from sqlalchemy import select
    from app.models.submission import Submission
    from app.models.assignment import Assignment
    
    query = select(Submission).where(Submission.student_id == student_id)
    
    if class_id:
        # 如果指定班级，需要验证学生已加入
        student_class = await self.repo.get_by_student_and_class(student_id, class_id)
        if not student_class:
            raise ValueError("学生未加入该班级")
        
        # 只查询该班级的提交
        query = query.join(Assignment).where(Assignment.teaching_class_id == class_id)
    
    # 获取总数
    count_result = await self.repo.db.execute(query)
    total = len(count_result.scalars().all())
    
    # 获取分页数据
    result = await self.repo.db.execute(query.offset(skip).limit(limit))
    submissions = result.scalars().all()
    
    items = []
    for submission in submissions:
        # 获取作业信息
        assignment_result = await self.repo.db.execute(
            select(Assignment).where(Assignment.id == submission.assignment_id)
        )
        assignment = assignment_result.scalars().first()
        
        items.append({
            "id": submission.id,
            "assignment_id": submission.assignment_id,
            "assignment_title": assignment.title if assignment else "",
            "class_name": "",  # TODO: 获取班级名称
            "submitted_at": submission.submitted_at,
            "status": "graded" if submission.graded_at else "submitted",
            "score": submission.score,
        })
    
    return {"total": total, "items": items}

async def get_submission_detail(self, student_id: str, submission_id: str) -> dict:
    """获取提交详情（需要验证是学生自己的提交）"""
    from sqlalchemy import select
    from app.models.submission import Submission
    from app.models.assignment import Assignment
    
    # 获取提交
    submission_result = await self.repo.db.execute(
        select(Submission).where(Submission.id == submission_id)
    )
    submission = submission_result.scalars().first()
    if not submission:
        raise ValueError("提交不存在")
    
    # 验证是学生自己的提交
    if submission.student_id != student_id:
        raise ValueError("无权限访问")
    
    # 获取作业信息
    assignment_result = await self.repo.db.execute(
        select(Assignment).where(Assignment.id == submission.assignment_id)
    )
    assignment = assignment_result.scalars().first()
    
    return {
        "id": submission.id,
        "assignment_id": submission.assignment_id,
        "assignment_title": assignment.title if assignment else "",
        "class_name": "",  # TODO: 获取班级名称
        "submitted_at": submission.submitted_at,
        "status": "graded" if submission.graded_at else "submitted",
        "content": submission.content,
        "attachments": [],  # TODO: 获取附件
        "score": submission.score,
        "graded_at": submission.graded_at,
    }
```

- [ ] **Step 2: 实现提交查看接口**

在 `app/api/v1/routes_student_classes.py` 中添加：

```python
@router.get("/me/submissions")
async def get_student_submissions(
    class_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    skip: Optional[int] = Query(0, ge=0),
    limit: Optional[int] = Query(20, ge=1, le=100),
    current_student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """
    查看学生的提交列表
    
    参数：
        class_id: 班级 ID（可选）
        status: 提交状态（可选）
        skip: 分页偏移量
        limit: 每页数量
        current_student: 当前学生
        db: 数据库会话
    
    返回：
        提交列表
    """
    try:
        return await StudentClassService(db).get_student_submissions(current_student.id, class_id, skip, limit)
    except ValueError as exc:
        if "未加入" in str(exc):
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/me/submissions/{submission_id}")
async def get_submission_detail(
    submission_id: str,
    current_student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """
    查看提交详情
    
    参数：
        submission_id: 提交 ID
        current_student: 当前学生
        db: 数据库会话
    
    返回：
        提交详情
    """
    try:
        return await StudentClassService(db).get_submission_detail(current_student.id, submission_id)
    except ValueError as exc:
        if "无权限" in str(exc):
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        raise HTTPException(status_code=404, detail=str(exc)) from exc
```

- [ ] **Step 3: 编写测试并验证通过**

运行：`pytest tests/test_student_classes.py -k submission -v`

预期：所有测试通过

- [ ] **Step 4: 提交**

```bash
git add app/api/v1/routes_student_classes.py app/services/student_class_service.py tests/test_student_classes.py
git commit -m "feat: add submission-related endpoints for students"
```

---

### Task 12: 创建反馈查看接口

**文件：**
- Modify: `app/api/v1/routes_student_classes.py`
- Modify: `app/services/student_class_service.py`

- [ ] **Step 1: 扩展 StudentClassService 获取反馈**

在 `app/services/student_class_service.py` 中添加方法：

```python
async def get_ai_feedback(self, student_id: str, submission_id: str) -> dict:
    """获取 AI 反馈"""
    from sqlalchemy import select
    from app.models.submission import Submission
    from app.models.ai_feedback import AIFeedback
    
    # 获取提交
    submission_result = await self.repo.db.execute(
        select(Submission).where(Submission.id == submission_id)
    )
    submission = submission_result.scalars().first()
    if not submission:
        raise ValueError("提交不存在")
    
    # 验证是学生自己的提交
    if submission.student_id != student_id:
        raise ValueError("无权限访问")
    
    # 获取 AI 反馈
    feedback_result = await self.repo.db.execute(
        select(AIFeedback).where(AIFeedback.submission_id == submission_id)
    )
    feedback = feedback_result.scalars().first()
    if not feedback:
        raise ValueError("反馈不存在")
    
    return {
        "id": feedback.id,
        "submission_id": feedback.submission_id,
        "feedback": feedback.feedback,
        "created_at": feedback.created_at,
        "model": feedback.model,
    }

async def get_teacher_feedback(self, student_id: str, submission_id: str) -> dict:
    """获取教师反馈"""
    from sqlalchemy import select
    from app.models.submission import Submission
    from app.models.teacher_feedback import TeacherFeedback
    
    # 获取提交
    submission_result = await self.repo.db.execute(
        select(Submission).where(Submission.id == submission_id)
    )
    submission = submission_result.scalars().first()
    if not submission:
        raise ValueError("提交不存在")
    
    # 验证是学生自己的提交
    if submission.student_id != student_id:
        raise ValueError("无权限访问")
    
    # 获取教师反馈
    feedback_result = await self.repo.db.execute(
        select(TeacherFeedback).where(TeacherFeedback.submission_id == submission_id)
    )
    feedback = feedback_result.scalars().first()
    if not feedback:
        raise ValueError("反馈不存在")
    
    return {
        "id": feedback.id,
        "submission_id": feedback.submission_id,
        "feedback": feedback.feedback,
        "score": feedback.score,
        "graded_at": feedback.graded_at,
        "teacher_name": "",  # TODO: 获取教师名称
    }
```

- [ ] **Step 2: 实现反馈查看接口**

在 `app/api/v1/routes_student_classes.py` 中添加：

```python
@router.get("/me/submissions/{submission_id}/ai-feedback")
async def get_ai_feedback(
    submission_id: str,
    current_student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """
    查看 AI 反馈
    
    参数：
        submission_id: 提交 ID
        current_student: 当前学生
        db: 数据库会话
    
    返回：
        AI 反馈
    """
    try:
        return await StudentClassService(db).get_ai_feedback(current_student.id, submission_id)
    except ValueError as exc:
        if "无权限" in str(exc):
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/me/submissions/{submission_id}/teacher-feedback")
async def get_teacher_feedback(
    submission_id: str,
    current_student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """
    查看教师反馈
    
    参数：
        submission_id: 提交 ID
        current_student: 当前学生
        db: 数据库会话
    
    返回：
        教师反馈
    """
    try:
        return await StudentClassService(db).get_teacher_feedback(current_student.id, submission_id)
    except ValueError as exc:
        if "无权限" in str(exc):
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        raise HTTPException(status_code=404, detail=str(exc)) from exc
```

- [ ] **Step 3: 编写测试并验证通过**

运行：`pytest tests/test_student_classes.py -k feedback -v`

预期：所有测试通过

- [ ] **Step 4: 提交**

```bash
git add app/api/v1/routes_student_classes.py app/services/student_class_service.py tests/test_student_classes.py
git commit -m "feat: add feedback-related endpoints for students"
```

---

## 第一阶段总结

完成了第一阶段的所有 12 个任务，实现了学生端的核心学习路径：
- ✅ 班级加入与查看（4 个接口）
- ✅ 作业与提交（4 个接口）
- ✅ 反馈查看（2 个接口）

**验证清单：**
- [ ] 所有单元测试通过
- [ ] 所有集成测试通过
- [ ] 完整学习路径可用
- [ ] 权限验证正确
- [ ] 错误处理完善

---

## 第二阶段：个人中心（后续实现）

第二阶段将实现个人中心功能，包括：
- 学习仪表板
- 作业汇总
- 反馈汇总

预期工作量：1 周

---

## 第三阶段：协作功能（后续实现）

第三阶段将集成现有的协作功能：
- 消息
- 评论
- 搜索

预期工作量：1 周
