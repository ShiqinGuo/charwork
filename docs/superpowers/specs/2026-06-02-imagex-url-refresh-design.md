# ImageX URL 定时刷新系统设计

> 状态：已确认 | 日期：2026-06-02

## 背景

veImageX 生成的签名 URL 有时效限制（当前 30 天）。域名未就绪前无法开启 URL 鉴权（鉴权后可配置更长的过期时间），因此需要通过定时任务刷新存量数据的签名 URL，保证后续仍可访问。

## 需求摘要

- Celery Beat 定时任务，每 5 分钟刷新所有 ImageX URL
- FastAPI 启动时异步触发一次刷新（发消息即可）
- 定时任务统一管理，支持配置化启停
- 覆盖所有存储 ImageX URL 的表

## 涉及数据

| 表 | 字段 | 说明 |
|---|---|---|
| `attachment` | `file_url` | 附件上传后存的签名 URL |
| `hanzi` | `image_path` | 数据集导入时上传的图片 URL |

`export_service` 导出的文件 URL 是本地 `/media/export_results/...` 路径，不涉及 ImageX，无需刷新。

## 设计

### 一、配置层

#### Settings 新增项（`app/core/config.py`）

```python
DEFAULT_URL_REFRESH_CONFIG = {
    "URL_REFRESH_ENABLED": False,        # 总开关
    "URL_REFRESH_INTERVAL_MINUTES": 5,   # beat 间隔
    "URL_REFRESH_BATCH_SIZE": 100,       # 每批条数
    "URL_REFRESH_DOMAINS": "veimagex",   # 域名关键词，逗号分隔
}
```

#### 表级注册表（`app/core/url_refresh_config.py`）

```python
from app.models.attachment import Attachment
from app.models.hanzi import Hanzi

URL_REFRESH_TABLE_CONFIG: dict[type, dict[str, object]] = {
    Attachment: {
        "url_field": "file_url",
        "uri_field": "uri",
        "enabled": True,
    },
    Hanzi: {
        "url_field": "image_path",
        "uri_field": "uri",
        "enabled": True,
    },
}
```

- 新增表：加一行字典条目
- 临时关闭某表：`enabled: False`
- `URL_REFRESH_ENABLED=False`：beat 不注册，启动也不触发

### 二、数据模型变更

#### `attachment` 表新增字段

```python
# veImageX 对象存储 URI，用于 URL 过期后重新签名刷新
uri: Mapped[str | None] = mapped_column(String(500), nullable=True)
# 上次刷新 URL 的时间，用于判断是否需要重新签名
url_refreshed_at: Mapped[DateTime | None] = mapped_column(DateTime, nullable=True)
```

#### `hanzi` 表新增字段

```python
# veImageX 对象存储 URI，用于 URL 过期后重新签名刷新
uri: Mapped[str | None] = mapped_column(String(500), nullable=True)
# 上次刷新 URL 的时间，用于判断是否需要重新签名
url_refreshed_at: Mapped[DateTime | None] = mapped_column(DateTime, nullable=True)
```

#### 存量回填

- Alembic migration 加列
- 独立回填脚本：正则从 URL 提取 URI，解析失败的跳过
- `uri IS NOT NULL` 作为"需要刷新"的条件
- 新增数据在上传时直接写入 uri

#### Schema 变更

`AttachmentBase` / `AttachmentCreate` / `AttachmentResponse` 新增 `uri: str | None` 字段。

### 三、刷新服务（`app/services/url_refresh_service.py`）

```
UrlRefreshService
├── refresh_all() → dict[str, int]     # 遍历注册表逐表刷新
├── refresh_table(model, cfg) → int    # 单表分批刷新
└── extract_uri_from_url(url) → str    # 存量 URI 解析工具
```

**刷新流程：**

1. 查询 `WHERE uri IS NOT NULL`，分页 LIMIT batch_size
2. 对每条记录调 `ImagexService.get_resource_url(ServiceId, Domain, URI, Timestamp=2592000)`
3. 更新 url_field 为新 URL
4. 批量 commit
5. 单条失败不阻断批次，记录错误

