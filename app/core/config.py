"""
应用配置模块。

通过 pydantic-settings 从 .env 文件和环境变量中加载全局配置项，
涵盖数据库、Redis、Elasticsearch、AI 服务、火山引擎、安全密钥等基础设施参数。
"""

import json
import os
from typing import Any, List, Union
from urllib.parse import quote_plus

from pydantic import ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# 外部服务默认连接地址（开发环境）
DEFAULT_EXTERNAL_SERVICE_URLS = {
    "REDIS_URL": "redis://:Gsq142857@115.190.28.100:6379/0",
    "ELASTICSEARCH_URL": "http://115.190.28.100:9200",
    "SEARCH_SYNC_RABBITMQ_URL": "amqp://admin:admin123@115.190.28.100:5672/",
}
# 搜索同步默认配置（Canal + RabbitMQ + Elasticsearch）
DEFAULT_SEARCH_SYNC_CONFIG = {
    "ELASTICSEARCH_INDEX_PREFIX": "charwork",
    "SEARCH_SYNC_ENABLED": True,
    "SEARCH_SYNC_RABBITMQ_QUEUE": "canal.search.sync",
    "SEARCH_SYNC_RABBITMQ_PREFETCH": 50,
    "SEARCH_SYNC_CANAL_TABLES": "assignment,comment,hanzi,course,teaching_class,student,hanzi_dictionary",
}
# AI 智能服务默认配置
DEFAULT_AI_CONFIG = {
    "AI_PROVIDER": "ark",
}
# 火山引擎 ImageX 图片处理服务默认配置
DEFAULT_VOLCENGINE_CONFIG = {
    "VOLCENGINE_REGION": "cn-north-1",
    "IMAGEX_HOST": "imagex.volcengineapi.com",
    "IMAGEX_DEFAULT_DOMAIN": "psbet1y7ve.veimagex-pub.cn-north-1.volces.com",
    "IMAGEX_DEFAULT_SCENE": "general",
    "IMAGEX_EXPIRE": 600,
    "IMAGEX_TEMPLATE_ID": "tplv-psbet1y7ve-image",
}
# JWT / 会话安全默认配置
DEFAULT_SECURITY_CONFIG = {
    "SECRET_KEY": "change_me",
    "ALGORITHM": "HS256",
    "ACCESS_TOKEN_EXPIRE_MINUTES": 30,
}


