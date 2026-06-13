# README 重写 + 用户操作手册 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修正 README 中的权限模型描述错误，按三层结构重写 README，并编写一份含流程图的用户操作手册。

**Architecture:** 本计划只涉及文档产出（Markdown + drawio 图），无代码变更。README 重写为三层结构（看懂→跑起来→深入），用户操作手册按角色组织（教师/学生/管理员），含 6 张 drawio 图。

**Tech Stack:** Markdown, drawio (MCP), Playwright (截图), Serena (代码核实)

**产出物：**
- 修改：`README.md`（重写）
- 新建：`docs/user-manual.md`（用户操作手册）
- 新建：`docs/diagrams/` 目录下的 drawio 图（6 张）

---

### Task 1: Serena 代码核实 — 权限模型与隔离机制

**目标：** 用 Serena 语义工具精确追踪权限/搜索/管理体系的实现，确保 README 中的描述与代码一致。

**Files:** 无须修改，只读分析

- [ ] **Step 1: 分析认证依赖链**

  用 `find_referencing_symbols` 追踪 `get_current_user` / `get_current_teacher` / `get_current_student` 在路由层被哪些文件引用。

  执行：
  ```
  mcp__plugin_serena_serena__find_referencing_symbols
    name_path: "get_current_teacher"
    relative_path: "app/core/auth.py"
  ```

  记录：哪些路由用了哪个依赖，确认教师/学生/管理员的功能权限边界。

- [ ] **Step 2: 分析搜索权限过滤**

  用 `get_symbols_overview` 查看 `cross_search_service.py` 的所有方法，找到 `_build_permission_filter` 和权限检查相关函数。

  执行：
  ```
  mcp__plugin_serena_serena__get_symbols_overview
    relative_path: "app/services/cross_search_service.py"
  ```

  记录：`PermissionContext` 的 role/user_id/course_ids/class_ids 字段如何参与过滤，确认"ES 召回 → 角色二次过滤"的描述准确。

- [ ] **Step 3: 分析 ManagementSystem 模型的关系网**

  用 `find_referencing_symbols` 追踪 `ManagementSystem` 被哪些 service/repository 引用。

  执行：
  ```
  mcp__plugin_serena_serena__find_referencing_symbols
    name_path: "ManagementSystem"
    relative_path: "app/models/management_system.py"
  ```

  记录：管理体系到底影响了哪些业务模块（custom_field, management_system_record），确认它**不是**全局多租户容器。

- [ ] **Step 4: 核实提交历史中的关键变更**

  执行：
  ```bash
  git show 788f980 --stat
  git log --oneline --all --grep="role-based\|permission\|isolation\|scope" | head -10
  ```

  确认 `management_scope.py` 被删除 → `PermissionContext` 替代的演进路径。

- [ ] **Step 5: Commit 核实结论（可选）**

  将核实结论记录为临时笔记，供写 README 时参考。不单独 commit（这是准备工作）。

---

### Task 2: 绘制系统架构图 + 权限模型图（drawio）

**目标：** 用 drawio skill 绘制 README 所需的两张架构图。

**Files:**
- Create: `docs/diagrams/system-architecture.drawio`
- Create: `docs/diagrams/permission-model.drawio`

- [ ] **Step 1: 绘制系统架构图**

  使用 `drawio` skill，按以下层级绘制：

  ```
  [浏览器 (React)] 
       ↓ HTTP/SSE
  [FastAPI (app/main.py)]
       ↓
  ┌──────┼──────────┬───────────┬──────────┐
  [MySQL] [Redis] [Elasticsearch] [Celery] [RabbitMQ]
  [火山方舟 AI] [百度 OCR] [火山 ImageX]
  ```

  导出到 `docs/diagrams/system-architecture.drawio`

