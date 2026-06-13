from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assignment_reminder import (
    AssignmentReminderExecution,
    AssignmentReminderPlan,
    AssignmentReminderPlanStatus,
)


class AssignmentReminderRepository:
    def __init__(self, db: AsyncSession):
        """
        功能描述：
            初始化AssignmentReminderRepository并准备运行所需的依赖对象。

        参数：
            db (AsyncSession): 数据库会话，用于执行持久化操作。

        返回值：
            None: 无返回值。
        """
        self.db = db

    async def get_plan(self, id: str) -> AssignmentReminderPlan | None:
        """
        功能描述：
            按条件获取计划。

        参数：
            id (str): 目标记录ID。

        返回值：
            AssignmentReminderPlan | None: 返回查询到的结果对象；未命中时返回 None。
        """
        result = await self.db.execute(select(AssignmentReminderPlan).where(AssignmentReminderPlan.id == id))
        return result.scalars().first()

    async def list_plans(self, assignment_id: str) -> list[AssignmentReminderPlan]:
        """
        功能描述：
            按条件查询plans列表。

        参数：
            assignment_id (str): 作业ID。

        返回值：
            list[AssignmentReminderPlan]: 返回列表形式的结果数据。
        """
        result = await self.db.execute(
            select(AssignmentReminderPlan)
            .where(AssignmentReminderPlan.assignment_id == assignment_id)
            .order_by(AssignmentReminderPlan.sequence_no.asc(), AssignmentReminderPlan.remind_at.asc())
        )
        return result.scalars().all()

    async def count_plans(self, assignment_id: str) -> int:
        """
        功能描述：
            统计plans数量。

        参数：
            assignment_id (str): 作业ID。

        返回值：
            int: 返回统计结果。
        """
        result = await self.db.execute(
            select(func.count()).select_from(AssignmentReminderPlan).where(
                AssignmentReminderPlan.assignment_id == assignment_id
            )
        )
        return int(result.scalar() or 0)

    async def add_plan(self, plan: AssignmentReminderPlan) -> AssignmentReminderPlan:
        """
        功能描述：
            新增计划。

        参数：
            plan (AssignmentReminderPlan): AssignmentReminderPlan 类型的数据。

        返回值：
            AssignmentReminderPlan: 返回AssignmentReminderPlan类型的处理结果。
        """
        self.db.add(plan)
        await self.db.commit()
        await self.db.refresh(plan)
        return plan

    async def list_due_pending_plans(
        self,
        assignment_id: str,
        now: datetime,
    ) -> list[AssignmentReminderPlan]:
        """
        功能描述：
            按条件查询duependingplans列表。

        参数：
            assignment_id (str): 作业ID。
            now (datetime): datetime 类型的数据。

        返回值：
            list[AssignmentReminderPlan]: 返回列表形式的结果数据。
        """
        result = await self.db.execute(
            select(AssignmentReminderPlan)
            .where(
                AssignmentReminderPlan.assignment_id == assignment_id,
                AssignmentReminderPlan.is_enabled.is_(True),
                AssignmentReminderPlan.status == AssignmentReminderPlanStatus.PENDING,
                AssignmentReminderPlan.remind_at <= now,
            )
            .order_by(AssignmentReminderPlan.sequence_no.asc(), AssignmentReminderPlan.remind_at.asc())
        )
        return result.scalars().all()

    async def list_executions(self, assignment_id: str) -> list[AssignmentReminderExecution]:
        """
        功能描述：
            按条件查询executions列表。

        参数：
            assignment_id (str): 作业ID。

        返回值：
            list[AssignmentReminderExecution]: 返回列表形式的结果数据。
        """
        result = await self.db.execute(
            select(AssignmentReminderExecution)
            .where(AssignmentReminderExecution.assignment_id == assignment_id)
            .order_by(AssignmentReminderExecution.scheduled_at.desc(), AssignmentReminderExecution.created_at.desc())
        )
        return result.scalars().all()

    async def count_executions(self, assignment_id: str) -> int:
        """
        功能描述：
            统计executions数量。

        参数：
            assignment_id (str): 作业ID。

        返回值：
            int: 返回统计结果。
        """
        result = await self.db.execute(
            select(func.count()).select_from(AssignmentReminderExecution).where(
                AssignmentReminderExecution.assignment_id == assignment_id
            )
        )
        return int(result.scalar() or 0)

    async def add_execution(self, execution: AssignmentReminderExecution) -> AssignmentReminderExecution:
        """
        功能描述：
            新增执行记录。

        参数：
            execution (AssignmentReminderExecution): AssignmentReminderExecution 类型的数据。

        返回值：
            AssignmentReminderExecution: 返回AssignmentReminderExecution类型的处理结果。
        """
        self.db.add(execution)
        await self.db.flush()
        return execution

    async def save(self) -> None:
        """
        功能描述：
            保存AssignmentReminderRepository。

        参数：
            无。

        返回值：
            None: 无返回值。
        """
        await self.db.commit()

    async def refresh(self, item) -> None:
        """
        功能描述：
            刷新AssignmentReminderRepository。

        参数：
            item (Any): 当前处理的实体对象。

        返回值：
            None: 无返回值。
        """
        await self.db.refresh(item)
