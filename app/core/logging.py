"""
日志系统初始化模块。

根据运行环境配置日志级别和格式，开发环境保留 DEBUG 便于排障，
生产环境默认 INFO 控制日志体量。
"""

import logging
from logging.config import dictConfig


def setup_logging(environment: str) -> None:
    """
    功能描述：
        初始化应用日志系统。根据环境变量设置日志级别，
        并配置控制台输出格式。

    参数：
        environment (str): 运行环境标识，"dev" 为开发环境，其他为生产环境。

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