- [ ] **Step 2: 绘制权限模型图**

  使用 `drawio` skill，按 spec 中的三层结构绘制：

  ```
  角色(UserRole): Teacher | Student | Admin → 功能权限
      ↓
  数据可见性: 教师→自己的课程/作业/学生 | 学生→自己的提交 → 业务归属
      ↓
  管理体系(ManagementSystem): 自定义字段模板 + 记录分组 → 辅助扩展
  ```

  导出到 `docs/diagrams/permission-model.drawio`

- [ ] **Step 3: Commit 架构图**

  ```bash
  git add docs/diagrams/system-architecture.drawio docs/diagrams/permission-model.drawio
  git commit -m "docs: add system architecture and permission model diagrams"
  ```

---

### Task 3: 重写 README.md

**目标：** 按三层结构完整重写 README，修正权限描述，补充架构细节。

**Files:**
- Modify: `README.md`（完整重写）

- [ ] **Step 1: 写入 README 头部（项目简介 + 架构图引用）**

  ```markdown
  # CharWork — 汉字书写教学管理平台

  面向汉字书写教学场景的全栈管理平台，支撑 **教师布置作业 → 学生书写提交 → AI 批改反馈** 的完整教学闭环。

  ![系统架构图](docs/diagrams/system-architecture.drawio)

  ## 项目简介

  CharWork 服务于汉字书写教学场景，提供课程与班级管理、作业发布与提交、AI 智能批改、全文检索、数据导入导出等功能。系统通过**角色驱动（RBAC）** 控制功能权限，通过**业务归属关系**控制数据可见性，并借助**管理体系（自定义字段模板）** 实现灵活的数据扩展。

  ### 三种角色

  | 角色 | 核心能力 |
  |------|----------|
  | **教师** | 创建课程/班级，发布作业，批改书写，查看学生提交，全文检索，数据导入导出 |
  | **学生** | 加入班级，查看作业，提交书写练习，查看 AI 批改反馈，评论互动 |
  | **管理员** | 用户管理，操作日志审计 |
  ```

- [ ] **Step 2: 写入核心功能（按角色分组）**

  ```markdown
  ## 核心功能

  ### 教师端

  - **课程与班级管理**：创建课程 → 创建教学班级 → 添加学生 → 关联课程
  - **作业系统**：状态机驱动（草稿 → 发布 → 截止 → 归档），支持定时提醒
  - **书写批改**：查看学生提交 → AI 自动批改反馈 → 教师修正 → AI 总结
  - **汉字管理**：汉字 CRUD、笔画解析、字典检索、OCR 预填充
  - **全文检索**：跨模块搜索（课程/作业/学生/汉字/讨论），ES 索引 + 角色过滤
  - **数据导入导出**：Excel 批量操作，Celery 异步任务

  ### 学生端

  - **作业提交**：查看已发布作业 → 上传书写附件 → 查看批改结果
  - **AI 反馈**：接收书写评价，查看 AI 建议
  - **互动**：评论与讨论，站内消息

  ### 管理员端

  - **用户管理**：师生账号管理
  - **操作日志**：关键操作审计留痕

  ### 通用功能

  - **AI 对话**：集成火山方舟 / OpenAI 兼容接口，上下文记忆 + 工具调用
  - **站内消息**：用户间私信
  - **自定义字段**：基于管理体系的动态字段扩展（课程/作业/学生维度）
  - **附件管理**：统一附件上传存储（火山引擎 ImageX）
  ```

