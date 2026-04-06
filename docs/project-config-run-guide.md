# 项目配置与运行文档

## 1. 环境要求

- Python 3.10+
- MySQL 8+
- Redis 6+
- Elasticsearch 8+
- Node.js 18+（前端联调时）

## 2. 后端依赖安装

```powershell
cd d:\mywork\charwork
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

## 3. 环境变量配置

在 `d:\mywork\charwork\.env` 配置：

```dotenv
APP_NAME=charwork-api
ENVIRONMENT=dev
CORS_ORIGINS=["http://localhost:5173"]

MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DB=charwork_db
DATABASE_URL=mysql+aiomysql://root:your_password@localhost:3306/charwork_db

REDIS_URL=redis://localhost:6379/0

# 如果 Redis 配置了密码（requirepass）：
# - 无用户名（常见）：redis://:password@host:6379/0
# - 有用户名（Redis 6 ACL）：redis://username:password@host:6379/0
# 注意：password 如包含特殊字符（如 @ : / ? #），需要进行 URL 编码

ELASTICSEARCH_URL=http://localhost:9200
ELASTICSEARCH_INDEX_PREFIX=charwork
SEARCH_SYNC_ENABLED=true
SEARCH_SYNC_RABBITMQ_URL=amqp://guest:guest@localhost:5672/
SEARCH_SYNC_RABBITMQ_QUEUE=canal.search.sync
SEARCH_SYNC_RABBITMQ_PREFETCH=50
SEARCH_SYNC_CANAL_SCHEMA=charwork_db
SEARCH_SYNC_CANAL_TABLES=assignment,comment,hanzi,course,teaching_class,student,hanzi_dictionary

SECRET_KEY=change_this_to_a_secure_random_key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

MySQL 需开启 Binlog（CDC 监听前提）：

```ini
[mysqld]
server-id=1
log-bin=mysql-bin
binlog_format=ROW
binlog_row_image=FULL
```

Canal 需开启 RabbitMQ MQ 模式并投递到检索队列，示例：

```properties
canal.serverMode=rabbitmq
canal.mq.flatMessage=true
canal.mq.topic=canal.search.sync
canal.mq.dynamicTopic=charwork_db.assignment,charwork_db.comment,charwork_db.hanzi,charwork_db.course,charwork_db.teaching_class,charwork_db.student,charwork_db.hanzi_dictionary
```

修改 `SEARCH_SYNC_CANAL_TABLES` 或 `canal.mq.dynamicTopic` 后，需要同时重启：

- API 服务
- `python -m app.services.search_sync_worker` 检索监听进程

如果服务器使用 systemd / supervisor / docker compose 等自启动方式，还需要同步更新自启动配置中的环境变量与启动参数，否则机器重启后会回到旧配置。

## 4. 数据库初始化

首次迁移：

```powershell
cd d:\mywork\charwork
.\.venv\Scripts\Activate.ps1
alembic revision --autogenerate -m "feature teaching-interaction-search"
alembic upgrade head
```

本次新增/变更的关键表：
- `event_outbox`
- `comment_like`
- `comment`（新增 parent_id/root_id/reply_to_user_id/reply_count/like_count）
- `assignment`（新增 deadline/archived 状态值）

## 5. 启动服务

### 5.1 启动后端 API

```powershell
cd d:\mywork\charwork
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 5.2 启动 Celery Worker

```powershell
cd d:\mywork\charwork
.\.venv\Scripts\Activate.ps1
celery -A app.core.celery_app.celery_app worker -l info -P solo
```

### 5.3 启动检索增量监听服务（独立进程）

```powershell
cd d:\mywork\charwork
.\.venv\Scripts\Activate.ps1
python -m app.services.search_sync_worker
```

## 6. Elasticsearch 初始化与检索

### 6.1 启动行为

- 应用启动时自动检查索引：
  - 无索引：自动创建
  - 索引为空：自动做一次首轮全量导入
  - 索引非空：跳过初始化
- 增量同步由 Canal + RabbitMQ + 独立监听服务完成

### 6.2 手动补齐跨模块索引

```http
POST /api/v1/search/reindex
```

该接口会按业务主键覆盖写入，不会先清空索引。

### 6.3 执行跨模块检索

```http
GET /api/v1/search?keyword=作业&modules=assignment&modules=discussion&limit=20
```

## 7. 功能验证建议

- 作业状态机：
  - 创建作业（draft）
  - 调用 `/api/v1/assignments/{id}/transitions` 触发 publish/reach_deadline/archive
- 评论扁平化：
  - 根评论 + 回复评论后调用 `/api/v1/comments/flat`
- 点赞原子性：
  - 并发调用 `/api/v1/comments/{comment_id}/likes`，确认单用户不会重复点赞
- Outbox：
  - 提交作业后检查 `event_outbox` 是否写入并由任务更新为 published
- 检索增量同步：
  - 更新 assignment/comment/hanzi/student 任一数据
  - 观察检索监听服务日志已消费 RabbitMQ 消息
  - 调用 `/api/v1/search` 验证增量变更可被检索到

## 8. 前端联调

在 `d:\mywork\charwork_fronted\.env.local` 配置：

```dotenv
VITE_API_URL=http://127.0.0.1:8000
```

启动：

```powershell
cd d:\mywork\charwork_fronted
npm install
npm run dev
```
