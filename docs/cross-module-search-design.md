# 跨模块检索设计架构

## 1. 模块目标

构建统一全文检索引擎，解决汉字、作业、讨论内容分散在不同接口与查询逻辑中的问题：
- 一次查询返回跨模块结果
- 统一关键词入口与分页参数
- 支持中文最小粒度切分提升召回

## 2. 数据与索引设计

### Elasticsearch 索引

- 索引名：`{ELASTICSEARCH_INDEX_PREFIX}_global_search`
- 文档模型：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| module | keyword | 模块标识 hanzi/assignment/discussion/student |
| source_id | keyword | 业务主键ID |
| title | text | 标题字段 |
| content | text | 正文字段 |

### 分词策略

使用 `ngram tokenizer(min_gram=1,max_gram=2)`：
- 兼容中文单字/短词检索
- 降低对外部分词插件依赖
- 适配汉字与作业文本混合场景

## 3. 接口设计

- `GET /api/v1/search`：跨模块关键词检索
- `POST /api/v1/search/reindex`：手动触发全量补齐（不清空索引，按ID覆盖）

检索参数：
- `keyword`：必填，关键词
- `modules`：可选，模块过滤数组
- `limit`：返回条数

## 4. 核心业务逻辑

### 4.1 启动检查与首轮初始化流程

1. 应用启动时检查索引是否存在，不存在则创建
2. 检查索引文档数，若为 0 执行首轮全量导入
3. 若索引已有文档则跳过初始化，不做重复全量同步

### 4.2 CDC 增量同步流程

1. Canal 监听 MySQL Binlog，仅订阅 `assignment/comment/hanzi/student`
2. Canal 以 flat message 发送到 RabbitMQ 队列 `canal.search.sync`
3. 独立轻量级监听服务消费 RabbitMQ，解析 insert/update/delete
4. 监听服务调用检索同步逻辑：insert/update 执行 ES upsert，delete 执行 ES delete
5. 通过固定文档ID保证重复投递下的幂等覆盖，消费失败走 RabbitMQ 重投或死信

### 4.3 检索流程

1. 使用 multi_match 查询 title 与 content
2. 按 score 相关性排序
3. 将命中结果统一映射为 `module + id + title + content + score`
4. 返回前端统一结构，前端可按 module 分组展示

## 5. 关键技术使用

- Elasticsearch Async 客户端：异步化检索与重建
- Canal + RabbitMQ：业务表变更解耦分发到检索同步服务
- 统一索引模型：降低业务侧多接口联查复杂度
- multi_match 检索：兼顾标题与内容相关性
- ngram 分析器：增强中文内容检索召回能力