- [ ] **Step 3: 写入权限与数据隔离（修正核心）**

  ```markdown
  ## 权限与数据隔离

  CharWork 采用**双层权限模型**，角色控制功能权限，业务归属控制数据可见性。

  ![权限模型图](docs/diagrams/permission-model.drawio)

  ### 第一层：角色控制（功能权限）

  | 角色 | 枚举值 | 可执行操作 |
  |------|--------|-----------|
  | Teacher | `teacher` | 管理课程/班级/作业/学生，批改提交，导入导出 |
  | Student | `student` | 查看作业，提交书写，查看反馈，评论 |
  | Admin | `admin` | 用户管理，日志审计 |

  路由通过 `get_current_teacher` / `get_current_student` / `get_current_admin` 依赖注入实现角色校验（`app/core/auth.py`）。

  ### 第二层：数据可见性（业务归属）

  | 角色 | 可见数据范围 |
  |------|-------------|
  | Teacher | 自己的课程、自己班级的学生、自己发布的作业及提交 |
  | Student | 自己的提交、所在班级的课程和作业 |
  | Admin | 全部数据 |

  **搜索二次过滤**：Elasticsearch 做全文召回后，`PermissionContext` 按当前用户角色和业务归属做二次裁剪。教师只能搜到自己的课程/作业/学生，学生只能搜到自己的提交和关联内容（`app/services/cross_search_service.py`）。

  ### 管理体系（辅助扩展）

  `ManagementSystem` 是**自定义字段模板 + 记录分组**机制，不是全局多租户容器：

  - 每个用户自动拥有一个**默认管理体系**（汉字书写模板）
  - 教师可创建自定义体系，定义字段模板（如自定义课程/作业/学生字段）
  - `ManagementSystemRecord` 存储按体系分组的通用记录
  - **不影响**核心业务实体（课程/作业/学生）的权限隔离
  ```

- [ ] **Step 4: 写入技术栈、项目结构、API 概览**

  ```markdown
  ## 技术栈

  | 组件 | 技术 | 说明 |
  |------|------|------|
  | Web 框架 | FastAPI (Python 3.10+) | 异步 API，自动 OpenAPI 文档 |
  | ORM | SQLAlchemy 2.0 (async) | 异步数据库操作 |
  | 数据库 | MySQL 8.0+ | 主数据存储 |
  | 缓存 / 会话 | Redis 6+ | Token 会话、缓存 |
  | 搜索引擎 | Elasticsearch 8.11+ | 全文检索，Canal CDC 实时同步 |
  | 异步任务 | Celery (Redis broker) | 导入导出、AI 批改、通知 |
  | 搜索同步 | RabbitMQ (Canal CDC) | MySQL → ES 增量同步（可选） |
  | AI 服务 | 火山方舟 Ark / OpenAI 兼容 | AI 批改 + AI 对话 |
  | 图片服务 | 火山引擎 ImageX | 附件上传与存储 |
  | OCR | 百度 OCR | 汉字识别 |
  | 前端 | React 18 + Vite + TypeScript | `charwork_fronted` 仓库 |

  ## 项目结构

  ```
  app/
  ├── main.py               # FastAPI 应用入口，路由挂载
  ├── api/v1/               # 路由层（19 个路由模块）
  │   ├── routes_auth.py           # 注册/登录/Token
  │   ├── routes_assignments.py    # 作业 CRUD + 状态流转
  │   ├── routes_submissions.py    # 学生提交 + 批改
  │   ├── routes_courses.py        # 课程管理
  │   ├── routes_teaching_classes.py # 教学班级
  │   ├── routes_students.py       # 学生档案
  │   ├── routes_teachers.py       # 教师档案
  │   ├── routes_hanzi.py          # 汉字 CRUD + OCR
  │   ├── routes_ai_chat.py        # AI 对话
  │   ├── routes_search.py         # 全文检索
  │   ├── routes_comments.py       # 评论
  │   ├── routes_messages.py       # 站内消息
  │   ├── routes_import.py         # Excel 导入
  │   ├── routes_export.py         # Excel 导出
  │   ├── routes_management_systems.py # 管理体系配置
  │   ├── routes_custom_fields.py  # 自定义字段
  │   ├── routes_logs.py           # 操作日志
  │   ├── routes_student_classes.py # 学生班级关联
  │   └── routes_assignment_reminders.py # 作业提醒
  ├── core/                 # 基础设施
  │   ├── config.py         # 配置管理
  │   ├── database.py       # 数据库连接
  │   ├── auth.py           # 认证依赖注入
  │   ├── security.py       # 会话管理 + Token
  │   ├── redis_client.py   # Redis 客户端
  │   ├── celery_app.py     # Celery 配置
  │   └── logging_config.py # 日志配置
  ├── models/               # SQLAlchemy 模型（23 个实体）
  ├── repositories/         # 数据访问层（21 个仓储模块）
  ├── schemas/              # Pydantic 请求/响应模型
  ├── services/             # 业务逻辑层（34 个服务模块）
  ├── tasks/                # Celery 异步任务
  ├── utils/                # 工具函数（分页/ID 生成/图片处理）
  └── workers/              # 搜索同步 Worker
  ```

  ## API 概览

  所有接口前缀为 `/api/v1`。启动后访问 `/docs` 查看完整的 Swagger 文档。

  | 路由 | 说明 |
  |------|------|
  | `/auth` | 注册、登录、Token 管理 |
  | `/hanzi` | 汉字 CRUD、OCR 预填充 |
  | `/assignments` | 作业管理、状态流转 |
  | `/assignment-reminders` | 作业提醒管理 |
  | `/courses` | 课程管理 |
  | `/teaching-classes` | 教学班级 |
  | `/student-classes` | 学生班级关联 |
  | `/teachers` / `/students` | 师生档案 |
  | `/submissions` | 学生提交与批改 |
  | `/comments` | 评论与讨论 |
  | `/messages` | 站内消息 |
  | `/search` | 全文检索（跨模块） |
  | `/ai-chat` | AI 对话（SSE 流式） |
  | `/import` / `/export` | 数据导入导出 |
  | `/management-systems` | 管理体系配置 |
  | `/custom-fields` | 自定义字段管理 |
  | `/logs` | 操作日志 |
  ```

