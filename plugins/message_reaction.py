"""
message_reaction.py - 消息表情回复

收到群消息后立即添加表情回复（如 ✅），类似 QQ 群聊的"表情回应"。
参考 frontier/plugins/agent/__init__.py 的 send_group_message_reaction 模式。

配置（.env）：
  MESSAGE_REACTION_ENABLED=true/false（默认 false）
  MESSAGE_REACTION_FACE_ID=QQ 表情 ID（默认 32=✅）

支持的协议端：
  - NapCat/OneBot V11（send_group_msg_reaction API）
  不支持的协议端自动忽略，不会报错。
"""

from __future__ import annotations

import os
import re

from nonebot import on_message
from nonebot.log import logger

# ── 从 .env 读取配置（兼容混入 Python 代码的 .env 文件） ─────

_PROJECT_ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read_dotenv(key: str) -> str:
    """直接从 .env 文件逐行扫描读取变量值（兜底方案）。"""
    value = os.getenv(key, "")
    if value:
        return value
    env_name = os.getenv("ENVIRONMENT", "")
    candidates: list[str] = []
    if env_name:
        candidates.append(f".env.{env_name}")
    candidates.append(".env")
    for fname in candidates:
        fpath = os.path.join(_PROJECT_ROOT, fname)
        if not os.path.isfile(fpath):
            continue
        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    m = re.match(r"export\s+", line)
                    if m:
                        line = line[m.end() :]
                    m = re.match(rf"({re.escape(key)})\s*=\s*(.*)", line)
                    if m:
                        val = m.group(2).strip().strip('"').strip("'")
                        if val:
                            return val
        except OSError:
            continue
    return os.getenv(key, "")


# ── 配置项 ────────────────────────────────────────────────────
MESSAGE_REACTION_ENABLED: bool = _read_dotenv("MESSAGE_REACTION_ENABLED").lower() in (
    "true",
    "1",
    "yes",
)
MESSAGE_REACTION_FACE_ID: str = _read_dotenv("MESSAGE_REACTION_FACE_ID") or "32"

# ── 消息处理器 ────────────────────────────────────────────────
# priority=1 先于所有命令处理器（priority=10）运行
# block=False 不阻止消息继续传递到下层处理器
reaction_handler = on_message(priority=1, block=False)


@reaction_handler.handle()
async def handle_message_reaction(bot, event):
    """收到消息后立即添加表情回复（仅群聊）。"""
    if not MESSAGE_REACTION_ENABLED:
        return

    # 只处理群消息
    group_id = _get_group_id(event)
    if group_id is None:
        return

    message_id = _get_message_id(event)
    if message_id is None:
        return

    # 通过 call_api 发送表情回复（NapCat/OneBot V11 扩展 API）
    # 不支持此 API 的协议端会抛出异常，这里静默忽略
    try:
        await bot.call_api(
            "send_group_msg_reaction",
            group_id=group_id,
            message_id=message_id,
            code=MESSAGE_REACTION_FACE_ID,
            is_add=True,
        )
        logger.debug(
            f"已添加表情回复 group={group_id} msg={message_id} face={MESSAGE_REACTION_FACE_ID}"
        )
    except Exception:
        # 协议端不支持表情回复，静默忽略
        pass


# ── 工具函数 ──────────────────────────────────────────────────


def _get_group_id(event) -> int | None:
    """从事件对象中提取群号。"""
    # OneBot V11 GroupMessageEvent
    group_id = getattr(event, "group_id", None)
    if group_id is not None:
        return group_id
    # QQ 适配器 GroupEvent
    group = getattr(event, "group", None) or getattr(event, "group_openid", None)
    if group is not None:
        return getattr(group, "group_id", None) or getattr(group, "id", None)
    return None


def _get_message_id(event) -> int | str | None:
    """从事件对象中提取消息 ID。"""
    # OneBot V11: message_id (int)
    msg_id = getattr(event, "message_id", None)
    if msg_id is not None:
        return msg_id
    # QQ 适配器: id (str)
    msg_id = getattr(event, "id", None)
    if msg_id is not None:
        return msg_id
    # event.data (部分适配器)
    data = getattr(event, "data", None)
    if data is not None:
        return getattr(data, "message_id", None) or getattr(data, "id", None)
    return None