class Settings(BaseSettings):
    """应用配置"""

    APP_NAME: str = "CharWork API"
    ENVIRONMENT: str = "dev"
    API_V1_STR: str = "/api/v1"
    SQL_ECHO: bool = False

    # 媒体文件根目录：上传图片、标准图、导入导出结果等
    MEDIA_ROOT: str = "media"
    STROKES_FILE_PATH: str = "Strokes.txt"
    # 临时目录
    TEMP_DIR: str = "temp"

    MACHINE_ID: int = 1

    # 跨域
    # 支持两种写法：
    # 1) CORS_ORIGINS=["http://localhost:5173"]（JSON 数组字符串）
    # 2) CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173（逗号分隔）
    # 以及允许通配符：CORS_ORIGINS=["*"]
    CORS_ORIGINS: List[str] = []

    @field_validator("CORS_ORIGINS", mode="before")
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        """
        功能描述：
            解析并组装 CORS 允许的源列表，兼容 JSON 数组字符串和逗号分隔两种写法。

        参数：
            v (Union[str, List[str]]): 从环境变量或配置文件读入的原始值。

        返回值：
            List[str]: 解析后的跨域源列表。
        """
        if v is None:
            return []

        if isinstance(v, list):
            return [str(i).strip() for i in v if str(i).strip()]

        if isinstance(v, str):
            raw = v.strip()
            if not raw:
                return []

            # 兼容运维常见的 JSON 数组写法，减少环境变量迁移改造成本。
            if raw.startswith("["):
                try:
                    items = json.loads(raw)
                    if isinstance(items, list):
                        return [str(i).strip() for i in items if str(i).strip()]
                except Exception:
                    pass

            # 回退到逗号分隔解析，兼容本地和容器环境的简写配置方式。
            return [i.strip() for i in raw.split(",") if i.strip()]

        raise ValueError(v)

    # 数据库
    MYSQL_HOST: str
    MYSQL_PORT: int
    MYSQL_USER: str
    MYSQL_PASSWORD: str
    MYSQL_DB: str
    DATABASE_URL: str | None = None

    @field_validator("DATABASE_URL", mode="before")
    def assemble_db_connection(cls, v: str | None, info: ValidationInfo) -> Any:
        """
        功能描述：
            根据 MYSQL_* 配置项拼装异步数据库连接 URL（mysql+aiomysql://...）。
            若已显式提供完整 DATABASE_URL 则直接返回。

        参数：
            v (str | None): 显式传入的数据库连接字符串，为 None 时自动拼装。
            info (ValidationInfo): Pydantic 验证上下文，可从中获取其他字段的值。

        返回值：
            Any: 完整的数据库连接 URL 字符串。
        """
        if isinstance(v, str):
            return v

        values = info.data
        user = values.get("MYSQL_USER")
        password = values.get("MYSQL_PASSWORD")
        host = values.get("MYSQL_HOST")
        port = values.get("MYSQL_PORT")
        db = values.get("MYSQL_DB")

        # 用户名和密码需要 URL 编码，避免特殊字符导致连接串解析失败。
        user_enc = quote_plus(str(user)) if user is not None else ""
        password_enc = quote_plus(str(password)) if password is not None else ""
        host_str = str(host) if host is not None else ""
        port_str = str(port) if port is not None else ""
        db_str = str(db) if db is not None else ""

        return f"mysql+aiomysql://{user_enc}:{password_enc}@{host_str}:{port_str}/{db_str}"

    # 缓存与状态
    REDIS_URL: str = DEFAULT_EXTERNAL_SERVICE_URLS["REDIS_URL"]
    ELASTICSEARCH_URL: str = DEFAULT_EXTERNAL_SERVICE_URLS["ELASTICSEARCH_URL"]
    ELASTICSEARCH_INDEX_PREFIX: str = DEFAULT_SEARCH_SYNC_CONFIG["ELASTICSEARCH_INDEX_PREFIX"]
    SEARCH_SYNC_ENABLED: bool = DEFAULT_SEARCH_SYNC_CONFIG["SEARCH_SYNC_ENABLED"]
    SEARCH_SYNC_RABBITMQ_URL: str = DEFAULT_EXTERNAL_SERVICE_URLS["SEARCH_SYNC_RABBITMQ_URL"]
    SEARCH_SYNC_RABBITMQ_QUEUE: str = DEFAULT_SEARCH_SYNC_CONFIG["SEARCH_SYNC_RABBITMQ_QUEUE"]
    SEARCH_SYNC_RABBITMQ_PREFETCH: int = DEFAULT_SEARCH_SYNC_CONFIG["SEARCH_SYNC_RABBITMQ_PREFETCH"]
    SEARCH_SYNC_CANAL_SCHEMA: str | None = None
    SEARCH_SYNC_CANAL_TABLES: str = DEFAULT_SEARCH_SYNC_CONFIG["SEARCH_SYNC_CANAL_TABLES"]

    # 智能识别 / AI 大模型（支持通用 OpenAI 兼容接口和火山方舟 Ark）
    AI_PROVIDER: str = DEFAULT_AI_CONFIG["AI_PROVIDER"]
    AI_BASE_URL: str | None = os.getenv("AI_BASE_URL")
    AI_API_KEY: str | None = os.getenv("AI_API_KEY")
    AI_MODEL: str | None = os.getenv("AI_MODEL")
    ARK_BASE_URL: str | None = os.getenv("ARK_BASE_URL")
    ARK_API_KEY: str | None = os.getenv("ARK_API_KEY")
    ARK_MODEL: str | None = os.getenv("ARK_MODEL")
    # 视觉模型，用于手写体评语生成（需支持图片输入）
    ARK_VISION_MODEL: str | None = os.getenv("ARK_VISION_MODEL")
    AI_SHORT_MEMORY_TURNS: int = 12       # AI 对话短期记忆保留的轮数
    AI_LONG_MEMORY_FACT_LIMIT: int = 200  # AI 对话长期记忆最大事实条数
    # 前端基础地址，用于 AI 搜索结果拼接完整跳转 URL
    FRONTEND_BASE_URL: str = os.getenv("FRONTEND_BASE_URL", "http://localhost:5173")

    VOLCENGINE_ACCESS_KEY_ID: str | None = os.getenv("VOLCENGINE_ACCESS_KEY_ID")
    VOLCENGINE_SECRET_ACCESS_KEY: str | None = os.getenv("VOLCENGINE_SECRET_ACCESS_KEY")
    VOLCENGINE_SERVICE_ID: str | None = os.getenv("VOLCENGINE_SERVICE_ID")
    VOLCENGINE_REGION: str = DEFAULT_VOLCENGINE_CONFIG["VOLCENGINE_REGION"]
    IMAGEX_HOST: str = DEFAULT_VOLCENGINE_CONFIG["IMAGEX_HOST"]
    IMAGEX_DEFAULT_DOMAIN: str = DEFAULT_VOLCENGINE_CONFIG["IMAGEX_DEFAULT_DOMAIN"]
    IMAGEX_DEFAULT_SCENE: str = DEFAULT_VOLCENGINE_CONFIG["IMAGEX_DEFAULT_SCENE"]
    IMAGEX_EXPIRE: int = DEFAULT_VOLCENGINE_CONFIG["IMAGEX_EXPIRE"]
    IMAGEX_TEMPLATE_ID: str = DEFAULT_VOLCENGINE_CONFIG["IMAGEX_TEMPLATE_ID"]

    # 百度ak/sk
    BAIDU_API_KEY: str | None = os.getenv("BAIDU_API_KEY")
    BAIDU_SECRET_KEY: str | None = os.getenv("BAIDU_SECRET_KEY")

    # 安全
    SECRET_KEY: str = DEFAULT_SECURITY_CONFIG["SECRET_KEY"]
    ALGORITHM: str = DEFAULT_SECURITY_CONFIG["ALGORITHM"]
    ACCESS_TOKEN_EXPIRE_MINUTES: int = DEFAULT_SECURITY_CONFIG["ACCESS_TOKEN_EXPIRE_MINUTES"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()

# 附件所有者类型配置
ATTACHMENT_OWNER_TYPES = {
    "submission": {
        "model": "Submission",
        "description": "作业提交"
    },
    "assignment": {
        "model": "Assignment",
        "description": "作业描述"
    },
    "comment": {
        "model": "Comment",
        "description": "评论"
    }
}