- [ ] **Step 5: 写入环境要求 + 快速开始**

  ```markdown
  ## 环境要求

  | 依赖 | 版本 | 必选 |
  |------|------|------|
  | Python | >= 3.10 | 是 |
  | MySQL | >= 8.0 | 是 |
  | Redis | >= 6.0 | 是 |
  | Elasticsearch | >= 8.11 | 是 |
  | RabbitMQ | 3.x | 否（搜索同步） |
  | Node.js | >= 18 | 否（前端） |

  ## 快速开始

  ### 1. 克隆仓库

  ```bash
  git clone <repo-url>
  cd charwork
  ```

  ### 2. 安装依赖

  ```bash
  python -m venv .venv
  # Windows
  .\.venv\Scripts\Activate.ps1
  # Linux/macOS
  source .venv/bin/activate

  pip install -e .
  ```

  ### 3. 配置环境变量

  创建 `.env` 文件（参考 `.env.example`）：

  ```dotenv
  APP_NAME=charwork-api
  ENVIRONMENT=dev

  # 跨域
  CORS_ORIGINS=["http://localhost:5173"]

  # 数据库
  MYSQL_HOST=localhost
  MYSQL_PORT=3306
  MYSQL_USER=root
  MYSQL_PASSWORD=your_password
  MYSQL_DB=charwork_db

  # Redis
  REDIS_URL=redis://localhost:6379/0

  # 安全
  SECRET_KEY=change_this_to_a_secure_random_key
  ALGORITHM=HS256
  ACCESS_TOKEN_EXPIRE_MINUTES=30

  # AI（可选）
  AI_PROVIDER=ark
  ARK_BASE_URL=https://...
  ARK_API_KEY=your_key
  ARK_MODEL=your_model

  # Elasticsearch
  ELASTICSEARCH_HOST=http://localhost:9200
  ELASTICSEARCH_INDEX_PREFIX=charwork
  ```

  ### 4. 初始化数据库

  ```bash
  # 创建数据库
  mysql -u root -p -e "CREATE DATABASE charwork_db DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;"

  # 执行迁移
  alembic upgrade head
  ```

  ### 5. 启动服务

  ```bash
  # 启动 API 服务（http://127.0.0.1:8000）
  uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

  # 启动 Celery Worker（异步任务，Windows 使用 -P solo）
  celery -A app.core.celery_app.celery_app worker -l info -P solo
  ```

  ### 6. 验证

  | 检查项 | 地址 |
  |--------|------|
  | 根路径 | http://127.0.0.1:8000 |
  | 健康检查 | http://127.0.0.1:8000/health |
  | API 文档 | http://127.0.0.1:8000/docs |
  ```

