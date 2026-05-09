# CharWork 用户操作手册

## 一、系统概述

CharWork 是一个面向汉字书写教学场景的管理平台，支持三种角色：

| 角色 | 核心工作 | 对应前端路由 |
|------|----------|-------------|
| **教师** | 创建课程与班级 → 发布作业 → 批改书写 | `/teacher/dashboard` |
| **学生** | 查看作业 → 提交书写 → 查看反馈 | `/student/dashboard` |
| **管理员** | 用户管理 → 日志审计 | 管理员面板 |

### 典型教学场景

教师张老师在 CharWork 中创建了一门"基础汉字"课程和一个"一班"班级，发布了"第 3 课生字练习"作业。学生小李登录后查看作业，上传了自己的书写图片。AI 自动分析字形笔画并生成反馈，张老师审核后发布给学生。

## 二、快速入门

### 2.1 注册与登录

![注册登录流程](diagrams/register-login-flow.drawio)

1. 打开平台，点击「注册」
2. 选择角色（教师/学生），填写用户名、邮箱、密码
3. 注册成功后跳转登录页，输入账号密码
4. 登录后系统根据角色自动跳转到对应工作台

**对应接口：** `POST /api/v1/auth/register` → `POST /api/v1/auth/login`（返回 `access_token`）

### 2.2 界面导航

登录后界面分为：
- **顶部导航栏**：AI 对话、消息、搜索、设置
- **左侧菜单**：按角色显示不同功能入口
- **主内容区**：当前功能页面

| 导航入口 | 教师 | 学生 |
|----------|------|------|
| 工作台 | Dashboard（概览统计） | Dashboard（我的作业） |
| 课程 | 课程列表 / 创建 | 我的课程 |
| 班级 | 班级列表 / 创建 | 我的班级 |
| 作业 | 作业管理 / 批改 | 作业列表 / 提交 |
| 汉字库 | 汉字管理 / OCR 导入 | — |
| 管理体系 | 自定义字段模板 | — |

## 三、教师操作指南

![教师完整工作流](diagrams/teacher-workflow.drawio)

### 3.1 课程管理

**创建课程：**
1. 点击左侧「课程」→「创建课程」
2. 填写课程名称、描述
3. 提交后进入课程详情页

**对应路由：** `/courses/create` → `POST /api/v1/courses`  
**详情页：** `/courses/:courseId` → `GET /api/v1/courses/{courseId}`

### 3.2 班级管理

**创建班级：**
1. 点击左侧「班级」→「创建班级」
2. 填写班级名称，关联课程
3. 添加学生（通过邀请码或直接选择）

**对应路由：** `/classes/create` → `POST /api/v1/teaching-classes`  
**添加学生：** 班级详情页 → 「添加学生」→ `POST /api/v1/student-classes`

### 3.3 作业管理

![作业状态机](diagrams/assignment-state-machine.drawio)

作业经历 **草稿 → 已发布 → 已截止 → 已归档** 四个状态。

**创建作业：**
1. 进入作业管理页 →「创建作业」
2. 填写标题、描述、截止日期，选择目标班级
3. 保存为草稿（`POST /api/v1/assignments` → status=`draft`）
4. 确认无误后「发布」（`PATCH /api/v1/assignments/{id}/status` → status=`published`）

**对应路由：** `/:managementSystemId/modules/assignments/create` → `AssignmentCreate.tsx`

**批改提交：**
1. 进入「批改」→ 选择作业
2. 查看学生提交列表（书写图片附件）
3. 点击「AI 批改」，系统调用 AI 分析书写质量
4. 查看 AI 反馈结果，教师可修改
5. 发布批改结果给学生

**对应路由：** `/assignments/:assignmentId` → `AssignmentDetail.tsx`  
**批改接口：** `POST /api/v1/submissions/{id}/grade` → AI 批改触发

### 3.4 汉字管理

1. 进入「汉字库」→ 查看已有汉字列表
2. 「新建汉字」→ 填写汉字、拼音、释义（`POST /api/v1/hanzi`）
3. 「OCR 导入」→ 上传图片，自动识别汉字并预填充（`POST /api/v1/hanzi/ocr`）

