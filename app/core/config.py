import json
import os
from typing import Any, List, Union
from urllib.parse import quote_plus

from pydantic import ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置"""

    APP_NAME: str = "CharWork API"
    ENVIRONMENT: str = "dev"
    API_V1_STR: str = "/api/v1"

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
        if v is None:
            return []

        if isinstance(v, list):
            return [str(i).strip() for i in v if str(i).strip()]

        if isinstance(v, str):
            raw = v.strip()
            if not raw:
                return []

            if raw.startswith("["):
                try:
                    items = json.loads(raw)
                    if isinstance(items, list):
                        return [str(i).strip() for i in items if str(i).strip()]
                except Exception:
                    pass

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
        if isinstance(v, str):
            return v

        values = info.data
        user = values.get("MYSQL_USER")
        password = values.get("MYSQL_PASSWORD")
        host = values.get("MYSQL_HOST")
        port = values.get("MYSQL_PORT")
        db = values.get("MYSQL_DB")

        user_enc = quote_plus(str(user)) if user is not None else ""
        password_enc = quote_plus(str(password)) if password is not None else ""
        host_str = str(host) if host is not None else ""
        port_str = str(port) if port is not None else ""
        db_str = str(db) if db is not None else ""

        return f"mysql+aiomysql://{user_enc}:{password_enc}@{host_str}:{port_str}/{db_str}"

    # 缓存与状态
    REDIS_URL: str = "redis://:Gsq142857@115.190.28.100:6379/0"
    ELASTICSEARCH_URL: str = "http://115.190.28.100:9200"
    ELASTICSEARCH_INDEX_PREFIX: str = "charwork"
    SEARCH_SYNC_ENABLED: bool = True
    SEARCH_SYNC_RABBITMQ_URL: str = "amqp://admin:admin123@115.190.28.100:5672/"
    SEARCH_SYNC_RABBITMQ_QUEUE: str = "canal.search.sync"
    SEARCH_SYNC_RABBITMQ_PREFETCH: int = 50
    SEARCH_SYNC_CANAL_SCHEMA: str | None = None
    SEARCH_SYNC_CANAL_TABLES: str = "assignment,comment,hanzi,student"

    # 智能识别 / 火山引擎
    AI_PROVIDER: str = "ark"
    AI_BASE_URL: str | None = None
    AI_API_KEY: str | None = None
    AI_MODEL: str | None = None

    VOLCENGINE_ACCESS_KEY_ID: str | None = os.getenv("VOLCENGINE_ACCESS_KEY_ID")
    VOLCENGINE_SECRET_ACCESS_KEY: str | None = os.getenv("VOLCENGINE_SECRET_ACCESS_KEY")
    VOLCENGINE_SERVICE_ID: str | None = os.getenv("VOLCENGINE_SERVICE_ID")
    VOLCENGINE_REGION: str = "cn-north-1"
    IMAGEX_HOST: str = "imagex.volcengineapi.com"
    IMAGEX_DEFAULT_DOMAIN: str = "psbet1y7ve.veimagex-pub.cn-north-1.volces.com"
    IMAGEX_DEFAULT_SCENE: str = "general"
    IMAGEX_EXPIRE: int = 600
    IMAGEX_TEMPLATE_ID: str = "tplv-psbet1y7ve-image"

    # 百度ak/sk
    BAIDU_API_KEY: str | None = os.getenv("BAIDU_API_KEY")
    BAIDU_SECRET_KEY: str | None = os.getenv("BAIDU_SECRET_KEY")

    # 安全
    SECRET_KEY: str = "change_me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()