- [ ] **Step 6: 写入前端 + FAQ + 相关文档**

  ```markdown
  ## 前端

  前端仓库 `charwork_fronted`（React 18 + Vite + TypeScript）。

  ```bash
  cd ../charwork_fronted
  npm install
  npm run dev
  ```
  前端默认运行在 `http://localhost:5173`，通过 `VITE_API_URL` 环境变量配置后端地址（`.env.local`）：

  ```dotenv
  VITE_API_URL=http://127.0.0.1:8000
  ```

  ## 常见问题

  | 问题 | 排查方向 |
  |------|----------|
  | CORS 错误 | 检查 `.env` 中 `CORS_ORIGINS` 是否包含前端地址 |
  | 404 Not Found | 确认请求路径包含 `/api/v1` 前缀，对照 `/docs` 查看可用路由 |
  | 401 Unauthorized | 检查请求头 `Authorization: Bearer <token>`，确认 `/api/v1/auth/me` 可用 |
  | 数据库连接失败 | 确认 MySQL 已启动、`.env` 中 `MYSQL_*` 配置正确、已执行 `alembic upgrade head` |
  | Redis 连接失败 | 确认 Redis 已启动，检查 `REDIS_URL` 配置 |
  | ES 搜索无结果 | 确认 ES 已启动，检查 `ELASTICSEARCH_HOST` 配置，执行 `/api/v1/search/reindex` 重建索引 |
  | Celery 任务不执行 | 确认 Celery Worker 已启动，检查 Redis 连接 |

  ## 相关文档

  - [用户操作手册](docs/user-manual.md) — 按角色的详细操作指南（含流程图）
  - [API 文档](http://127.0.0.1:8000/docs) — 启动后端后访问 Swagger
  - [设计文档](docs/) — 模块设计文档

  ## License

  Private
  ```

- [ ] **Step 7: Commit README**

  ```bash
  git add README.md
  git commit -m "docs: rewrite README with corrected permission model and layered structure"
  ```

---

### Task 4: 绘制用户手册流程图（drawio）

**目标：** 用 drawio skill 绘制用户操作手册的 4 张业务流程图。

**Files:**
- Create: `docs/diagrams/assignment-state-machine.drawio`
- Create: `docs/diagrams/submission-feedback-pipeline.drawio`
- Create: `docs/diagrams/teacher-workflow.drawio`
- Create: `docs/diagrams/register-login-flow.drawio`

- [ ] **Step 1: 绘制作业生命周期状态机**

  ```
  ┌─────────┐  publish  ┌──────────┐  deadline  ┌──────────┐  archive  ┌─────────┐
  │  DRAFT  │ ────────→ │ PUBLISHED│ ─────────→ │  CLOSED  │ ────────→ │ ARCHIVED│
  └─────────┘           └──────────┘            └──────────┘           └─────────┘
       ↑                      │
       └────── unpublish ─────┘
  ```

  导出到 `docs/diagrams/assignment-state-machine.drawio`

- [ ] **Step 2: 绘制提交→批改→反馈链路（泳道图）**

  三个泳道：**学生** | **教师** | **AI 系统**

  ```
  学生: 查看作业 → 上传书写附件 → 提交
  教师: 查看提交列表 → 触发 AI 批改 / 手动批改
  AI:   接收批改请求 → 分析书写 → 生成反馈 → 返回结果
  学生: 查看 AI 反馈 → 评论互动
  ```

  导出到 `docs/diagrams/submission-feedback-pipeline.drawio`

- [ ] **Step 3: 绘制教师完整工作流**

  ```
  创建课程 → 创建班级 → 添加学生 → 关联课程
      ↓
  创建作业(选择班级) → 发布作业
      ↓
  等待学生提交
      ↓
  查看提交 → 触发AI批改 → 查看/修改批改 → 发布反馈
      ↓
  截止 → 归档
  ```

  导出到 `docs/diagrams/teacher-workflow.drawio`

- [ ] **Step 4: 绘制注册登录流程**

  ```
  访问平台 → 注册(选择角色) → 填写信息 → 登录 → Token 签发 → 角色路由
                                                              ├→ 教师后台
                                                              ├→ 学生后台
                                                              └→ 管理后台
  ```

  导出到 `docs/diagrams/register-login-flow.drawio`

- [ ] **Step 5: Commit 流程图**

  ```bash
  git add docs/diagrams/
  git commit -m "docs: add user manual flowcharts (assignment FSM, feedback pipeline, teacher workflow, login)"
  ```

---

### Task 5: 编写用户操作手册 docs/user-manual.md

**目标：** 编写按角色组织的用户操作手册，嵌入流程图，结合前后端代码描述实际操作步骤。

**Files:**
- Create: `docs/user-manual.md`

- [ ] **Step 1: 写入手册头部（系统概述 + 快速入门）**

  ```markdown
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
  ```

- [ ] **Step 2: 写入教师操作指南**

  ```markdown
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
  ```

- [ ] **Step 3: 写入学生操作指南**

  ```markdown
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
  ```

- [ ] **Step 4: 写入管理员操作指南 + 常见问题**

  ```markdown
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
  ```

- [ ] **Step 5: Commit 用户操作手册**

  ```bash
  git add docs/user-manual.md
  git commit -m "docs: add user operation manual with role-based guides and flowcharts"
  ```

---

### Task 6: 前端截图（可选 — Playwright）

**目标：** 用 Playwright 启动前端，截取关键页面配图。

> 注意：此步骤需要前后端均能正常启动。如果环境不满足，可跳过，手册用纯文字+流程图即可。

**Files:** 截图保存到 `docs/images/`

- [ ] **Step 1: 启动后端服务**

  ```bash
  cd D:/mywork/charwork
  # 后台启动后端
  uvicorn app.main:app --host 127.0.0.1 --port 8000 &
  ```

- [ ] **Step 2: 启动前端服务**

  ```bash
  cd D:/mywork/charwork_fronted
  npm run dev &
  ```

- [ ] **Step 3: 截取关键页面**

  使用 Playwright MCP：
  ```
  mcp__plugin_playwright_playwright__browser_navigate("http://localhost:5173/login")
  mcp__plugin_playwright_playwright__browser_take_screenshot(filename="docs/images/login.png")
  
  # 登录后截取教师 Dashboard
  # 登录后截取学生作业列表
  # 登录后截取作业详情/批改页面
  ```

- [ ] **Step 4: 将截图嵌入用户手册**

  在 `docs/user-manual.md` 对应位置添加：
  ```markdown
  ![登录页面](images/login.png)
  ```

- [ ] **Step 5: Commit 截图**

  ```bash
  git add docs/images/ docs/user-manual.md
  git commit -m "docs: add frontend screenshots to user manual"
  ```

---

### Task 7: 自审 + 收尾

- [ ] **Step 1: 交叉检查**

  - README 中的权限描述是否与 `app/core/auth.py` + `app/services/cross_search_service.py` 实际逻辑一致
  - 操作手册中的 API 路由/前端路由是否与实际代码匹配
  - 流程图是否遗漏关键状态/步骤
  - 所有内部链接（`docs/diagrams/`、`docs/user-manual.md`）是否有效

- [ ] **Step 2: 检查 git 状态**

  ```bash
  git status
  git log --oneline -5
  ```

  确认所有文件已提交，无遗漏。

- [ ] **Step 3: 标记完成**

  向用户报告产出物清单和最终状态。

---