### 3.5 全文检索

1. 点击顶部搜索框
2. 输入关键词，选择搜索范围（全部/课程/作业/学生/汉字）
3. 系统从 ES 召回结果，按角色过滤后返回

**对应接口：** `GET /api/v1/search?keyword=xxx&modules=assignment,course`  
**前端路由：** `/teacher/workspace/search` → `WorkspaceSearch.tsx`

### 3.6 数据导入导出

**导入：** `POST /api/v1/import/{entity_type}`（支持 assignments/students/hanzi）— Celery 异步执行  
**导出：** `POST /api/v1/export/{entity_type}` — 生成 Excel 文件下载

### 3.7 AI 对话

点击顶部「AI 对话」→ 进入对话工作台（`/teacher/ai-chat` → `AIChatWorkspace.tsx`）  
支持 SSE 流式输出，可调用内置工具（查询作业/学生等），上下文自动记忆。

## 四、学生操作指南

### 4.1 加入课程/班级

1. 教师提供邀请码或直接添加
2. 学生登录后在「我的班级」中查看已加入的班级
3. 通过「加入预览」输入邀请码加入新班级

**对应路由：** `/join-preview` → `JoinPreview.tsx`  
**对应接口：** `POST /api/v1/student-classes/join`

### 4.2 查看作业 & 提交书写

![提交批改反馈链路](diagrams/submission-feedback-pipeline.drawio)

1. 进入「我的作业」→ 查看已发布的作业列表
2. 点击作业进入详情
3. 上传书写图片（拍照或从相册选择）
4. 点击「提交」

**对应路由：** `/student/assignments` → `Assignments.tsx`  
**提交接口：** `POST /api/v1/submissions`（上传附件 + 文本）

### 4.3 查看 AI 批改反馈

1. 教师发布批改后，学生在作业详情页查看反馈
2. 反馈包含：字形分析、笔画评价、改进建议
3. 可在评论区与教师互动

**对应接口：** `GET /api/v1/submissions/{id}`（含 feedback 字段）  
**评论接口：** `POST /api/v1/comments`

### 4.4 站内消息

点击顶部「消息」→ 查看收到的消息 / 发送新消息  
**对应接口：** `GET/POST /api/v1/messages`

## 五、管理员操作指南

### 5.1 用户管理

管理员可查看/启用/禁用所有用户账号。  
**对应接口：** `GET /api/v1/admin/users`、`PATCH /api/v1/admin/users/{id}`

### 5.2 操作日志

查看系统中的关键操作记录（创建/修改/删除等审计事件）。  
**对应接口：** `GET /api/v1/logs`

## 六、通用功能

### 6.1 AI 对话助手

支持教师端使用，集成火山方舟/OpenAI 模型：
- 自然语言查询（如"我有哪些未批改的作业？"）
- 上下文记忆（多轮对话）
- 工具调用（自动查询数据库）

**对应接口：** `POST /api/v1/ai-chat`（SSE 流式返回）

### 6.2 站内消息

所有角色均可使用，支持私信和系统通知。

## 七、常见问题

| 问题 | 解决方法 |
|------|----------|
| 登录后空白页 | 检查角色是否正确，教师访问 `/teacher/dashboard`，学生访问 `/student/dashboard` |
| 看不到作业 | 确认教师已发布作业（非草稿状态），学生已加入对应班级 |
| 上传图片失败 | 检查图片格式（支持 JPG/PNG）和大小限制 |
| AI 批改不生效 | 确认 `AI_PROVIDER` 和 API Key 配置正确，Celery Worker 已启动 |
| 搜索无结果 | 尝试调用 `/api/v1/search/reindex` 重建 ES 索引 |
| 找不到某个功能 | 确认角色权限：部分功能仅教师可用 |

> **更多帮助：** 查看 [API 文档](http://127.0.0.1:8000/docs)（启动后端后访问）或联系系统管理员。
