# AI 手写体评语 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 学生提交手写作业后，系统自动调用 Ark 视觉模型生成结构化 AI 评语（笔画/结构/整体三维度），教师可独立补充评语，两者分开存储。

**Architecture:** 提交触发 Celery 异步任务，任务调用 AIFeedbackService，后者串联 OCR 识别和 Ark 视觉模型，将结构化 JSON 写入 submission.ai_feedback。教师评语独立存储在 teacher_feedback 字段（原 feedback 字段重命名）。

**Tech Stack:** FastAPI, SQLAlchemy async, Alembic, Celery, volcenginesdkarkruntime (AsyncArk), 百度 OCR

---

## File Map

| 文件 | 操作 | 职责 |
|------|------|------|
| `migrations/versions/<rev>_ai_feedback_submission.py` | 新建 | 重命名 feedback→teacher_feedback，添加 ai_feedback JSON 列 |
| `app/models/submission.py` | 修改 | 添加 ai_feedback、teacher_feedback 字段，删除 feedback |
| `app/schemas/submission.py` | 修改 | 更新 Response，添加 TeacherFeedbackUpdate schema |
| `app/core/config.py` | 修改 | 添加 ARK_VISION_MODEL 配置项 |
| `app/services/ai_feedback_service.py` | 新建 | OCR + 视觉模型调用，生成结构化评语 |
| `app/tasks/ai_feedback_tasks.py` | 新建 | Celery task: generate_ai_feedback |
| `app/services/submission_service.py` | 修改 | create 时触发任务；grade 写 teacher_feedback；添加 get_ai_feedback/save_teacher_feedback |
| `app/api/v1/routes_submissions.py` | 修改 | 添加 GET ai-feedback、POST teacher-feedback 端点 |
| `tests/test_ai_feedback.py` | 新建 | 所有新功能的单元测试 |

---

### Task 1: 模型字段 + 数据库迁移

**Files:**
- Modify: `app/models/submission.py`
- Create: `migrations/versions/<rev>_ai_feedback_submission.py`
- Create: `tests/test_ai_feedback.py`

- [ ] **Step 1: 写失败测试**

新建 `tests/test_ai_feedback.py`：

```python
import os, unittest
from datetime import datetime
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("MYSQL_HOST", "localhost")
os.environ.setdefault("MYSQL_PORT", "3306")
os.environ.setdefault("MYSQL_USER", "root")
os.environ.setdefault("MYSQL_PASSWORD", "root")
os.environ.setdefault("MYSQL_DB", "charwork")

from app.models.submission import Submission

class TestSubmissionModel(unittest.TestCase):
    def test_has_ai_feedback_field(self):
        self.assertTrue(hasattr(Submission(), 'ai_feedback'))

    def test_has_teacher_feedback_field(self):
        self.assertTrue(hasattr(Submission(), 'teacher_feedback'))

    def test_no_feedback_field(self):
        self.assertFalse(hasattr(Submission(), 'feedback'))
```

- [ ] **Step 2: 运行测试，确认失败**

```
pytest tests/test_ai_feedback.py::TestSubmissionModel -v
```
Expected: FAIL

- [ ] **Step 3: 修改 app/models/submission.py**

将原有 `feedback` 字段替换为 `teacher_feedback` 和 `ai_feedback`：

```python
# 删除这行：
# feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

# 替换为：
teacher_feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
# AI 生成的结构化评语：{status, generated_at, items:[{image_index,char,stroke_score,...}]}
ai_feedback: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
```

- [ ] **Step 4: 运行测试，确认通过**

```
pytest tests/test_ai_feedback.py::TestSubmissionModel -v
```
Expected: PASS

- [ ] **Step 5: 生成并编辑迁移文件**

```bash
alembic revision --autogenerate -m "ai_feedback_submission"
```

编辑生成的文件，upgrade/downgrade 内容如下：

```python
def upgrade() -> None:
    op.alter_column('submission', 'feedback',
                    new_column_name='teacher_feedback',
                    existing_type=sa.Text(),
                    nullable=True)
    op.add_column('submission', sa.Column('ai_feedback', sa.JSON(), nullable=True))

def downgrade() -> None:
    op.drop_column('submission', 'ai_feedback')
    op.alter_column('submission', 'teacher_feedback',
                    new_column_name='feedback',
                    existing_type=sa.Text(),
                    nullable=True)
```

- [ ] **Step 6: Commit**

