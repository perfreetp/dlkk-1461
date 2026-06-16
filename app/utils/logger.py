import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


def get_logger(name: str = "petct_scheduler") -> logging.Logger:
    """获取配置好的日志记录器"""
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    format_str = "%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s"
    formatter = logging.Formatter(format_str)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)

    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    file_handler = RotatingFileHandler(
        log_dir / f"{name}.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    logger.addHandler(file_handler)

    error_file_handler = RotatingFileHandler(
        log_dir / f"{name}_error.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    error_file_handler.setFormatter(formatter)
    error_file_handler.setLevel(logging.ERROR)
    logger.addHandler(error_file_handler)

    logger.propagate = False
    return logger


def log_operation(logger: logging.Logger, operation: str, user: str = "", **kwargs):
    """记录操作日志"""
    extra_info = ", ".join([f"{k}={v}" for k, v in kwargs.items()])
    logger.info(f"OPERATION: {operation} | USER: {user} | {extra_info}")


def log_exception(logger: logging.Logger, exception: Exception, context: str = ""):
    """记录异常日志"""
    logger.error(f"EXCEPTION in {context}: {str(exception)}", exc_info=True)
