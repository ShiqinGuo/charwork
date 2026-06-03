"""清理 course_teaching_class 重复数据，确保 teaching_class_id 唯一"""
import asyncio
from app.core.database import AsyncSessionLocal
from sqlalchemy import text

async def main():
    async with AsyncSessionLocal() as db:
        # 删除旧重复记录：teaching_class 7467626964170481664 先后关联了两个课程，保留最新的
        result = await db.execute(text(
            "DELETE FROM course_teaching_class WHERE id = '7467628250165059584'"
        ))
        print("Deleted:", result.rowcount)

        # 更新课程的 primary teaching_class_id
        await db.execute(text(
            "UPDATE course SET teaching_class_id = '7467626857807126528' "
            "WHERE id = '7467626365551026176'"
        ))
        await db.commit()
        print("Fixed course primary class")

        # 确认无重复
        result = await db.execute(text(
            "SELECT teaching_class_id, COUNT(*) as cnt "
            "FROM course_teaching_class GROUP BY teaching_class_id HAVING cnt > 1"
        ))
        rows = result.fetchall()
        print("Remaining duplicates:", len(rows))

asyncio.run(main())