**注意：** `get_resource_url` 是同步 SDK 调用，celery task 内直接同步调用即可（celery worker 天然支持同步任务）。

### 四、Celery 定时任务

#### Task（`app/tasks/url_refresh_tasks.py`）

```python
@celery_app.task(name="refresh_imagex_urls")
def refresh_imagex_urls() -> dict:
    ocr_service = OCRService()
    refresh_service = UrlRefreshService(ocr_service.imagex_service)
    result = refresh_service.refresh_all()
    return {"status": "ok", "refreshed": result}
```

#### Beat Schedule（`app/core/celery_app.py`）

仅在 `URL_REFRESH_ENABLED=True` 时注册：

```python
if settings.URL_REFRESH_ENABLED:
    celery_app.conf.beat_schedule = {
        "refresh-imagex-urls": {
            "task": "refresh_imagex_urls",
            "schedule": timedelta(minutes=settings.URL_REFRESH_INTERVAL_MINUTES),
            "options": {"expires": settings.URL_REFRESH_INTERVAL_MINUTES * 60 - 30},
        },
    }
```

### 五、启动异步触发（`app/main.py`）

在 `_bootstrap_application()` 末尾追加：

```python
if settings.URL_REFRESH_ENABLED:
    from app.tasks.url_refresh_tasks import refresh_imagex_urls
    refresh_imagex_urls.delay()
    logger.info("启动时已提交 ImageX URL 刷新任务")
```

### 六、上传链路改造

#### `attachment_service.py`

```python
upload_result = await self.ocr_service.upload_image(temp_file_path)
file_url = upload_result.get("image_url", "")
uri = upload_result.get("uri", "")        # 新增：获取 URI

attachment_in = AttachmentCreate(
    ...
    file_url=file_url,
    uri=uri,                               # 新增：写入 URI
)
```

#### `attachment_repo.py`

```python
attachment = Attachment(
    ...
    file_url=attachment_in.file_url,
    uri=attachment_in.uri,                 # 新增
)
```

#### `dataset_import_service.py` 中的 `_upload_one()`

```python
def _upload_one(path, ocr):
    info = ocr._upload_image(path)
    img_url = ocr._transform_uri2url(info.get("URI", ""))
    return {
        "path": path,
        "url": img_url or "",
        "uri": info.get("URI", ""),        # 新增：返回 URI
        "status": "ok" if img_url else "failed",
    }
```

调用方在写入 `hanzi.image_path` 时同步写入 `hanzi.uri`。

## 变更文件清单

| 文件 | 操作 | 说明 |
|---|---|---|
| `app/core/config.py` | 改 | 新增 URL_REFRESH_* 配置项 |
| `app/core/url_refresh_config.py` | 新建 | 表级注册表 |
| `app/models/attachment.py` | 改 | 新增 uri 字段 |
| `app/models/hanzi.py` | 改 | 新增 uri 字段 |
| `app/schemas/attachment.py` | 改 | AttachmentBase/Create/Response 新增 uri |
| `app/repositories/attachment_repo.py` | 改 | create 时写入 uri |
| `app/services/url_refresh_service.py` | 新建 | 刷新服务 |
| `app/services/attachment_service.py` | 改 | 上传时获取并写入 uri |
| `app/services/dataset_import_service.py` | 改 | _upload_one 返回 uri，hanzi 写入时一并落库 |
| `app/tasks/url_refresh_tasks.py` | 新建 | Celery 定时任务 |
| `app/tasks/__init__.py` | 改 | 注册 url_refresh_tasks |
| `app/core/celery_app.py` | 改 | 条件注册 beat_schedule |
| `app/main.py` | 改 | 启动时异步触发刷新 |
| `migrations/versions/xxxx_add_uri_to_attachment_and_hanzi.py` | 新建 | Alembic migration |

## 禁用方式

- 临时禁用：`.env` 中设 `URL_REFRESH_ENABLED=false`，重启生效
- 禁用单表：`url_refresh_config.py` 中设 `"enabled": False`
