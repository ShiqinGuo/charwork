from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.management_system_record import ManagementSystemRecord


class ManagementSystemRecordRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_by_system(
        self,
        management_system_id: str,
        owner_user_id: str,
        skip: int,
        limit: int,
        keyword: Optional[str] = None,
    ) -> list[ManagementSystemRecord]:
        stmt = (
            select(ManagementSystemRecord)
            .where(
                ManagementSystemRecord.management_system_id == management_system_id,
                ManagementSystemRecord.owner_user_id == owner_user_id,
            )
            .order_by(ManagementSystemRecord.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        if keyword:
            stmt = stmt.where(ManagementSystemRecord.title.ilike(f"%{keyword}%"))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count_by_system(
        self,
        management_system_id: str,
        owner_user_id: str,
        keyword: Optional[str] = None,
    ) -> int:
        stmt = select(func.count()).select_from(ManagementSystemRecord).where(
            ManagementSystemRecord.management_system_id == management_system_id,
            ManagementSystemRecord.owner_user_id == owner_user_id,
        )
        if keyword:
            stmt = stmt.where(ManagementSystemRecord.title.ilike(f"%{keyword}%"))
        result = await self.db.execute(stmt)
        return int(result.scalar() or 0)

    async def get(self, record_id: str, management_system_id: str,
                  owner_user_id: str) -> Optional[ManagementSystemRecord]:
        result = await self.db.execute(
            select(ManagementSystemRecord).where(
                ManagementSystemRecord.id == record_id,
                ManagementSystemRecord.management_system_id == management_system_id,
                ManagementSystemRecord.owner_user_id == owner_user_id,
            )
        )
        return result.scalars().first()

    async def add(self, record: ManagementSystemRecord) -> ManagementSystemRecord:
        self.db.add(record)
        await self.db.flush()
        return record

    async def delete(self, record: ManagementSystemRecord) -> None:
        await self.db.delete(record)
        await self.db.flush()

    async def save(self) -> None:
        await self.db.commit()
