"""
error_logger.py - 错误日志模块

所有模块共用的错误日志工具。
每次调用写一个时间戳文件到 logs/，方便回溯。

log_error()  → logs/error_<时间戳>.log  （一般错误，如网络超时）
log_crash()  → logs/crash_<时间戳>.log  （崩溃级错误，含 extra 上下文）
               + 可选 ntfy 推送（通过环境变量 CRASH_NTFY_SERVER / CRASH_NTFY_TOPIC 配置）。

日志文件会自动记录触发错误的指令文本（如 "steamGoods 12345"），
仅当错误发生在指令/事件处理上下文中时才会写入该行。

用法：
    from plugins.error_logger import log_error, log_crash

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

import json
import os
import traceback
from datetime import datetime
from typing import Any

import requests

# 项目根目录定位：此文件位于 plugins/error_logger.py，往上级 2 层
_PROJECT_ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LOG_DIR: str = os.path.join(_PROJECT_ROOT, "log")
os.makedirs(_LOG_DIR, exist_ok=True)

# ── ntfy 配置（惰性加载，避免导入时 dotenv 未就绪）───────────────

_NTFY_CONFIG: dict[str, str] | None = None


def _read_dotenv(key: str) -> str:
    """
    从 .env 文件读取变量（不依赖 python-dotenv）。
    先查 os.environ（兼容已加载 dotenv 的环境），再手动解析 .env 文件。
    """
    val = os.environ.get(key, "")
    if val:
        return val
    env_path = os.path.join(_PROJECT_ROOT, ".env")
    if not os.path.isfile(env_path):
        return ""
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                k, _, v = line.partition("=")
                if k.strip() == key:
                    return v.strip().strip('"').strip("'")
    except OSError:
        pass
    return ""


def _get_ntfy_config() -> dict[str, str] | None:
    """惰性读取 ntfy 配置，未配置时返回 None。"""
    global _NTFY_CONFIG
    if _NTFY_CONFIG is not None:
        return _NTFY_CONFIG if _NTFY_CONFIG else None

    server = _read_dotenv("CRASH_NTFY_SERVER") or "https://ntfy.sh"
    topic = _read_dotenv("CRASH_NTFY_TOPIC")
    if not topic:
        _NTFY_CONFIG = {}
        return None

    _NTFY_CONFIG = {"server": server.rstrip("/"), "topic": topic}
    return _NTFY_CONFIG


def _push_ntfy(source: str, message: str, extra: dict[str, Any] | None) -> None:
    """通过 ntfy 推送崩溃通知，静默失败。"""
    cfg = _get_ntfy_config()
    if not cfg:
        return

    title = f"💥 {source}"
    body = message
    if extra:
        extra_str = ", ".join(f"{k}={v}" for k, v in extra.items())
        body += f"\n\n上下文: {extra_str}"

    payload = {
        "topic": cfg["topic"],
        "title": title,
        "message": body,
        "tags": ["warning", "bug"],
        "priority": 5,
    }
    headers = {"Content-Type": "application/json"}

    try:
        resp = requests.post(
            cfg["server"],
            data=json.dumps(payload),
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        print(f"[ntfy] 推送成功: {title}")
    except Exception as e:
        # ntfy 推送失败本身不写日志，避免死循环
        print(f"[ntfy] 推送失败: {e}")


def _get_current_command() -> str | None:
    """
    获取当前正在执行的指令文本（如 "steamGoods 12345"）。

    通过 NoneBot 的 ``current_event`` 上下文变量读取，仅在事件处理中
    （指令处理器/定时任务等）有值；脚本独立运行时返回 None。
    """
    try:
        from nonebot.internal.matcher import current_event

        event = current_event.get()
        text = event.get_plaintext().strip()
        if text:
            return text[:200]
    except Exception:  # noqa: BLE001 - 上下文未设置或解析失败，忽略
        pass
    return None


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
    command = _get_current_command()
    if command:
        lines.append(f"指令: {command}")
    if exc_info:
        tb = traceback.format_exc().strip()
        if tb:
            lines.append("Traceback:")
            for line in tb.split("\n"):
                lines.append(f"  {line}")
    if extra:
        lines.append("Extra context:")
        for k, v in extra.items():
            lines.append(f"  {k}: {v}")

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

    日志内容形如::

        [2026-01-01_12-00-00] [steam_utils.get_game_info] 请求API异常: ...
        指令: steamGoods 12345
        Traceback:
          ...
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
    如已配置 CRASH_NTFY_SERVER / CRASH_NTFY_TOPIC，还会推送 ntfy 通知。
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
    _push_ntfy(source, message, extra)
    return filepath
