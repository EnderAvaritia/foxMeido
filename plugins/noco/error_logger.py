"""
error_logger.py - 错误日志模块

记录程序运行中的异常/错误到 logs/error.log（带旋转），
同时打印到控制台（与原 print() 行为一致）。

用法：
    from noco.error_logger import log_error

    try:
        ...
    except Exception as e:
        log_error("module.function", f"操作失败: {e}")

日志文件路径：项目根目录/logs/error.log
"""

from __future__ import annotations

import os
import sys
from logging.handlers import RotatingFileHandler
from logging import (
    Formatter,
    getLogger,
    ERROR,
)

# 项目根目录定位：此文件位于 plugins/noco/，往上级 3 层
_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
_LOG_DIR = os.path.join(_PROJECT_ROOT, "logs")
_LOG_FILE = os.path.join(_LOG_DIR, "error.log")

os.makedirs(_LOG_DIR, exist_ok=True)

_logger = getLogger("foxMeido")
_logger.setLevel(ERROR)

# 防止重复添加 handler（模块重载时）
if not _logger.handlers:
    _handler = RotatingFileHandler(
        _LOG_FILE,
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=3,              # 保留 3 个备份
        encoding="utf-8",
    )
    _handler.setLevel(ERROR)
    _handler.setFormatter(
        Formatter(
            "[%(asctime)s] [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    _logger.addHandler(_handler)


def log_error(source: str, message: str, exc_info: bool = True) -> None:
    """
    记录错误：写入 logs/error.log 并打印到控制台。

    Args:
        source: 错误来源，如 ``"steamFinder.take_screenshot"``。
        message: 错误描述文字。
        exc_info: 是否在日志中包含异常堆栈（默认 True，
                  仅当处于 except 块中时有实际内容）。
    """
    print(f"[ERROR] [{source}] {message}")
    _logger.error(f"[{source}] {message}", exc_info=exc_info)
