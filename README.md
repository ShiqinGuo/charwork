# CharWork

汉字书写教学管理平台后端服务，基于 FastAPI 构建。

## 项目简介

CharWork 是一个面向汉字书写教学场景的管理平台，支持教师创建课程与作业、学生提交书写练习、AI 智能辅导、OCR 字形识别等功能。系统采用多租户架构，通过「管理体系」实现数据隔离。

### 核心功能

- 汉字管理：汉字 CRUD、笔画解析、字典检索、OCR 预填充
- 作业系统：状态机驱动（草稿 → 发布 → 截止 → 归档），支持定时提醒
- 课程与班级：课程管理、教学班级、师生关联
- 学生作业提交与批改
- 评论与点赞、站内消息
- AI 对话：集成火山方舟 / OpenAI 兼容接口，支持上下文记忆与工具调用
- 全文检索：基于 Elasticsearch，支持跨实体搜索
- 数据导入导出：Excel 批量操作，Celery 异步任务
- 多租户：管理体系级别的数据隔离与权限控制

## 技术栈

| 组件 | 技术 |
|------|------|
| Web 框架 | FastAPI |
| ORM | SQLAlchemy 2.0 (async) |
| 数据库 | MySQL 8+ |
| 数据库迁移 | Alembic |
| 缓存 / 消息队列 | Redis |
| 搜索引擎 | Elasticsearch 8 |
| 异步任务 | Celery |
| 搜索同步 | RabbitMQ (Canal CDC) |
| AI 服务 | 火山方舟 Ark / OpenAI 兼容接口 |
| 图片服务 | 火山引擎 ImageX |
| OCR | 百度 OCR |

## 项目结构

```
app/
├── api/v1/          # 路由层（18 个路由模块）
├── core/            # 基础设施（配置、数据库、认证、Redis、ES、Celery）
├── models/          # SQLAlchemy 模型（20+ 实体）
├── repositories/    # 数据访问层
├── schemas/         # Pydantic 请求/响应模型
├── services/        # 业务逻辑层
├── tasks/           # Celery 异步任务（导入、通知）
└── utils/           # 工具函数（分页、ID 生成、图片处理等）
```

## API 概览

所有接口前缀为 `/api/v1`，主要模块：

| 路由 | 说明 |
|------|------|
| `/auth` | 注册、登录、Token 管理 |
| `/hanzi` | 汉字 CRUD、OCR 预填充 |
| `/assignments` | 作业管理、状态流转、提醒 |
| `/courses` | 课程管理 |
| `/teaching-classes` | 教学班级 |
| `/teachers` / `/students` | 师生档案 |
| `/submissions` | 学生提交与批改 |
| `/comments` | 评论与讨论 |
| `/messages` | 站内消息 |
| `/search` | 全文检索 |
| `/ai-chat` | AI 对话 |
| `/import` / `/export` | 数据导入导出 |
| `/management-systems` | 管理体系配置 |

启动后访问 `/docs` 查看完整的 Swagger 文档。

## 环境要求

- Python >= 3.10
- MySQL >= 8
- Redis >= 6
- Elasticsearch >= 8.11
- RabbitMQ（搜索同步，可选）
- Node.js >= 18（前端，仓库 `charwork_fronted`）

## 快速开始

### 1. 安装依赖

```bash
python -m venv .venv
# Windows
.\.venv\Scripts\Activate.ps1
# Linux/macOS
source .venv/bin/activate

pip install -e .
```

### 2. 配置环境变量

复制 `.env.example`（或手动创建 `.env`），关键配置项：

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
```

### 3. 初始化数据库

```bash
# 创建数据库
mysql -u root -p -e "CREATE DATABASE charwork_db DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;"

# 执行迁移
alembic upgrade head
```

### 4. 启动服务

```bash
# 启动 API 服务
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# 启动 Celery Worker（异步任务，Windows 使用 -P solo）
celery -A app.core.celery_app.celery_app worker -l info -P solo
```

验证：
- 根路径：http://127.0.0.1:8000
- 健康检查：http://127.0.0.1:8000/health
- API 文档：http://127.0.0.1:8000/docs

## 前端

前端仓库位于 `charwork_fronted`（Vite + React），开发服务器默认运行在 `http://localhost:5173`。

```bash
cd charwork_fronted
npm install
npm run dev
```

前端通过 `VITE_API_URL` 环境变量指向后端地址，在 `.env.local` 中配置：

```dotenv
VITE_API_URL=http://127.0.0.1:8000
```

## 常见问题

| 问题 | 排查方向 |
|------|----------|
| CORS 错误 | 检查 `.env` 中 `CORS_ORIGINS` 是否包含前端地址 |
| 404 | 确认请求路径包含 `/api/v1` 前缀，对照 `/docs` |
| 401 | 检查请求头 `Authorization: Bearer <token>`，确认 `/api/v1/auth/me` 可用 |
| 数据库报错 | 确认 MySQL 已启动、`.env` 配置正确、已执行 `alembic upgrade head` |

## License

Private
