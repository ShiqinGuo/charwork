# 学生端功能闭环设计文档

**日期：** 2026-04-16  
**作者：** Kiro  
**状态：** 设计阶段

---

## 1. 概述

### 1.1 目标

实现学生端完整的功能闭环，使学生能够：
1. 加入班级
2. 查看班级信息和作业
3. 提交作业
4. 查看反馈（AI 反馈和教师反馈）
5. 追踪个人学习进度
6. 与教师进行协作沟通

### 1.2 范围

本设计涵盖学生端的三个阶段实现：
- **第一阶段（核心）：** 班级加入、作业查看、提交、反馈查看
- **第二阶段（完善）：** 个人中心、学习记录汇总
- **第三阶段（协作）：** 消息、评论、搜索集成

### 1.3 设计原则

- **用户为中心：** 围绕学生的学习路径组织功能
- **权限隔离：** 学生只能访问自己的数据和已加入班级的内容
- **渐进式实现：** 分阶段交付，每个阶段都能独立验证
- **复用现有能力：** 充分利用现有的教师端接口和服务

---

## 2. 系统架构

### 2.1 整体架构

```
学生端 API 层
├── 班级管理模块 (ClassModule)
│   ├── 加入班级
│   ├── 查看班级列表
│   └── 查看班级详情
├── 作业管理模块 (AssignmentModule)
│   ├── 查看班级作业
│   ├── 查看作业详情
│   └── 查看提交历史
├── 反馈模块 (FeedbackModule)
│   ├── 查看 AI 反馈
│   └── 查看教师反馈
├── 个人中心模块 (ProfileModule) [第二阶段]
│   ├── 学习仪表板
│   ├── 作业汇总
│   └── 反馈汇总
└── 协作模块 (CollaborationModule) [第三阶段]
    ├── 消息
    ├── 评论
    └── 搜索
```

### 2.2 数据模型关系

```
Student (学生)
├── 1:N → StudentClass (学生-班级关系)
│   └── N:1 → TeachingClass (班级)
│       └── 1:N → Assignment (作业)
│           └── 1:N → Submission (提交)
│               ├── 1:1 → AIFeedback (AI 反馈)
│               └── 1:1 → TeacherFeedback (教师反馈)
```

**新增表：** `StudentClass` - 记录学生与班级的关系
- `id`: 主键
- `student_id`: 学生 ID
- `teaching_class_id`: 班级 ID
- `joined_at`: 加入时间
- `status`: 状态（active/inactive）

---

## 3. 第一阶段详细设计（核心学习路径）

### 3.1 班级加入与查看模块

#### 3.1.1 加入班级接口

**接口：** `POST /students/me/join-class`

**请求体：**
```json
{
  "token": "string",  // 班级加入令牌（教师生成）
  "class_code": "string"  // 或班级代码（可选，备选方案）
}
```

**响应：**
```json
{
  "id": "string",
  "teaching_class_id": "string",
  "class_name": "string",
  "teacher_name": "string",
  "joined_at": "datetime",
  "status": "active"
}
```

**业务规则：**
- 学生不能重复加入同一班级
- Token 需要验证有效期和使用次数限制
- 加入成功后创建 StudentClass 记录

**错误处理：**
- 400: Token 无效或已过期
- 409: 学生已加入该班级

#### 3.1.2 查看班级列表接口

**接口：** `GET /students/me/classes`

**查询参数：**
```
status: active|inactive (可选)
skip: int (默认 0)
limit: int (默认 20, 最大 100)
```

**响应：**
```json
{
  "total": 5,
  "items": [
    {
      "id": "string",
      "name": "string",
      "teacher_name": "string",
      "member_count": 30,
      "assignment_count": 5,
      "joined_at": "datetime",
      "status": "active"
    }
  ]
}
```

#### 3.1.3 查看班级详情接口

**接口：** `GET /students/me/classes/{class_id}`

**响应：**
```json
{
  "id": "string",
  "name": "string",
  "description": "string",
  "teacher_id": "string",
  "teacher_name": "string",
  "member_count": 30,
  "assignment_count": 5,
  "joined_at": "datetime",
  "status": "active"
}
```

**权限验证：** 学生必须已加入该班级

#### 3.1.4 查看班级成员列表接口

**接口：** `GET /students/me/classes/{class_id}/members`

**查询参数：**
```
skip: int (默认 0)
limit: int (默认 20, 最大 100)
```

**响应：**
```json
{
  "total": 30,
  "items": [
    {
      "id": "string",
      "name": "string",
      "joined_at": "datetime"
    }
  ]
}
```

### 3.2 作业与提交模块

#### 3.2.1 查看班级作业列表接口

**接口：** `GET /students/me/classes/{class_id}/assignments`

