# 教学模块设计架构

## 1. 模块目标

教学模块覆盖作业全生命周期管理与作业提交一致性处理，核心目标：
- 通过状态机约束作业状态流转：草稿 -> 发布 -> 截止 -> 归档
- 保证提交作业与异步通知事件的一致性，避免主流程成功但消息丢失

## 2. 数据库表设计

### assignment

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | varchar(50), PK | 作业ID |
| teacher_id | varchar(50), FK teacher.id | 教师ID |
| title | varchar(200) | 标题 |
| description | text, nullable | 描述 |
| hanzi_ids | json, nullable | 关联汉字ID列表 |
| due_date | datetime, nullable | 截止时间 |
| status | varchar(20) | draft/published/deadline/archived/closed |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |

### submission

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | varchar(50), PK | 提交ID |
| assignment_id | varchar(50), FK assignment.id | 作业ID |
| student_id | varchar(50), FK student.id | 学生ID |
| content | text, nullable | 提交内容 |
| image_paths | json, nullable | 图片路径数组 |
| status | varchar(20) | submitted/graded |
| score | int, nullable | 分数 |
| feedback | text, nullable | 评语 |
| submitted_at | datetime | 提交时间 |
| graded_at | datetime, nullable | 批改时间 |

### event_outbox

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | varchar(50), PK | 事件ID |
| aggregate_type | varchar(50) | 聚合类型，如 submission |
| aggregate_id | varchar(50), index | 聚合ID |
| event_type | varchar(100) | 事件类型，如 submission.created |
| payload | text | 事件载荷JSON |
| status | varchar(20), index | pending/published/failed |
| retry_count | int | 重试次数 |
| error_message | text, nullable | 失败原因 |
| created_at | datetime | 创建时间 |
| published_at | datetime, nullable | 发布时间 |

## 3. 接口设计

### 作业接口

- `GET /api/v1/assignments`：分页查询作业
- `POST /api/v1/assignments`：创建作业
- `GET /api/v1/assignments/{id}`：查询作业详情
- `PUT /api/v1/assignments/{id}`：更新作业
- `DELETE /api/v1/assignments/{id}`：删除作业
- `POST /api/v1/assignments/{id}/transitions`：触发状态机事件流转
- `POST /api/v1/assignments/transitions/reach-deadline`：批量处理到期作业

请求体示例（状态流转）：

```json
{
  "event": "publish"
}
```

### 提交接口

- `POST /api/v1/assignments/{assignment_id}/submissions`：提交作业（含 outbox 事件写入）
- `GET /api/v1/assignments/{assignment_id}/submissions`：查询作业提交列表
- `GET /api/v1/submissions/{id}`：提交详情
- `PUT /api/v1/submissions/{id}/grade`：批改提交

## 4. 核心业务逻辑

### 4.1 状态机流转规则

状态机按事件驱动，不允许跨状态随意更新：
- draft + publish -> published
- published + reach_deadline -> deadline
- published + archive -> archived
- deadline + archive -> archived

非法事件触发直接返回业务错误，防止数据进入非法状态。

### 4.2 截止任务处理

通过 `reach_deadline_assignments` 逻辑按当前时间扫描：
- 条件：status = published 且 due_date <= now
- 命中后统一执行状态机事件 `reach_deadline`

该接口可以被定时任务调度调用。

### 4.3 Outbox 一致性流程

提交流程：
1. 写入 submission 主业务记录
2. 同一事务写入 event_outbox（status=pending）
3. 事务提交成功后触发异步发布任务
4. 发布任务扫描 pending 事件并标记 published 或 failed

通过“主业务 + 事件记录”同事务提交，保障一致性。

## 5. 关键技术使用

- 状态机模式：`AssignmentStateMachine` 维护统一状态图与事件规则
- Event Outbox：`event_outbox` 表承接可靠事件投递
- Celery 异步任务：`publish_outbox_events` 实现事件发布与状态回写
- SQLAlchemy Async：统一异步事务与持久化操作
