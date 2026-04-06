import logging
from logging.config import dictConfig


def setup_logging(environment: str) -> None:
    # 开发环境保留 DEBUG 便于排障，生产默认 INFO 控制日志体量。
    """
    功能描述：
        初始化logging。

    参数：
        environment (str): 字符串结果。

    返回值：
        None: 无返回值。
    """
    level = logging.DEBUG if environment == "dev" else logging.INFO
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(levelname)s %(asctime)s %(name)s: %(message)s",
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                }
            },
            "loggers": {
                "sqlalchemy.engine": {
                    "handlers": ["console"],
                    "level": "WARNING",
                    "propagate": False,
                },
                "sqlalchemy.pool": {
                    "handlers": ["console"],
                    "level": "WARNING",
                    "propagate": False,
                },
                "aiomysql": {
                    "handlers": ["console"],
                    "level": "WARNING",
                    "propagate": False,
                },
            },
            "root": {
                "handlers": ["console"],
                "level": level,
            },
        }
    )
