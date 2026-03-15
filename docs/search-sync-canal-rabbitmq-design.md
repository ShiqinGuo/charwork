# 检索增量同步服务设计（Canal + RabbitMQ）

## 1. 目标

- 将检索同步从主应用解耦为独立轻量级服务
- 使用 Canal 监听 MySQL Binlog，避免业务层双写 ES
- 通过 RabbitMQ 解耦 CDC 采集与 ES 写入，提升可观测性与可恢复性

## 2. 架构

- Canal Server：订阅 MySQL Binlog，输出 flat message
- RabbitMQ：接收 Canal 消息，提供持久化队列
- Search Sync Worker：独立进程消费消息，写入 Elasticsearch
- API 服务：仅负责启动时索引检查与首轮初始化，不承担增量监听

数据流：
1. `assignment/comment/hanzi/student` 发生变更
2. Canal 产出 insert/update/delete 事件并投递 RabbitMQ
3. Worker 消费事件，调用 `CrossSearchService.apply_cdc_change`
4. ES upsert/delete 完成增量同步

## 3. 队列与可靠性策略

- 队列：`canal.search.sync`（durable）
- 消费模式：手动 ack，处理成功后确认
- 失败策略：消息处理异常不 requeue，建议在 RabbitMQ 配置 DLX
- 幂等策略：ES 文档 ID 固定为 `{module}_{id}`，重复消费仅覆盖
- 顺序策略：默认队列顺序消费；若扩容多消费者，需按表主键分片路由

## 4. 消息格式约束（flat message）

最小字段：
- `database`
- `table`
- `type`（INSERT/UPDATE/DELETE）
- `isDdl`
- `data`（数组，每项为行数据）

Worker 仅处理：
- `database == SEARCH_SYNC_CANAL_SCHEMA`
- `table in SEARCH_SYNC_CANAL_TABLES`
- `isDdl == false`

## 5. 服务部署建议

- 进程入口：`python -m app.services.search_sync_worker`
- 部署方式：systemd / supervisor / k8s Deployment（副本建议从 1 开始）
- 健康检查：结合日志与 RabbitMQ consumer count 监控
- 监控项：
  - 消费速率、积压长度、失败数
  - ES 写入耗时与失败率
  - 重试与死信队列长度

## 6. 回滚与补偿策略

- Canal 或 Worker 故障恢复后继续从 MQ 未确认消息消费
- 极端情况下可调用 `/api/v1/search/reindex` 做数据补齐
- 若出现映射升级，先灰度新索引再切 alias，避免检索中断
