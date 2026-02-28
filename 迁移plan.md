# HanziProject 后端迁移至 FastAPI 异步方案

## 1. 现状功能盘点

### 1.1 技术栈与关键模块
- 后端框架：Django 4.2
- 数据库：MySQL
- 缓存与任务：Redis + Celery + RabbitMQ
- 图像与识别：火山引擎 AI 图像识别
- 数据处理：pandas、openpyxl

关键模块与职责：
- 数据模型：hanzi_app/models.py（Hanzi、Category）
- 业务视图：hanzi_app/views.py（页面渲染、API、导入导出、日志）
- 识别能力：hanzi_app/recognition.py
- 汉字标准图生成与笔顺拼音：hanzi_app/generate.py
- 导入处理：hanzi_app/data_importer.py
- 异步任务：hanzi_app/tasks.py + hanzi_project/celery.py

### 1.2 数据模型
重新架构数据模型，ID统一采用雪花算法

### 1.3 主要功能与接口现状
1) 汉字管理
- 列表与筛选、分页展示
- 详情查看（拼音、笔顺）
- 新增、编辑、删除
- 结构类型生成编号
- 上传用户书写图片并生成标准图

2) 汉字检索
- 多条件筛选（结构、等级、简繁体、笔画数等）
- 笔顺检索
- 单字笔画数查询

3) 数据导入
- JSON/Excel 导入
- ZIP 图片包解压与匹配
- 识别、字段补全（解耦功能）
- SSE 进度推送
- Celery 异步导入任务
- 导入结果 Excel 与失败日志管理

4) 数据导出
- 选择字段导出
- 可选导出用户图片、标准图片
- 支持 Excel 内嵌图片
- 下载与清理导出文件

5) 基础能力
- 识别汉字（简/繁）
- 生成标准汉字图
- 拼音与笔顺获取

## 2. FastAPI 异步目标架构

### 2.1 总体架构
分层结构：
- API 层：FastAPI 路由与请求校验
- 服务层：业务编排、规则校验、事务边界
- 数据访问层：异步 ORM/SQLAlchemy
- 任务层：Celery 异步任务 + Redis 状态缓存
- 资源层：媒体文件、导入导出结果存储

### 2.2 关键技术选择
- Web 框架：FastAPI + Uvicorn
- ORM：SQLAlchemy 2.0 Async
- 迁移：Alembic
- 缓存：Redis
- 消息队列：RabbitMQ
- 任务队列：Celery
- 前端页面：迁移至Vue 3单页应用

### 2.3 目录结构建议
```
app/
  main.py
  core/
    config.py
    logging.py
  api/
    v1/
      routes_hanzi.py
      routes_import.py
      routes_export.py
      routes_logs.py
  models/
    hanzi.py
    category.py
  schemas/
    hanzi.py
    import_export.py
  services/
    hanzi_service.py
    import_service.py
    export_service.py
    log_service.py
  repositories/
    hanzi_repo.py
  tasks/
    import_tasks.py
  utils/
    file_utils.py
    image_utils.py
```

## 3. 功能需求拆解与迁移点

### 3.1 汉字管理与检索
需求点：
- 列表查询：多条件筛选与分页
- 详情：拼音、笔顺、图片展示
- 新增：结构生成 ID、上传图片、自动笔顺与标准图
- 编辑：字段更新、图片替换
- 删除：数据库记录与图片文件

迁移要点：
- SQLAlchemy Async 模型与查询
- 上传文件保存与路径规则对齐（uploads、standard_images）
- 结构 ID 生成逻辑迁移为服务层方法

### 3.2 笔画与笔顺服务
需求点：
- 单字笔画数查询
- 笔顺检索
- 自动笔顺获取（本地数据文件）

迁移要点：
- 笔画数据预加载（应用启动加载到内存或 Redis）
- 笔顺检索改为服务层逻辑

### 3.3 数据导入
需求点：
- JSON/Excel 解析
- ZIP 图片匹配
- 汉字识别与字段补全
- 异步任务与进度查询
- 结果 Excel 与失败日志生成

迁移要点：
- 识别采用火山引擎 OCR 异步接口
- 通过合并图片的方式，一次识别多个上传汉字（batch 控制，默认20*20 张）
- 导入任务迁移为 Celery 异步任务
- 任务状态写入 Redis，提供 SSE 进度推送
- 大文件流式处理与断点恢复策略

### 3.4 数据导出
需求点：
- 选择字段导出
- 可选导出用户图片与标准图片
- Excel 内嵌图片
- 下载

迁移要点：
- 服务层聚合筛选与导出参数
- 文件生成路径规范化
- 下载与删除接口权限控制

## 4. 数据模型与存储迁移

### 4.1 表结构
保持原有 MySQL 表结构，字段保持兼容：
- hanzi（主键 id 字符串）
- category

### 4.2 ORM 迁移策略
- SQLAlchemy 模型与字段保持一致
- 使用 Alembic 生成迁移脚本
- 使用现有数据库进行反向校验

## 5. 异步与任务方案

### 5.1 任务策略
- 重任务（导入识别、批量生成标准图）使用 Celery

### 5.2 任务状态
- Redis 记录任务进度日志
- 接口支持轮询与 SSE 两种方式

## 6. 接口分层与路由拆分

建议接口分组：
- /api/v1/hanzi：CRUD、列表、详情、笔画、笔顺
- /api/v1/import：导入任务提交、任务状态查询、结果文件管理
- /api/v1/export：导出任务提交、下载、清理
- /api/v1/logs：前端日志上报、查询、删除

## 7. 迁移实施步骤

1) 项目骨架与配置
- FastAPI 主入口与配置中心
- 异步数据库连接与会话管理
- 统一日志与错误处理

2) 数据模型与仓储层
- SQLAlchemy 模型对齐
- 仓储层封装查询与写入

3) 核心功能 API
- 汉字 CRUD 与筛选
- 笔画、笔顺、拼音服务

4) 导入导出与任务系统
- Celery 任务迁移
- 进度状态与文件管理

5) 前端
- 前后端分离，提供 API 接口


## 8. 验收标准

- 现有功能全量覆盖，部分优化、重构
- 异步导入与进度查询稳定
