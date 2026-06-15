"""
message_reaction.py - 消息表情回复模块

提供：
1. 自动钩子 — 收到群消息后立即添加表情回复（如 ✅）
2. 核心函数 — 供其他插件手动调用

用法：
    # 自动钩子：在 .env 中设置 MESSAGE_REACTION_ENABLED=true

    # 手动调用（其他插件中）：
    from plugins.message_reaction import send_reaction, remove_reaction
    await send_reaction(bot, group_id=..., message_id=..., face_id="351")

配置（.env）：
    MESSAGE_REACTION_ENABLED  - 是否启用（默认 false）
    MESSAGE_REACTION_FACE_ID  - QQ 表情 ID（默认 32=✅）

支持的协议端：
    - NapCat/OneBot V11（send_group_msg_reaction API）
    不支持的协议端自动忽略，不会报错。
"""

from __future__ import annotations

import os
import re
from typing import Any

from nonebot import on_message
from nonebot.log import logger

# ── 项目根目录 ────────────────────────────────────────────────
# 此文件位于 plugins/ 下，往上级 2 层
_PROJECT_ROOT: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ── 配置读取（兼容混入 Python 代码的 .env 文件） ─────────────


def _read_dotenv(key: str) -> str:
    """直接从 .env 文件逐行扫描读取变量值（兜底方案）。

    支持行内注释：``KEY=VALUE  # comment`` 会返回 ``VALUE``。
    """
    value = os.getenv(key, "")
    if value:
        return value.split("#")[0].strip()
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
                        # 去掉行内注释
                        val = val.split("#")[0].strip()
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

# 协议端不支持时的缓存标记，避免每条消息都报错
_API_UNSUPPORTED: bool = False


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
    global _API_UNSUPPORTED

    if _API_UNSUPPORTED:
        return False

    if face_id is None:
        _, face_id = get_reaction_config()

    try:
        await bot.call_api(
            "set_msg_emoji_like",
            message_id=str(message_id),
            emoji_id=str(face_id),
        )
        action = "添加" if is_add else "移除"
        logger.opt(colors=True).debug(
            f"<green>✓</green> 已{action}表情回复 group={group_id} msg={message_id} face={face_id}"
        )
        return True
    except Exception as e:
        msg = str(e)
        # retcode=1404 = 不支持的API，标记后不再重试
        if "1404" in msg:
            _API_UNSUPPORTED = True
            logger.opt(colors=True).warning(
                f"<yellow>✗</yellow> 协议端不支持 set_msg_emoji_like，"
                f"已自动禁用表情回复功能"
            )
        else:
            logger.opt(colors=True).warning(
                f"<yellow>✗</yellow> 表情回复失败 group={group_id} msg={message_id} "
                f"face={face_id} is_add={is_add}: {type(e).__name__}: {e}"
            )
        return False


async def remove_reaction(
    bot: Any,
    group_id: int,
    message_id: int | str,
    face_id: str | None = None,
) -> bool:
    """移除群消息表情回复（便捷函数）。"""
    return await send_reaction(bot, group_id, message_id, face_id=face_id, is_add=False)


# ── 自动钩子 ──────────────────────────────────────────────────
# priority=1 先于所有命令处理器（priority=10）运行
# block=False 不阻止消息继续传递到下层处理器
_reaction_handler = on_message(priority=1, block=False)


@_reaction_handler.handle()
async def _handle_message_reaction(bot, event):
    """收到群消息后立即添加表情回复。"""
    enabled, face_id = get_reaction_config()
    logger.opt(colors=True).debug(
        f"<cyan>[Reaction]</cyan> 收到消息 MESSAGE_REACTION_ENABLED={enabled} "
        f"face_id={face_id!r} event_type={type(event).__name__}"
    )
    if not enabled:
        return

    group_id = extract_group_id(event)
    message_id = extract_message_id(event)
    logger.opt(colors=True).debug(
        f"<cyan>[Reaction]</cyan> 提取结果 group_id={group_id!r} message_id={message_id!r}"
    )
    if group_id is None or message_id is None:
        return

    await send_reaction(bot, group_id=group_id, message_id=message_id, face_id=face_id)