```bash
git add app/models/submission.py migrations/versions/ tests/test_ai_feedback.py
git commit -m "feat: submission 模型添加 ai_feedback/teacher_feedback 字段"
```

---

### Task 2: Schema 更新

**Files:**
- Modify: `app/schemas/submission.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_ai_feedback.py` 追加：

```python
class TestSubmissionSchemas(unittest.TestCase):
    def test_response_has_teacher_feedback(self):
        from app.schemas.submission import SubmissionResponse
        self.assertIn('teacher_feedback', SubmissionResponse.model_fields)

    def test_response_has_ai_feedback(self):
        from app.schemas.submission import SubmissionResponse
        self.assertIn('ai_feedback', SubmissionResponse.model_fields)

    def test_teacher_feedback_update_schema(self):
        from app.schemas.submission import TeacherFeedbackUpdate
        obj = TeacherFeedbackUpdate(teacher_feedback="写得不错", score=8)
        self.assertEqual(obj.score, 8)
```

- [ ] **Step 2: 运行测试，确认失败**

```
pytest tests/test_ai_feedback.py::TestSubmissionSchemas -v
```
Expected: FAIL

- [ ] **Step 3: 替换 app/schemas/submission.py 全部内容**

```python
from typing import Optional, List, Any
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from enum import Enum


class SubmissionStatus(str, Enum):
    SUBMITTED = "submitted"
    GRADED = "graded"


class SubmissionBase(BaseModel):
    content: Optional[str] = None
    image_paths: Optional[List[str]] = None


class SubmissionCreate(SubmissionBase):
    student_id: Optional[str] = None


class SubmissionGrade(BaseModel):
    score: int
    # feedback 参数名保留，语义对应 teacher_feedback 列
    feedback: Optional[str] = None


class TeacherFeedbackUpdate(BaseModel):
    teacher_feedback: Optional[str] = None
    score: int


class SubmissionResponse(SubmissionBase):
    id: str
    assignment_id: str
    student_id: str
    management_system_id: Optional[str] = None
    status: SubmissionStatus
    score: Optional[int] = None
    teacher_feedback: Optional[str] = None
    ai_feedback: Optional[Any] = None
    submitted_at: datetime
    graded_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SubmissionListResponse(BaseModel):
    total: int
    items: List[SubmissionResponse]
    page: Optional[int] = None
    size: Optional[int] = None
    skip: Optional[int] = None
    limit: Optional[int] = None
    has_more: Optional[bool] = None
```

- [ ] **Step 4: 运行测试，确认通过**

```
pytest tests/test_ai_feedback.py::TestSubmissionSchemas -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/schemas/submission.py tests/test_ai_feedback.py
git commit -m "feat: submission schema 添加 teacher_feedback/ai_feedback，新增 TeacherFeedbackUpdate"
```

---

### Task 3: 配置项 + AIFeedbackService

**Files:**
- Modify: `app/core/config.py`
- Create: `app/services/ai_feedback_service.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_ai_feedback.py` 追加：

```python
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace

class TestAIFeedbackService(unittest.IsolatedAsyncioTestCase):
    async def test_generate_done_on_success(self):
        from app.services.ai_feedback_service import AIFeedbackService
        submission = SimpleNamespace(id="sub-1", image_paths=["media/t.jpg"], ai_feedback=None)
        svc = AIFeedbackService(AsyncMock())
        with patch.object(svc, '_recognize_char', new=AsyncMock(return_value="永")), \
             patch.object(svc, '_call_vision_model', new=AsyncMock(return_value={
                 "stroke_score": 7, "structure_score": 8, "overall_score": 6, "summary": "不错"
             })), \
             patch.object(svc.repo, 'get', new=AsyncMock(return_value=submission)), \
             patch.object(svc.repo, 'update', new=AsyncMock(return_value=submission)):
            await svc.generate("sub-1")
            kwargs = svc.repo.update.call_args[0][1]
            self.assertEqual(kwargs['ai_feedback']['status'], 'done')
            self.assertEqual(len(kwargs['ai_feedback']['items']), 1)

    async def test_generate_failed_on_exception(self):
        from app.services.ai_feedback_service import AIFeedbackService
        submission = SimpleNamespace(id="sub-1", image_paths=["media/t.jpg"], ai_feedback=None)
        svc = AIFeedbackService(AsyncMock())
        with patch.object(svc, '_recognize_char', new=AsyncMock(side_effect=Exception("ocr error"))), \
             patch.object(svc.repo, 'get', new=AsyncMock(return_value=submission)), \
             patch.object(svc.repo, 'update', new=AsyncMock(return_value=submission)):
            await svc.generate("sub-1")
            kwargs = svc.repo.update.call_args[0][1]
            self.assertEqual(kwargs['ai_feedback']['status'], 'failed')
```

