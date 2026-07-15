"""日志配置模块

提供统一的日志配置,所有模块通过 `from app.logger import logger` 使用。
日志级别通过环境变量 LOG_LEVEL 控制(默认 INFO)。
"""
import logging
import os
import sys


def _configure_logger() -> logging.Logger:
    """配置并返回应用全局 logger"""
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()

    logger = logging.getLogger("ingredient_analyzer")
    logger.setLevel(getattr(logging, log_level, logging.INFO))

    # 避免重复添加 handler(模块多次导入时)
    if logger.handlers:
        return logger

    # 输出到 stdout(Railway/Vercel 会捕获)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, log_level, logging.INFO))

    # 日志格式:时间 | 级别 | 模块 | 消息
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # 防止日志向上传播到 root logger(避免重复输出)
    logger.propagate = False

    return logger


# 模块级单例,导入即用
logger = _configure_logger()