**查询参数：**
```
status: not_submitted|submitted|graded (可选)
sort_by: deadline|created_at (默认 deadline)
skip: int (默认 0)
limit: int (默认 20, 最大 100)
```

**响应：**
```json
{
  "total": 10,
  "items": [
    {
      "id": "string",
      "title": "string",
      "description": "string",
      "deadline": "datetime",
      "created_at": "datetime",
      "submission_status": "not_submitted|submitted|graded",
      "submission_id": "string (if submitted)"
    }
  ]
}
```

**业务规则：**
- 按截止时间排序，未截止的优先显示
- 显示学生的提交状态

#### 3.2.2 查看作业详情接口

**接口：** `GET /students/me/assignments/{assignment_id}`

**响应：**
```json
{
  "id": "string",
  "title": "string",
  "description": "string",
  "requirements": "string",
  "deadline": "datetime",
  "created_at": "datetime",
  "attachments": [
    {
      "id": "string",
      "name": "string",
      "url": "string"
    }
  ],
  "submission": {
    "id": "string",
    "status": "submitted|graded",
    "submitted_at": "datetime",
    "content": "string",
    "score": "number (if graded)"
  }
}
```

**权限验证：** 学生必须已加入该作业所属班级

#### 3.2.3 查看个人提交列表接口

**接口：** `GET /students/me/submissions`

**查询参数：**
```
class_id: string (可选，筛选特定班级)
status: submitted|graded (可选)
skip: int (默认 0)
limit: int (默认 20, 最大 100)
```

**响应：**
```json
{
  "total": 15,
  "items": [
    {
      "id": "string",
      "assignment_id": "string",
      "assignment_title": "string",
      "class_name": "string",
      "submitted_at": "datetime",
      "status": "submitted|graded",
      "score": "number (if graded)"
    }
  ]
}
```

#### 3.2.4 查看提交详情接口

**接口：** `GET /students/me/submissions/{submission_id}`

**响应：**
```json
{
  "id": "string",
  "assignment_id": "string",
  "assignment_title": "string",
  "class_name": "string",
  "submitted_at": "datetime",
  "status": "submitted|graded",
  "content": "string",
  "attachments": [
    {
      "id": "string",
      "name": "string",
      "url": "string"
    }
  ],
  "score": "number (if graded)",
  "graded_at": "datetime (if graded)"
}
```

**权限验证：** 学生只能查看自己的提交

### 3.3 反馈查看模块

#### 3.3.1 查看 AI 反馈接口

**接口：** `GET /students/me/submissions/{submission_id}/ai-feedback`

**响应：**
```json
{
  "id": "string",
  "submission_id": "string",
  "feedback": "string",
  "created_at": "datetime",
  "model": "string"
}
```

**权限验证：** 学生只能查看自己提交的反馈

#### 3.3.2 查看教师反馈接口

**接口：** `GET /students/me/submissions/{submission_id}/teacher-feedback`

**响应：**
```json
{
  "id": "string",
  "submission_id": "string",
  "feedback": "string",
  "score": "number",
  "graded_at": "datetime",
  "teacher_name": "string"
}
```

**权限验证：** 学生只能查看自己提交的反馈

---

## 4. 第二阶段设计（个人中心）

### 4.1 个人学习仪表板

**接口：** `GET /students/me/dashboard`

**响应：**
```json
{
  "total_assignments": 25,
  "submitted_count": 18,
  "pending_count": 7,
  "graded_count": 15,
  "average_score": 85.5,
  "classes_count": 3,
  "recent_feedback": [
    {
      "assignment_title": "string",
      "feedback_type": "ai|teacher",
      "created_at": "datetime"
    }
  ]
}
```

### 4.2 个人作业汇总

**接口：** `GET /students/me/assignments-summary`

**响应：**
```json
{
  "total": 25,
  "by_status": {
    "not_submitted": 7,
    "submitted": 3,
    "graded": 15
  },
  "by_class": [
    {
      "class_name": "string",
      "total": 10,
      "submitted": 8,
      "graded": 7
    }
  ]
}
```

### 4.3 个人反馈汇总

**接口：** `GET /students/me/feedback-summary`

**响应：**
```json
{
  "total_feedback": 15,
  "ai_feedback_count": 10,
  "teacher_feedback_count": 5,
  "recent_feedback": [
    {
      "assignment_title": "string",
      "feedback_type": "ai|teacher",
      "score": "number (if teacher feedback)",
      "created_at": "datetime"
    }
  ]
}
```

---

## 5. 第三阶段设计（协作功能）

### 5.1 消息功能

复用现有接口：
- `GET /messages` - 查看消息列表
- `POST /messages` - 发送消息
- `GET /messages/{id}` - 查看消息详情

学生端需要集成这些接口，支持与教师的沟通。

### 5.2 评论功能

