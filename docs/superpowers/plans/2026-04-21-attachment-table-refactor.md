# 作业附件表重构 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将作业提交的单字段图片存储改为通用附件表，支持一对多关系和多种对象类型。

**Architecture:** 创建独立的 Attachment 表，通过多态关联支持多种对象类型。后端新增 AttachmentService，修改 SubmissionService。前端适配新接口。

**Tech Stack:** SQLAlchemy ORM、FastAPI、Pydantic、React + TypeScript

---

## 核心任务

### Task 1: 创建 Attachment 数据模型
- [ ] 创建 app/models/attachment.py
- [ ] 在 models/__init__.py 中导入
- [ ] 提交

### Task 2: 创建 Attachment Schema
- [ ] 创建 app/schemas/attachment.py
- [ ] 提交

### Task 3: 创建 AttachmentRepository
- [ ] 创建 app/repositories/attachment_repo.py
- [ ] 提交

### Task 4: 创建 AttachmentService
- [ ] 在 app/core/config.py 添加 ATTACHMENT_OWNER_TYPES
- [ ] 创建 app/services/attachment_service.py
- [ ] 提交

### Task 5: 创建数据库迁移
- [ ] 运行 alembic revision --autogenerate
- [ ] 验证迁移脚本
- [ ] 运行 alembic upgrade head
- [ ] 提交

### Task 6: 修改 Submission 模型
- [ ] 删除 image_paths 字段
- [ ] 添加 attachments 关系
- [ ] 提交

### Task 7: 修改 Submission Schema
- [ ] 修改 SubmissionCreate 添加 attachment_ids
- [ ] 修改 SubmissionResponse 添加 attachments
- [ ] 提交

### Task 8: 修改 SubmissionRepository
- [ ] 修改 build_submission 删除 image_paths
- [ ] 在查询方法添加 joinedload
- [ ] 提交

### Task 9: 修改 SubmissionService
- [ ] 修改 upload_submission_images 返回 attachment_ids
- [ ] 修改 create_submission 关联 attachment_ids
- [ ] 修改 update_submission 支持附件增删改
- [ ] 提交

### Task 10: 修改 API 路由
- [ ] 修改上传接口返回 attachment_ids
- [ ] 提交

### Task 11: 修改前端类型
- [ ] 添加 Attachment 接口
- [ ] 修改 Submission 接口
- [ ] 提交

### Task 12: 修改前端组件
- [ ] 修改 AssignmentInsightDialogs 展示 attachments
- [ ] 提交

### Task 13: 数据迁移（可选）
- [ ] 创建迁移脚本
- [ ] 运行迁移
- [ ] 提交

---

## 验证清单

- [ ] 后端单元测试通过
- [ ] 前端类型检查通过
- [ ] 完整流程可用
- [ ] 多租户隔离验证通过