- [ ] **Step 2: 运行测试，确认失败**

```
pytest tests/test_ai_feedback.py::TestAIFeedbackService -v
```
Expected: FAIL

- [ ] **Step 3: 在 app/core/config.py 的 ARK_MODEL 行后添加**

```python
# 视觉模型，用于手写体评语生成（需支持图片输入）
ARK_VISION_MODEL: str | None = os.getenv("ARK_VISION_MODEL")
```

- [ ] **Step 4: 创建 app/services/ai_feedback_service.py**

```python
"""
为什么这样做：OCR 识别文字作为锚点与图片一起发给视觉模型，
补偿纯视觉模型对笔画细节理解不稳定的问题。
特殊逻辑：任意步骤失败时写 status=failed 静默退出，不影响提交主流程。
"""

import base64
import json
import logging
import re
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from volcenginesdkarkruntime import AsyncArk

from app.core.config import settings
from app.repositories.submission_repo import SubmissionRepository
from app.services.ocr_service import OCRService

logger = logging.getLogger(__name__)

_PROMPT_TEMPLATE = (
    "你是书法评审专家。图片是一个学生手写的汉字"{char}"。\n"
    "请从以下三个维度评分（1-10分）并给出总评：\n"
    "- stroke_score：笔画质量（起收笔、粗细变化）\n"
    "- structure_score：结构布局（间架比例、重心）\n"
    "- overall_score：整体气韵\n"
    "以 JSON 格式返回，不要输出其他内容。示例：\n"
    '{{"stroke_score":7,"structure_score":8,"overall_score":6,"summary":"..."}}'
)

_JSON_PATTERN = re.compile(r'\{.*\}', re.DOTALL)


class AIFeedbackService:
    def __init__(self, db: AsyncSession):
        self.repo = SubmissionRepository(db)
        self.ocr = OCRService()
        self._ark_client: AsyncArk | None = None

    def _get_ark_client(self) -> AsyncArk:
        if self._ark_client is None:
            self._ark_client = AsyncArk(
                base_url=(settings.ARK_BASE_URL or settings.AI_BASE_URL or "").rstrip("/"),
                api_key=settings.ARK_API_KEY or settings.AI_API_KEY or "",
            )
        return self._ark_client

    def _get_vision_model(self) -> str:
        model = settings.ARK_VISION_MODEL or settings.ARK_MODEL or settings.AI_MODEL or ""
        if not model:
            raise ValueError("缺少视觉模型配置，请设置 ARK_VISION_MODEL")
        return model

    async def generate(self, submission_id: str) -> None:
        submission = await self.repo.get(submission_id)
        if not submission:
            logger.warning("generate_ai_feedback: submission %s 不存在", submission_id)
            return

        image_paths: list[str] = submission.image_paths or []
        if not image_paths:
            await self.repo.update(submission, {
                "ai_feedback": {"status": "done", "generated_at": _now(), "items": []}
            })
            return

        try:
            items = []
            for idx, path in enumerate(image_paths):
                char = await self._recognize_char(path)
                scores = await self._call_vision_model(path, char)
                items.append({
                    "image_index": idx,
                    "char": char,
                    "stroke_score": scores.get("stroke_score"),
                    "structure_score": scores.get("structure_score"),
                    "overall_score": scores.get("overall_score"),
                    "summary": scores.get("summary", ""),
                })
            await self.repo.update(submission, {
                "ai_feedback": {"status": "done", "generated_at": _now(), "items": items}
            })
        except Exception as exc:
            logger.error("AI 评语生成失败 submission=%s: %s", submission_id, exc)
            await self.repo.update(submission, {
                "ai_feedback": {"status": "failed", "generated_at": _now(), "items": []}
            })

    async def _recognize_char(self, image_path: str) -> str:
        try:
            result = await self.ocr.recognize_image(image_path)
            if isinstance(result, list):
                return "".join(result)
            return str(result) if result else ""
        except Exception:
            return ""

    async def _call_vision_model(self, image_path: str, char: str) -> dict[str, Any]:
        b64 = _encode_image(image_path)
        char_label = char if char else "（字符未识别）"
        prompt = _PROMPT_TEMPLATE.format(char=char_label)
        response = await self._get_ark_client().chat.completions.create(
            model=self._get_vision_model(),
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                    {"type": "text", "text": prompt},
                ],
            }],
            stream=False,
        )
        raw = response.choices[0].message.content or ""
        return _parse_json_response(raw)


def _encode_image(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _parse_json_response(raw: str) -> dict[str, Any]:
    match = _JSON_PATTERN.search(raw)
    if not match:
        raise ValueError(f"模型未返回有效 JSON: {raw[:200]}")
    return json.loads(match.group())


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")
```