复用现有接口：
- `GET /comments` - 查看评论列表
- `POST /comments` - 发表评论
- `DELETE /comments/{id}` - 删除评论

学生端可在作业、提交上发表评论。

### 5.3 搜索功能

复用现有接口：
- `GET /search` - 搜索作业、班级、反馈等

---

## 6. 权限与安全

### 6.1 权限控制

所有学生端接口需要：
1. 用户认证：`get_current_user`
2. 学生身份验证：`get_current_student`
3. 资源权限验证：
   - 班级权限：学生必须已加入班级
   - 提交权限：学生只能查看自己的提交
   - 反馈权限：学生只能查看自己的反馈

### 6.2 数据隔离

- 学生只能查看自己加入的班级
- 学生只能查看自己的提交和反馈
- 学生不能修改他人的数据

---

## 7. 错误处理

### 7.1 HTTP 状态码

| 状态码 | 场景 | 示例 |
|--------|------|------|
| 400 | 请求参数错误 | Token 无效、参数格式错误 |
| 403 | 无权限访问 | 学生未加入班级、查看他人数据 |
| 404 | 资源不存在 | 班级不存在、作业不存在 |
| 409 | 冲突 | 学生已加入班级、重复提交 |
| 500 | 服务器错误 | 数据库错误、系统异常 |

### 7.2 业务异常

- **加入班级失败：** Token 过期、班级已满、学生已加入
- **提交失败：** 超过截止时间、格式错误、文件过大
- **查询失败：** 班级不存在、作业不存在、无权限

---

## 8. 数据流

### 8.1 核心学习路径

```
1. 学生登录
   ↓
2. 获取已加入班级列表 (GET /students/me/classes)
   ↓
3. 选择班级，查看班级详情 (GET /students/me/classes/{class_id})
   ↓
4. 查看班级作业列表 (GET /students/me/classes/{class_id}/assignments)
   ↓
5. 选择作业，查看作业详情 (GET /students/me/assignments/{assignment_id})
   ↓
6. 提交作业 (POST /assignments/{assignment_id}/submissions)
   ↓
7. 查看提交状态 (GET /students/me/submissions/{submission_id})
   ↓
8. 查看 AI 反馈 (GET /students/me/submissions/{submission_id}/ai-feedback)
   ↓
9. 查看教师反馈 (GET /students/me/submissions/{submission_id}/teacher-feedback)
```

### 8.2 个人学习记录查询

```
学生进入个人中心
   ↓
查看学习仪表板 (GET /students/me/dashboard)
   ↓
查看作业汇总 (GET /students/me/assignments-summary)
   ↓
查看反馈汇总 (GET /students/me/feedback-summary)
```

---

## 9. 测试策略

### 9.1 单元测试

- **Service 层：** 班级查询、作业筛选、权限验证逻辑
- **Schema 层：** 数据模型验证、字段类型检查
- **Repository 层：** 数据库查询逻辑

### 9.2 集成测试

- **完整学习路径：** 加入班级 → 查看作业 → 提交 → 查看反馈
- **权限验证：** 学生无法访问未加入班级的内容
- **错误场景：** 超时提交、重复加入、无效 Token

### 9.3 端到端测试

- 学生完整的学习流程（前端集成测试）
- 多班级场景下的数据隔离

---

## 10. 实现计划

### 10.1 第一阶段（核心）

**预期工作量：** 2-3 周

1. 创建 StudentClass 数据模型和迁移
2. 实现班级加入与查看模块（4 个接口）
3. 实现作业与提交模块（4 个接口）
4. 实现反馈查看模块（2 个接口）
5. 编写单元测试和集成测试
6. 验证完整学习路径

### 10.2 第二阶段（个人中心）

**预期工作量：** 1 周

1. 实现个人中心模块（3 个接口）
2. 编写测试
3. 集成到前端

### 10.3 第三阶段（协作功能）

**预期工作量：** 1 周

1. 集成现有消息、评论、搜索接口
2. 编写学生端的使用文档
3. 端到端测试

---

## 11. 依赖与风险

### 11.1 依赖

- 现有的 Assignment、Submission、Feedback 模型和服务
- 现有的认证和授权系统
- 现有的消息、评论、搜索功能

### 11.2 风险

- **数据一致性：** StudentClass 表与 TeachingClass 的同步
- **性能：** 大班级下的成员列表查询可能较慢
- **权限复杂性：** 多班级场景下的权限验证逻辑

### 11.3 缓解措施

- 使用数据库约束确保数据一致性
- 对成员列表查询进行分页和缓存
- 编写详细的权限验证测试

---

## 12. 后续考虑

- 学生端的通知功能（作业截止提醒、反馈通知）
- 学生端的离线支持
- 学生端的性能优化（缓存、预加载）
- 学生端的国际化支持
