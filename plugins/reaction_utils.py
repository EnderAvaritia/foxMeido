"""
reaction_utils.py - 群消息表情回复工具模块

提供可复用的表情回复核心函数，支持 OneBot V11 / NapCat 的 send_group_msg_reaction API。
不支持的协议端自动 try/except 忽略，不会报错。

用法：

    1. 作为自动 hook（plugins/message_reaction.py 中已配置）：
       在 .env 中设置 MESSAGE_REACTION_ENABLED=true

    2. 在任意插件中手动调用：

        from plugins.reaction_utils import send_reaction, remove_reaction

        # 直接对消息添加表情
        await send_reaction(bot, group_id=123456, message_id=98765)

        # 指定表情 ID
        await send_reaction(bot, group_id=123456, message_id=98765, face_id="351")

        # 移除表情
        await remove_reaction(bot, group_id=123456, message_id=98765, face_id="32")

        # 从事件对象提取信息后发送
        from plugins.reaction_utils import extract_group_id, extract_message_id
        group_id = extract_group_id(event)
        message_id = extract_message_id(event)
        await send_reaction(bot, group_id=group_id, message_id=message_id)

配置（.env）：
    MESSAGE_REACTION_ENABLED  - 是否启用（默认 false）
    MESSAGE_REACTION_FACE_ID  - QQ 表情 ID（默认 32=✅）
"""

from __future__ import annotations

import os
import re
from typing import Any

from nonebot.log import logger

# ── 项目根目录 ────────────────────────────────────────────────
# 此文件位于 plugins/ 下，往上级 2 层
_PROJECT_ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ── 配置读取（兼容混入 Python 代码的 .env 文件） ─────────────


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


def get_reaction_config() -> tuple[bool, str]:
    """获取表情回复配置。

    Returns:
        (enabled, face_id): 是否启用，QQ 表情 ID
    """
    enabled = _read_dotenv("MESSAGE_REACTION_ENABLED").lower() in ("true", "1", "yes")
    face_id = _read_dotenv("MESSAGE_REACTION_FACE_ID") or "32"
    return enabled, face_id


# ── 事件提取工具 ──────────────────────────────────────────────


def extract_group_id(event: Any) -> int | None:
    """从消息事件对象中提取群号。

    兼容 OneBot V11 GroupMessageEvent 和 QQ 适配器 GroupEvent。
    """
    # OneBot V11: event.group_id (int)
    group_id = getattr(event, "group_id", None)
    if group_id is not None:
        return int(group_id) if not isinstance(group_id, int) else group_id
    # QQ 适配器: event.group.group_id / event.group_openid
    group = getattr(event, "group", None) or getattr(event, "group_openid", None)
    if group is not None:
        gid = getattr(group, "group_id", None) or getattr(group, "id", None)
        if gid is not None:
            return int(gid) if not isinstance(gid, int) else gid
    return None


def extract_message_id(event: Any) -> int | str | None:
    """从消息事件对象中提取消息 ID。

    兼容 OneBot V11 和 QQ 适配器。
    """
    # OneBot V11: event.message_id (int)
    msg_id = getattr(event, "message_id", None)
    if msg_id is not None:
        return msg_id
    # QQ 适配器: event.id (str)
    msg_id = getattr(event, "id", None)
    if msg_id is not None:
        return msg_id
    # event.data (部分适配器)
    data = getattr(event, "data", None)
    if data is not None:
        return getattr(data, "message_id", None) or getattr(data, "id", None)
    return None


# ── 核心函数 ──────────────────────────────────────────────────


async def send_reaction(
    bot: Any,
    group_id: int,
    message_id: int | str,
    face_id: str | None = None,
    *,
    is_add: bool = True,
) -> bool:
    """发送或移除群消息表情回复。

    Args:
        bot: NoneBot Bot 实例
        group_id: 群号
        message_id: 消息 ID
        face_id: QQ 表情 ID。为 None 时使用 .env 中配置的默认值
        is_add: True=添加，False=移除

    Returns:
        bool: 是否成功发送（False 表示协议端不支持）
    """
    if face_id is None:
        _, face_id = get_reaction_config()

    try:
        await bot.call_api(
            "send_group_msg_reaction",
            group_id=group_id,
            message_id=message_id,
            code=face_id,
            is_add=is_add,
        )
        action = "添加" if is_add else "移除"
        logger.debug(
            f"已{action}表情回复 group={group_id} msg={message_id} face={face_id}"
        )
        return True
    except Exception:
        # 协议端不支持表情回复，静默忽略
        return False


async def remove_reaction(
    bot: Any,
    group_id: int,
    message_id: int | str,
    face_id: str | None = None,
) -> bool:
    """移除群消息表情回复（便捷函数）。"""
    return await send_reaction(bot, group_id, message_id, face_id=face_id, is_add=False)
