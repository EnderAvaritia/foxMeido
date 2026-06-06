"""
error_logger.py - 错误日志模块

每次调用写一个时间戳文件到 logs/，方便回溯。

log_error()  → logs/error_<时间戳>.log  （一般错误，如网络超时）
log_crash()  → logs/crash_<时间戳>.log  （崩溃级错误，含 extra 上下文）

用法：
    from plugins.noco.error_logger import log_error, log_crash

    # 一般错误
    try:
        ...
    except Exception as e:
        log_error("module.function", f"操作失败: {e}")

    # 崩溃级错误
    try:
        ...
    except Exception as e:
        log_crash("module.function", f"关键错误: {e}", extra={"appid": 12345})
"""

from __future__ import annotations

import os
import traceback
from datetime import datetime
from typing import Any

# 项目根目录定位：此文件位于 plugins/noco/，往上级 3 层
_PROJECT_ROOT: str = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
_LOG_DIR: str = os.path.join(_PROJECT_ROOT, "logs")
os.makedirs(_LOG_DIR, exist_ok=True)


def _write_log(
    prefix: str,
    source: str,
    message: str,
    exc_info: bool,
    extra: dict[str, Any] | None,
) -> str:
    """写入时间戳日志文件的底层函数。"""
    timestamp: str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename: str = f"{prefix}_{timestamp}.log"
    filepath: str = os.path.join(_LOG_DIR, filename)

    lines: list[str] = [
        f"[{timestamp}] [{source}] {message}",
    ]
    if exc_info:
        tb = traceback.format_exc().strip()
        if tb:
            lines.append("Traceback:")
            for line in tb.split("\n"):
                lines.append(f"  {line}")
    if extra:
        lines.append("Extra context:")
        for k, v in extra.items():
            lines.append(f"  {k}: {v!r}")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return filepath


# ── log_error ─────────────────────────────────────────────────


def log_error(source: str, message: str, exc_info: bool = True) -> None:
    """
    一般错误日志。

    写入 ``logs/error_<时间戳>.log``，同时打印到控制台。
    适用于网络超时、API 拒绝等可恢复的异常场景。

    Args:
        source: 错误来源，如 ``"steamFinder.take_screenshot"``。
        message: 错误描述文字。
        exc_info: 是否包含异常堆栈（默认 True）。
    """
    filepath = _write_log("error", source, message, exc_info, extra=None)
    print(f"[ERROR] [{source}] {message} → {filepath}")


# ── log_crash ─────────────────────────────────────────────────


def log_crash(
    source: str,
    message: str,
    exc_info: bool = True,
    extra: dict[str, Any] | None = None,
) -> str:
    """
    崩溃级错误日志。

    写入 ``logs/crash_<时间戳>.log``，同时打印到控制台。
    适用于数据库写入失败、关键功能不可用等需要额外上下文的场景。

    Args:
        source: 错误来源。
        message: 错误描述。
        exc_info: 是否包含异常堆栈（默认 True）。
        extra: 额外上下文（如 ``{"appid": 3818900, "url": "..."}``）。

    Returns:
        str: 创建的日志文件路径。
    """
    filepath = _write_log("crash", source, message, exc_info, extra)
    print(f"[CRASH] [{source}] {message} → {filepath}")
    return filepath
