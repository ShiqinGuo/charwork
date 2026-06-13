# 作业附件表重构设计文档

**日期**: 2026-04-21  
**范围**: 后端数据模型 + 前端接口适配  
**目标**: 将单字段图片存储改为通用附件表，支持一对多关系和多种对象类型

---

## 1. 需求概述

### 当前问题
- `Submission` 表用 `image_paths` JSON 字段存储所有图片路径
- 无法追踪单个文件的元数据（大小、类型、上传时间）
- 不支持其他对象类型（作业、评论等）的附件需求

### 目标状态
- 创建通用 `Attachment` 表，支持多种对象类型
- 通过外键 + 软删除实现生命周期管理
- 保留附件记录用于审计，物理文件由云存储生命周期策略管理

---

## 2. 数据模型设计

### 2.1 新增 `Attachment` 表

```sql
CREATE TABLE attachment (
    id VARCHAR(50) PRIMARY KEY,
    owner_type VARCHAR(50) NOT NULL,           -- 关联对象类型
    owner_id VARCHAR(50) NOT NULL,             -- 关联对象ID
    file_url VARCHAR(500) NOT NULL,            -- 云存储文件地址
    filename VARCHAR(255) NOT NULL,            -- 原始文件名
    file_size INTEGER NOT NULL,                -- 文件大小（字节）
    mime_type VARCHAR(100) NOT NULL,           -- 文件类型
    management_system_id VARCHAR(50),          -- 租户隔离
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    deleted_at DATETIME,                       -- 软删除标记
    
    INDEX idx_owner (owner_type, owner_id),
    INDEX idx_management_system (management_system_id),
    INDEX idx_deleted (deleted_at)
);
```

### 2.2 修改 `Submission` 表

**删除字段**:
- `image_paths` (JSON)

**添加关系**:
- 反向关系 `attachments: relationship` 指向 `Attachment` 表

---

## 3. 配置管理

### 3.1 支持的附件所有者类型

在 `app/core/config.py` 中定义：

```python
ATTACHMENT_OWNER_TYPES = {
    "submission": {
        "model": "Submission",
        "description": "作业提交"
    },
    "assignment": {
        "model": "Assignment",
        "description": "作业描述"
    },
    "comment": {
        "model": "Comment",
        "description": "评论"
    }
}
```

**为什么这样做**:
- 符合代码规范（配置项不硬编码）
- 新增类型只需修改配置，无需改代码
- 应用层通过配置验证和查询

---

## 4. 后端服务层设计

### 4.1 新增 `AttachmentService`

**职责**:
- 上传文件到云存储并创建附件记录
- 查询、删除附件
- 验证所有者类型和权限

**核心方法**:

```python
class AttachmentService:
    async def upload_attachment(
        self,
        file: UploadFile,
        owner_type: str,
        owner_id: str,
        management_system_id: str,
    ) -> AttachmentResponse:
        """上传文件到云存储，创建附件记录"""
        
    async def get_attachments_by_owner(
        self,
        owner_type: str,
        owner_id: str,
        management_system_id: str,
    ) -> List[AttachmentResponse]:
        """按所有者查询附件（排除已删除）"""
        
    async def delete_attachment(
        self,
        attachment_id: str,
        management_system_id: str,
    ) -> None:
        """软删除附件"""
        
    def validate_owner_type(self, owner_type: str) -> bool:
        """验证所有者类型是否支持"""
```

### 4.2 修改 `SubmissionService`

**变更点**:

1. `upload_submission_images()` 改为调用 `AttachmentService.upload_attachment()`
   - 返回 `attachment_id` 列表（而非 `file_url`）

2. `create_submission()` 支持 `attachment_ids` 参数
   - 验证这些附件确实存在且未被关联
   - 后端自动建立关联关系

3. `update_submission()` 支持附件的增删改
   - 新增附件：调用 `upload_attachment()`
   - 删除附件：调用 `delete_attachment()`
   - 保留附件：无需操作

4. 删除提交时自动软删除关联附件
   - 通过 SQLAlchemy 级联删除或显式调用

### 4.3 修改 `SubmissionRepository`

**变更点**:

1. `build_submission()` 不再处理 `image_paths`
2. 新增 `attach_attachments()` 方法建立关联
3. 查询时通过 `joinedload(Submission.attachments)` 加载附件

---

## 5. API 层变更

### 5.1 上传图片接口

**现有接口** (保留):
```
POST /api/v1/assignments/{assignment_id}/upload-images
Content-Type: multipart/form-data

Response:
{
  "attachment_ids": ["att_001", "att_002"]  // 改为返回 ID 列表
}
```

### 5.2 创建提交接口

**请求体变更**:
```json
{
  "student_id": "stu_001",
  "content": "我的答案",
  "attachment_ids": ["att_001", "att_002"]  // 新增字段
}
```

