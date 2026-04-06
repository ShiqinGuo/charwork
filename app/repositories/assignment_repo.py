from datetime import datetime
from typing import List, Optional
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.assignment import Assignment, AssignmentStatus
from app.schemas.assignment import AssignmentCreate, AssignmentUpdate


class AssignmentRepository:
    def __init__(self, db: AsyncSession):
        """
        功能描述：
            初始化AssignmentRepository并准备运行所需的依赖对象。

        参数：
            db (AsyncSession): 数据库会话，用于执行持久化操作。

        返回值：
            None: 无返回值。
        """
        self.db = db

    async def get(self, id: str, management_system_id: Optional[str] = None) -> Optional[Assignment]:
        """
        功能描述：
            获取AssignmentRepository。

        参数：
            id (str): 目标记录ID。
            management_system_id (Optional[str]): 管理系统ID，用于限制数据作用域。

        返回值：
            Optional[Assignment]: 返回处理结果对象；无可用结果时返回 None。
        """
        query = select(Assignment).where(Assignment.id == id)
        if management_system_id:
            query = query.where(Assignment.management_system_id == management_system_id)
        result = await self.db.execute(query)
        return result.scalars().first()

    async def get_all(self, skip: int = 0, limit: int = 100,
                      teacher_id: Optional[str] = None,
                      status: Optional[str] = None,
                      management_system_id: Optional[str] = None,
                      course_id: Optional[str] = None,
                      course_ids: Optional[List[str]] = None) -> List[Assignment]:
        """
        功能描述：
            按条件获取all。

        参数：
            skip (int): 分页偏移量。
            limit (int): 单次查询的最大返回数量。
            teacher_id (Optional[str]): 教师ID。
            status (Optional[str]): 状态筛选条件或目标状态。
            management_system_id (Optional[str]): 管理系统ID，用于限制数据作用域。
            course_id (Optional[str]): 课程ID。
            course_ids (Optional[List[str]]): 课程ID列表。

        返回值：
            List[Assignment]: 返回查询到的结果对象。
        """
        query = select(Assignment)
        if management_system_id:
            query = query.where(Assignment.management_system_id == management_system_id)
        if course_id:
            query = query.where(Assignment.course_id == course_id)
        elif course_ids is not None:
            if not course_ids:
                # 传入空课程集合时直接返回空结果，避免退化为“仅按其他条件”导致范围意外放大。
                return []
            query = query.where(Assignment.course_id.in_(course_ids))

        if teacher_id:
            query = query.where(Assignment.teacher_id == teacher_id)
        if status:
            query = query.where(Assignment.status == status)

        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def count(self, teacher_id: Optional[str] = None,
                    status: Optional[str] = None,
                    management_system_id: Optional[str] = None,
                    course_id: Optional[str] = None,
                    course_ids: Optional[List[str]] = None) -> int:
        """
        功能描述：
            统计AssignmentRepository。

        参数：
            teacher_id (Optional[str]): 教师ID。
            status (Optional[str]): 状态筛选条件或目标状态。
            management_system_id (Optional[str]): 管理系统ID，用于限制数据作用域。
            course_id (Optional[str]): 课程ID。
            course_ids (Optional[List[str]]): 课程ID列表。

        返回值：
            int: 返回int类型的处理结果。
        """
        query = select(func.count()).select_from(Assignment)
        if management_system_id:
            query = query.where(Assignment.management_system_id == management_system_id)
        if course_id:
            query = query.where(Assignment.course_id == course_id)
        elif course_ids is not None:
            if not course_ids:
                # 计数查询与列表查询保持相同短路语义，防止分页 total 与实际 items 不一致。
                return 0
            query = query.where(Assignment.course_id.in_(course_ids))

        if teacher_id:
            query = query.where(Assignment.teacher_id == teacher_id)
        if status:
            query = query.where(Assignment.status == status)

        result = await self.db.execute(query)
        return result.scalar()

    async def create(
        self,
        assignment_in: AssignmentCreate,
        teacher_id: str,
        management_system_id: str,
        course_id: Optional[str] = None,
    ) -> Assignment:
        """
        功能描述：
            创建AssignmentRepository。

        参数：
            assignment_in (AssignmentCreate): 作业输入对象。
            teacher_id (str): 教师ID。
            management_system_id (str): 管理系统ID，用于限制数据作用域。
            course_id (Optional[str]): 课程ID。

        返回值：
            Assignment: 返回Assignment类型的处理结果。
        """
        payload = assignment_in.model_dump()
        payload["hanzi_ids"] = payload.get("character_ids", [])
        payload.pop("character_ids", None)
        payload.pop("course_id", None)
        # 管理系统归属由作用域解析结果注入，禁止客户端透传覆盖以确保写入边界稳定。
        payload.pop("management_system_id", None)
        payload.pop("custom_field_values", None)
        assignment = Assignment(
            **payload,
            teacher_id=teacher_id,
            management_system_id=management_system_id,
            course_id=course_id,
        )
        self.db.add(assignment)
        await self.db.commit()
        await self.db.refresh(assignment)
        return assignment

    async def update(self, assignment: Assignment, assignment_in: AssignmentUpdate) -> Assignment:
        """
        功能描述：
            更新AssignmentRepository。

        参数：
            assignment (Assignment): Assignment 类型的数据。
            assignment_in (AssignmentUpdate): 作业输入对象。

        返回值：
            Assignment: 返回Assignment类型的处理结果。
        """
        update_data = assignment_in.model_dump(exclude_unset=True)
        if "character_ids" in update_data:
            update_data["hanzi_ids"] = update_data["character_ids"]
            update_data.pop("character_ids", None)
        # 更新场景同样丢弃外部管理系统字段，防止跨系统迁移被伪装成普通更新请求。
        update_data.pop("management_system_id", None)
        update_data.pop("custom_field_values", None)
        for key, value in update_data.items():
            setattr(assignment, key, value)

        await self.db.commit()
        await self.db.refresh(assignment)
        return assignment

    async def delete(self, assignment: Assignment) -> None:
        """
        功能描述：
            删除AssignmentRepository。

        参数：
            assignment (Assignment): Assignment 类型的数据。

        返回值：
            None: 无返回值。
        """
        await self.db.delete(assignment)
        await self.db.commit()

    async def commit_and_refresh(self, assignment: Assignment) -> None:
        """
        功能描述：
            处理andrefresh。

        参数：
            assignment (Assignment): Assignment 类型的数据。

        返回值：
            None: 无返回值。
        """
        await self.db.commit()
        await self.db.refresh(assignment)

    async def commit(self) -> None:
        """
        功能描述：
            处理AssignmentRepository。

        参数：
            无。

        返回值：
            None: 无返回值。
        """
        await self.db.commit()

    async def list_published_due(self, now: datetime, management_system_id: Optional[str] = None) -> List[Assignment]:
        """
        功能描述：
            按条件查询publisheddue列表。

        参数：
            now (datetime): datetime 类型的数据。
            management_system_id (Optional[str]): 管理系统ID，用于限制数据作用域。

        返回值：
            List[Assignment]: 返回列表或分页查询结果。
        """
        conditions = [
            Assignment.status == AssignmentStatus.PUBLISHED,
            Assignment.due_date.is_not(None),
            Assignment.due_date <= now,
        ]
        if management_system_id:
            conditions.append(Assignment.management_system_id == management_system_id)
        result = await self.db.execute(
            select(Assignment).where(and_(*conditions))
        )
        return result.scalars().all()
