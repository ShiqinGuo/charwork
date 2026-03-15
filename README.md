# CharWork 初始化

本文档用于在本机完成 CharWork 后端（FastAPI）与前端（Vite + React）初始化、启动与联调。

## 0. 端口与地址约定

- 后端（FastAPI）：http://127.0.0.1:8000
- 前端（Vite Dev Server）：http://localhost:5173
- MySQL：127.0.0.1:3306
- Redis：127.0.0.1:6379

后端路由前缀：
- `/api/v1/*`（见 `app/main.py`）

## 1. 环境准备

### 1.1 必需软件

- Python >= 3.10
- Node.js >= 18（建议 LTS）
- MySQL >= 8
- Redis >= 6

### 1.2 拉起 MySQL / Redis

确保 MySQL 与 Redis 已启动，并能从本机连接：
- MySQL：`root` 用户或你自定义用户可连接
- Redis：默认 `redis://localhost:6379/0`

## 2. 后端初始化与启动（d:\mywork\charwork）

### 2.1 创建虚拟环境并安装依赖

在 PowerShell 中执行：

```powershell
cd d:\mywork\charwork

python -m venv .venv
.\.venv\Scripts\Activate.ps1

pip install -e .
```

### 2.2 配置环境变量（.env）

后端使用 `d:\mywork\charwork\.env`（代码读取方式见 `app/core/config.py`）。

关键配置项（示例，按你的环境修改；不要提交真实密钥到仓库）：

```dotenv
APP_NAME=charwork-api
ENVIRONMENT=dev

# 允许前端跨域访问（开发环境）
CORS_ORIGINS=["http://localhost:5173"]

# 数据库（示例）
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DB=charwork_db
DATABASE_URL=mysql+aiomysql://root:your_password@localhost:3306/charwork_db

# Redis（Celery broker/backend + 导入任务日志）
REDIS_URL=redis://localhost:6379/0

# 安全（开发可用固定值，生产务必替换）
SECRET_KEY=change_this_to_a_secure_random_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

### 2.3 创建数据库

用 MySQL 客户端创建数据库（示例）：

```sql
CREATE DATABASE charwork_db DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
```

### 2.4 初始化数据库表（Alembic）

项目已包含 `alembic.ini` 与 `migrations/env.py`，但当前 `migrations/versions` 可能尚未生成。

第一次初始化（在后端 venv 激活状态下）：

```powershell
cd d:\mywork\charwork

# 1) 生成首个迁移（会创建 migrations\versions\*.py）
alembic revision --autogenerate -m "init"

# 2) 执行迁移
alembic upgrade head
```

后续模型变更：
```powershell
alembic revision --autogenerate -m "xxx"
alembic upgrade head
```

### 2.5 启动后端服务

```powershell
cd d:\mywork\charwork
.\.venv\Scripts\Activate.ps1

uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

验证：
- http://127.0.0.1:8000/health
- http://127.0.0.1:8000/docs

### 2.6 启动 Celery Worker（可选但建议）

导入任务等异步能力依赖 Celery + Redis。Windows 建议使用 `-P solo`：

```powershell
cd d:\mywork\charwork
.\.venv\Scripts\Activate.ps1

celery -A app.core.celery_app.celery_app worker -l info -P solo
```

## 3. 前端初始化与启动（d:\mywork\charwork_fronted）

### 3.1 安装依赖

```powershell
cd d:\mywork\charwork_fronted
npm install
```

### 3.2 配置前端 API 地址（.env.local）

前端请求基地址由 `VITE_API_URL` 控制（见 `src/utils/request.ts`）。

新建文件 `d:\mywork\charwork_fronted\.env.local`：

```dotenv
VITE_API_URL=http://127.0.0.1:8000
```

### 3.3 启动前端开发服务器

```powershell
cd d:\mywork\charwork_fronted
npm run dev
```

访问：
- http://localhost:5173

## 4. 前后端联调要点（必须对齐）

### 4.1 CORS 必须放行前端地址

后端 `.env` 中确保：
- `CORS_ORIGINS=["http://localhost:5173"]`

如果你更换了前端端口或域名，要同步修改。

### 4.2 API 前缀必须一致

后端实际前缀是：
- `/api/v1`

例如汉字接口为：
- `GET /api/v1/hanzi?skip=0&limit=20&search=...`
- `POST /api/v1/hanzi`

如果前端写成 `/hanzi` 或 `/characters` 会直接 404。

### 4.3 认证 Token（Bearer）

前端 Axios 会自动在请求头加：
- `Authorization: Bearer <token>`

建议后端提供（或确保存在）：
- `POST /api/v1/auth/login` -> 返回 `{ access_token, token_type }`
- `GET /api/v1/auth/me` -> 返回当前用户信息（前端登录后会调用，用于识别角色与跳转）

若前端登录后一直跳回登录页，优先检查：
- Network 是否 401
- 后端是否实现 `/api/v1/auth/me`
- Token 是否确实写入了 `localStorage(token)`

## 5. 常见问题排查

### 5.1 浏览器报 CORS 错误
- 确认后端 `.env` 的 `CORS_ORIGINS` 包含当前前端地址（含端口）
- 确认后端确实读到了 `.env`（最简单：改一下 `APP_NAME` 看 /docs 是否变化）
- 确认前端 `VITE_API_URL` 指向后端可访问地址

### 5.2 404（接口不存在）
- 检查前端请求路径是否带 `/api/v1`
- 打开后端 `/docs` 对照实际路径

### 5.3 401（未授权）
- 检查请求头是否带 `Authorization: Bearer ...`
- 检查后端是否校验 token，以及 `/api/v1/auth/me` 是否可用
- 清空 `localStorage token` 后重新登录（避免旧 token）

### 5.4 数据库相关报错
- 确认 MySQL 已启动、账号密码正确
- 确认已执行 `alembic upgrade head`
- 确认 `.env` 中 `DATABASE_URL` 与 `MYSQL_*` 一致

## 6. 生产构建（可选）

前端构建：
```powershell
cd d:\mywork\charwork_fronted
npm run build
```

后端生产建议：
- 使用 `uvicorn`/`gunicorn` 部署
- `SECRET_KEY` 使用强随机值
- `CORS_ORIGINS` 限制为真实域名
- 不要提交 `.env` 到仓库