**响应体变更**:
```json
{
  "id": "sub_001",
  "assignment_id": "asg_001",
  "student_id": "stu_001",
  "content": "我的答案",
  "attachments": [
    {
      "id": "att_001",
      "file_url": "https://...",
      "filename": "answer.jpg",
      "file_size": 102400,
      "mime_type": "image/jpeg",
      "created_at": "2026-04-21T10:00:00Z"
    }
  ],
  "status": "submitted",
  "submitted_at": "2026-04-21T10:00:00Z"
}
```

### 5.3 修改提交接口

**请求体变更**:
```json
{
  "content": "修改后的答案",
  "attachment_ids": ["att_001", "att_003"],  // 新增、保留、删除的混合
  "deleted_attachment_ids": ["att_002"]      // 显式删除的 ID
}
```

### 5.4 查询提交接口

**响应体变更**: 同创建提交接口，包含完整 `attachments` 数组

---

## 6. 前端接口适配

### 6.1 上传流程变更

**现有流程**:
1. 调用 `/upload-images` → 获得 `file_url` 列表
2. 调用 `/submissions` 创建提交，传入 `image_paths`

**新流程**:
1. 调用 `/upload-images` → 获得 `attachment_id` 列表
2. 调用 `/submissions` 创建提交，传入 `attachment_ids`

### 6.2 前端组件变更

**`AssignmentInsightDialogs.tsx`**:
- 修改提交详情展示，从 `submission.image_paths` 改为 `submission.attachments`
- 遍历 `attachments` 数组，展示文件名、大小、类型等

**提交表单组件** (新增或修改):
- 上传后保存 `attachment_id` 列表
- 创建提交时传入 `attachment_ids`
- 修改提交时支持增删附件

### 6.3 类型定义变更

**`types/assignment.ts`**:

```typescript
interface Attachment {
  id: string;
  file_url: string;
  filename: string;
  file_size: number;
  mime_type: string;
  created_at: string;
}

interface Submission {
  id: string;
  assignment_id: string;
  student_id: string;
  content?: string;
  attachments: Attachment[];  // 改为数组
  status: 'submitted' | 'graded';
  score?: number;
  teacher_feedback?: string;
  submitted_at: string;
  graded_at?: string;
}

interface SubmissionCreate {
  student_id?: string;
  content?: string;
  attachment_ids: string[];  // 新增字段
}
```

---

## 7. 数据迁移策略

### 7.1 迁移步骤

1. **创建 `Attachment` 表** (新表)
2. **数据迁移脚本**:
   - 遍历所有 `Submission` 记录
   - 对每条记录的 `image_paths` JSON 数组
   - 为每个 URL 创建 `Attachment` 记录
   - 记录 `owner_type="submission"`, `owner_id=submission.id`

3. **删除 `Submission.image_paths` 字段** (破坏性变更)

### 7.2 回滚方案

- 保留迁移脚本的反向操作
- 如需回滚，从 `Attachment` 表重建 `image_paths` JSON

---

## 8. 错误处理

### 8.1 上传阶段

| 场景 | HTTP 状态 | 错误信息 |
|------|---------|--------|
| 文件大小超限 | 400 | `File size exceeds limit` |
| 不支持的文件类型 | 400 | `Unsupported file type` |
| 云存储上传失败 | 500 | `Failed to upload to cloud storage` |

### 8.2 创建提交阶段

| 场景 | HTTP 状态 | 错误信息 |
|------|---------|--------|
| 引用不存在的附件 | 400 | `Attachment not found` |
| 附件已被其他提交关联 | 400 | `Attachment already associated` |
| 附件属于其他租户 | 403 | `Attachment access denied` |

### 8.3 删除提交阶段

- 自动软删除关联附件，无需显式处理
- 物理文件由云存储生命周期策略管理

---

## 9. 测试策略

### 9.1 后端单元测试

- `AttachmentService` 的上传、查询、删除逻辑
- `SubmissionService` 的附件关联逻辑
- 多租户隔离验证

### 9.2 集成测试

- 完整的上传 → 创建提交 → 查询提交流程
- 修改提交时的附件增删改
- 删除提交时的级联软删除

### 9.3 前端测试

- 上传表单的 `attachment_id` 收集
- 提交详情的附件展示
- 修改提交时的附件管理

---

## 10. 部署注意事项

### 10.1 顺序

1. 部署后端代码（新增 `AttachmentService`、修改 `SubmissionService`）
2. 运行数据迁移脚本
3. 部署前端代码（适配新接口）

### 10.2 兼容性

- 迁移期间，后端需同时支持旧接口（`image_paths`）和新接口（`attachment_ids`）
- 前端可逐步切换到新接口

---

## 11. 未来扩展

- 支持作业描述的附件
- 支持评论的附件
- 附件版本管理（同一文件的多个版本）
- 附件权限控制（谁可以下载、删除）

