# 互动与通知模块设计架构

## 1. 模块目标

互动模块聚焦讨论区评论与点赞高并发一致性：
- 评论采用两级扁平化结构，避免树形递归查询
- 点赞采用 Redis Lua + 数据库唯一索引，保证并发原子防重
- 通知模块基于 Celery 执行异步发送和 outbox 发布

## 2. 数据库表设计

### comment

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | varchar(50), PK | 评论ID |
| user_id | varchar(50), FK user.id | 评论用户 |
| target_type | varchar(20) | 目标类型 assignment/submission |
| target_id | varchar(50), index | 目标ID |
| parent_id | varchar(50), nullable, index | 父评论ID，根评论为空 |
| root_id | varchar(50), nullable, index | 根评论ID |
| reply_to_user_id | varchar(50), nullable | 被回复用户 |
| content | text | 评论内容 |
| reply_count | int | 回复数 |
| like_count | int | 点赞数 |
| created_at | datetime | 创建时间 |

### comment_like

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | varchar(50), PK | 点赞记录ID |
| comment_id | varchar(50), FK comment.id | 评论ID |
| user_id | varchar(50), FK user.id | 用户ID |
| created_at | datetime | 点赞时间 |

联合唯一约束：
- `uq_comment_like_comment_user(comment_id, user_id)`

## 3. 接口设计

- `GET /api/v1/comments`：基础评论列表
- `GET /api/v1/comments/flat`：扁平化评论列表（根评论 + replies）
- `POST /api/v1/comments`：发布评论或回复评论
- `POST /api/v1/comments/{comment_id}/likes`：点赞/取消点赞

点赞请求体示例：

```json
{
  "user_id": "student_001",
  "action": "like"
}
```

## 4. 核心业务逻辑

### 4.1 扁平化评论查询

查询流程：
1. 按目标分页查询根评论（parent_id is null）
2. 一次性按 root_id in (...) 查询全部二级回复
3. 在服务层按 root_id 分组组装为 `root + replies`

该方式避免递归查询和多层 join，适合讨论区热点读取。

### 4.2 回复写入规则

- `parent_id` 不为空时，必须校验父评论存在
- 回复记录自动继承 `root_id`，并默认 `reply_to_user_id=父评论.user_id`
- 父评论 `reply_count` 自增，便于列表展示

### 4.3 点赞原子性规则

点赞逻辑使用 Lua 脚本保证 Redis 层原子判断：
- like：key 不存在时写入并返回 1，已存在返回 0
- unlike：key 存在时删除并返回 1，不存在返回 0

数据库层通过唯一索引兜底防重，即便并发穿透也不会重复点赞记录。

## 5. 关键技术使用

- Redis Lua 脚本：把“判断 + 写入/删除”变为单条原子操作
- MySQL 联合唯一索引：提供最终一致约束
- SQLAlchemy Async：统一点赞记录与评论计数持久化
- Celery 异步任务：支撑通知发送与 outbox 事件发布
