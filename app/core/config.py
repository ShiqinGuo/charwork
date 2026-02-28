import os
from typing import Any, List, Union
from pydantic import AnyHttpUrl, ValidationInfo, field_validator
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
    CORS_ORIGINS: List[AnyHttpUrl] = []

    @field_validator("CORS_ORIGINS", mode="before")
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
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
        return (
            f"mysql+aiomysql://"
            f"{values.get('MYSQL_USER')}:{values.get('MYSQL_PASSWORD')}"
            f"@{values.get('MYSQL_HOST')}:{values.get('MYSQL_PORT')}"
            f"/{values.get('MYSQL_DB')}"
        )

    # 缓存与状态
    REDIS_URL: str = "redis://localhost:6379/0"

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