- [ ] **Step 5: 运行测试，确认通过**

```
pytest tests/test_ai_feedback.py::TestAIFeedbackService -v
```
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/core/config.py app/services/ai_feedback_service.py tests/test_ai_feedback.py
git commit -m "feat: AIFeedbackService — OCR+视觉模型生成结构化评语"
```

---

### Task 4: Celery 任务

**Files:**
- Create: `app/tasks/ai_feedback_tasks.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_ai_feedback.py` 追加：

```python
class TestAIFeedbackTask(unittest.TestCase):
    def test_task_is_callable(self):
        from app.tasks.ai_feedback_tasks import generate_ai_feedback
        self.assertTrue(callable(generate_ai_feedback))
```

- [ ] **Step 2: 运行测试，确认失败**

```
pytest tests/test_ai_feedback.py::TestAIFeedbackTask -v
```
Expected: FAIL

- [ ] **Step 3: 创建 app/tasks/ai_feedback_tasks.py**

```python
import asyncio
import logging

from app.core.celery_app import celery_app
from app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


@celery_app.task(name="generate_ai_feedback")
def generate_ai_feedback(submission_id: str) -> dict:
    """异步生成手写体 AI 评语，由提交创建后触发。"""
    logger.info("开始生成 AI 评语：submission_id=%s", submission_id)
    return asyncio.run(_generate(submission_id))


async def _generate(submission_id: str) -> dict:
    # 延迟导入避免循环依赖
    from app.services.ai_feedback_service import AIFeedbackService

    async with AsyncSessionLocal() as db:
        await AIFeedbackService(db).generate(submission_id)
    return {"status": "ok", "submission_id": submission_id}
```

- [ ] **Step 4: 运行测试，确认通过**

```
pytest tests/test_ai_feedback.py::TestAIFeedbackTask -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/tasks/ai_feedback_tasks.py tests/test_ai_feedback.py
git commit -m "feat: Celery task generate_ai_feedback"
```

---

### Task 5: SubmissionService 更新

**Files:**
- Modify: `app/services/submission_service.py`

- [ ] **Step 1: 写失败测试**

在 `tests/test_ai_feedback.py` 追加：

```python
class TestSubmissionServiceUpdates(unittest.IsolatedAsyncioTestCase):
    async def test_grade_writes_teacher_feedback(self):
        from app.services.submission_service import SubmissionService
        from app.schemas.submission import SubmissionGrade

        submission = SimpleNamespace(
            id="sub-1", assignment_id="asg-1", student_id="stu-1",
            management_system_id="ms-1", status="submitted",
            score=None, teacher_feedback=None, ai_feedback=None,
            submitted_at=datetime(2026, 4, 15), graded_at=None,
            content=None, image_paths=None,
        )
        svc = SubmissionService(AsyncMock())
        svc.repo.get = AsyncMock(return_value=submission)
        svc.repo.update = AsyncMock(return_value=submission)
        svc.repo.db = AsyncMock()
        svc.repo.db.execute = AsyncMock(return_value=AsyncMock(scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=None)))))
        svc.repo.commit = AsyncMock()

        from unittest.mock import MagicMock
        with patch('app.services.submission_service.send_grade_notification') as mock_task:
            mock_task.delay = MagicMock()
            await svc.grade_submission("sub-1", SubmissionGrade(score=9, feedback="很好"), "ms-1", "teacher-1")

        update_data = svc.repo.update.call_args[0][1]
        self.assertIn('teacher_feedback', update_data)
        self.assertEqual(update_data['teacher_feedback'], "很好")

    async def test_get_ai_feedback_returns_field(self):
        from app.services.submission_service import SubmissionService

        submission = SimpleNamespace(
            id="sub-1", assignment_id="asg-1", student_id="stu-1",
            management_system_id="ms-1", status="submitted",
            score=None, teacher_feedback=None,
            ai_feedback={"status": "done", "generated_at": "2026-04-15T10:00:00", "items": []},
            submitted_at=datetime(2026, 4, 15), graded_at=None,
            content=None, image_paths=None,
        )
        svc = SubmissionService(AsyncMock())
        svc.repo.get = AsyncMock(return_value=submission)

        result = await svc.get_ai_feedback("sub-1", "ms-1")
        self.assertEqual(result['status'], 'done')
