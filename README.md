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
