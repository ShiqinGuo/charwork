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
| module | keyword | 模块标识 hanzi/assignment/discussion/course/teaching_class/student |
| source_id | keyword | 业务主键ID |
| management_system_ids | keyword | 可访问的管理系统作用域ID集合 |
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

权限要求：
- 接口必须登录
- 请求必须绑定管理系统作用域
- 检索结果必须受 `management_system_id` 过滤
- 学生角色仅返回其可访问课程/班级范围内的数据

## 4. 核心业务逻辑

### 4.1 启动检查与首轮初始化流程

1. 应用启动时检查索引是否存在，不存在则创建
2. 应用启动时始终执行一次业务索引全量补齐
3. 共享字典索引初始化与业务索引初始化分开处理，互不影响

### 4.2 CDC 增量同步流程

1. Canal 监听 MySQL Binlog，仅订阅配置驱动开启的业务表，当前默认包括 `assignment/comment/hanzi/course/teaching_class/student`
2. Canal 以 flat message 发送到 RabbitMQ 队列 `canal.search.sync`
3. 独立轻量级监听服务按注册表识别业务模块并消费 RabbitMQ 消息
4. 监听服务调用检索同步逻辑：insert/update 按注册表从数据库重建文档并执行 ES upsert，delete 执行 ES delete
5. 通过固定文档ID保证重复投递下的幂等覆盖，消费失败走 RabbitMQ 重投或死信

### 4.3 检索流程

1. 使用 multi_match 查询 title 与 content
2. 按 `management_system_ids` 过滤到当前管理系统作用域
3. 学生角色再按课程/班级可见性做二次权限过滤
4. 按 score 相关性排序
5. 将命中结果统一映射为 `module + id + title + content + score`
6. 返回前端统一结构，前端可按 module 分组展示

## 5. 关键技术使用

- Elasticsearch Async 客户端：异步化检索与重建
- Canal + RabbitMQ：业务表变更解耦分发到检索同步服务
- 统一索引模型：降低业务侧多接口联查复杂度
- multi_match 检索：兼顾标题与内容相关性
- ngram 分析器：增强中文内容检索召回能力