```

- [ ] **Step 2: 运行测试，确认失败**

```
pytest tests/test_ai_feedback.py::TestSubmissionServiceUpdates -v
```
Expected: FAIL

- [ ] **Step 3: 修改 app/services/submission_service.py**

1. 在 import 区域添加：
```python
from app.tasks.ai_feedback_tasks import generate_ai_feedback
```

2. `grade_submission` 方法中，将 `update_data` 的 `"feedback"` 键改为 `"teacher_feedback"`：
```python
update_data = {
    "score": body.score,
    "teacher_feedback": body.feedback,   # feedback 参数映射到 teacher_feedback 列
    "status": "graded",
    "graded_at": datetime.now(),
}
```

3. `_write_grade_result_message` 中，将 `body.feedback` 引用改为 `body.feedback`（不变，因为 SubmissionGrade.feedback 字段名未变）。

4. `create_submission` 方法末尾，在 `send_submission_notification.delay` 后添加：
```python
generate_ai_feedback.delay(submission.id)
```

5. 在类末尾添加两个新方法：
```python
async def get_ai_feedback(self, id: str, management_system_id: str) -> Optional[dict]:
    submission = await self.repo.get(id, management_system_id)
    if not submission:
        return None
    return submission.ai_feedback

async def save_teacher_feedback(
    self,
    id: str,
    teacher_feedback: Optional[str],
    score: int,
    management_system_id: str,
) -> Optional[SubmissionResponse]:
    submission = await self.repo.get(id, management_system_id)
    if not submission:
        return None
    updated = await self.repo.update(submission, {
        "teacher_feedback": teacher_feedback,
        "score": score,
        "status": "graded",
        "graded_at": datetime.now(),
    })
    return SubmissionResponse.model_validate(updated)
```

- [ ] **Step 4: 运行测试，确认通过**

```
pytest tests/test_ai_feedback.py::TestSubmissionServiceUpdates -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/submission_service.py tests/test_ai_feedback.py
git commit -m "feat: SubmissionService 触发 AI 评语任务，添加 get_ai_feedback/save_teacher_feedback"
```

---

### Task 6: API 端点

**Files:**
- Modify: `app/api/v1/routes_submissions.py`

- [ ] **Step 1: 在 routes_submissions.py 的 import 区域添加**

```python
from app.schemas.submission import (
    SubmissionCreate, SubmissionGrade, SubmissionListResponse,
    SubmissionResponse, TeacherFeedbackUpdate,
)
```

- [ ] **Step 2: 在文件末尾追加两个端点**

```python
@router.get("/submissions/{id}/ai-feedback")
async def get_ai_feedback(
    id: str,
    scope: ManagementScope = Depends(get_management_scope),
    db: AsyncSession = Depends(get_db),
):
    result = await SubmissionService(db).get_ai_feedback(id, scope.management_system_id)
    if result is None:
        raise HTTPException(status_code=404, detail="提交记录不存在")
    return result


@router.post("/submissions/{id}/teacher-feedback", response_model=SubmissionResponse)
async def save_teacher_feedback(
    id: str,
    body: TeacherFeedbackUpdate,
    scope: ManagementScope = Depends(get_management_scope),
    current_teacher: Teacher = Depends(get_current_teacher),
    db: AsyncSession = Depends(get_db),
):
    submission = await SubmissionService(db).save_teacher_feedback(
        id=id,
        teacher_feedback=body.teacher_feedback,
        score=body.score,
        management_system_id=scope.management_system_id,
    )
    if not submission:
        raise HTTPException(status_code=404, detail="提交记录不存在")
    return submission
```

- [ ] **Step 3: 运行全量测试，确认无回归**

```
pytest tests/test_ai_feedback.py -v
```
Expected: 全部 PASS

- [ ] **Step 4: Commit**

```bash
git add app/api/v1/routes_submissions.py
git commit -m "feat: 新增 GET ai-feedback 和 POST teacher-feedback 端点"
```

---

## 环境变量说明

实现完成后，需在 `.env` 中配置：

```
ARK_VISION_MODEL=<豆包视觉模型 endpoint ID>
```

若不配置，系统回退使用 `ARK_MODEL`（文本模型），视觉理解效果会下降。
