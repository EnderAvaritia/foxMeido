"""
message_reaction.py - 消息表情回复模块

提供 send_reaction 核心函数，以及 reaction_cleanup 便捷函数（自动添加 + 移除）。

用法：
    # .env 中启用：
    MESSAGE_REACTION_ENABLED=true
    MESSAGE_REACTION_FACE_ID=32

    # 在 handler 中调用（推荐——自动移除）：
    from plugins.message_reaction import reaction_cleanup

    cleanup = await reaction_cleanup(bot, event)
    # ... 业务逻辑 ...
    if cleanup:
        await cleanup()
    await matcher.finish("完成")

    # 或使用底层函数（不移除）：
    from plugins.message_reaction import send_reaction, extract_group_id, extract_message_id

    group_id = extract_group_id(event)
    message_id = extract_message_id(event)
    if group_id and message_id:
        await send_reaction(bot, group_id, message_id, face_id="351")

配置（.env）：
    MESSAGE_REACTION_ENABLED  - 是否启用（默认 false）
    MESSAGE_REACTION_FACE_ID  - QQ 表情 ID（默认 32=✅）

支持的协议端：
    - OneBot V11（NapCat 的 set_msg_emoji_like）
    - Milky（send_group_message_reaction）
    不支持时自动忽略，不会报错。是否支持由 plugins.protocol.reaction 按 Bot 判断。
"""

from __future__ import annotations

import os
import re
from typing import Any

from nonebot.log import logger

from plugins.protocol.identity import ChatRef, MessageRef, receive
from plugins.protocol.reaction import get_reaction_ops

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


def get_reaction_config() -> tuple[bool, str, bool]:
    """获取表情回复配置。

    Returns:
        (enabled, face_id, auto_remove): 是否启用，QQ 表情 ID，处理结束后是否自动移除
    """
    enabled = _read_dotenv("MESSAGE_REACTION_ENABLED").lower() in ("true", "1", "yes")
    face_id = _read_dotenv("MESSAGE_REACTION_FACE_ID") or "32"
    auto_remove = _read_dotenv("MESSAGE_REACTION_AUTO_REMOVE").lower() in ("true", "1", "yes")
    return enabled, face_id, auto_remove


# ── 事件提取工具（保留旧接口，内部走协议中立层） ────────────────


def extract_group_id(event: Any) -> int | None:
    """从消息事件对象中提取群号；私聊返回 None。"""

    msg = receive(event)
    return msg.group_id if msg is not None else None


def extract_message_id(event: Any) -> int | None:
    """从消息事件对象中提取消息序号；非消息事件返回 None。"""

    msg = receive(event)
    if msg is None or msg.message is None:
        return None
    return msg.message.seq


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
        message_id: 消息序号（OneBot V11 的 message_id / Milky 的 message_seq）
        face_id: QQ 表情 ID。为 None 时使用 .env 中配置的默认值
        is_add: True=添加，False=移除

    Returns:
        bool: 是否成功发送（False 表示协议端不支持或不是群聊）
    """
    if face_id is None:
        _, face_id, _ = get_reaction_config()

    try:
        seq = int(message_id)
    except (TypeError, ValueError):
        logger.warning("表情回复的 message_id 不是整数: {!r}", message_id)
        return False

    ref = MessageRef(chat=ChatRef(scene="group", peer_id=int(group_id)), seq=seq)
    ops = get_reaction_ops(bot)
    if not ops.supports(ref):
        return False

    if is_add:
        ok = await ops.add(ref, str(face_id))
    else:
        ok = await ops.remove(ref, str(face_id))

    if ok:
        action = "添加" if is_add else "移除"
        logger.opt(colors=True).debug(
            f"<green>✓</green> 已{action}表情回复 group={group_id} msg={message_id} face={face_id}"
        )
    return ok


async def remove_reaction(
    bot: Any,
    group_id: int,
    message_id: int | str,
    face_id: str | None = None,
) -> bool:
    """移除群消息表情回复（便捷函数）。"""
    return await send_reaction(bot, group_id, message_id, face_id=face_id, is_add=False)


async def reaction_cleanup(
    bot: Any,
    event: Any,
    face_id: str | None = None,
):
    """添加表情回应并返回移除函数。handler 在处理结束后调用移除函数即可。

    是否自动移除受 .env 配置 MESSAGE_REACTION_AUTO_REMOVE 控制（默认 false）。

    用法：:

        cleanup = await reaction_cleanup(bot, event)
        # ... 业务逻辑 ...
        if cleanup:
            await cleanup()
        await matcher.finish("完成")

    Args:
        bot: NoneBot Bot 实例
        event: 消息事件
        face_id: QQ 表情 ID，为 None 使用 .env 默认值

    Returns:
        移除表情的 async callable，如果禁用自动移除或提取失败返回 None
    """
    msg = receive(event)
    ref = msg.message if msg is not None else None
    if ref is None or ref.chat.scene != "group":
        return None

    if not await send_reaction(bot, ref.chat.peer_id, ref.seq, face_id):
        return None

    _, _, auto_remove = get_reaction_config()
    if not auto_remove:
        return None

    async def _remove():
        await remove_reaction(bot, ref.chat.peer_id, ref.seq, face_id)

    return _remove
