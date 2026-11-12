"""
notify.py - 主动消息（无事件上下文）

绝不再使用 nonebot.get_bot()：多个 Bot 同时连接时它会按连接顺序返回第一个，
导致消息发到错误的协议端。这里始终从 get_bots() 里显式筛选。

配置：
- PROTOCOL_PRIMARY = onebot_v11 | milky
  多 Bot 同时在线时用于选择主动发送的协议端；只有一个 Bot 时可省略。
- PROTOCOL_SELF_ID
  可选，进一步限定 Bot 的 self_id。

硬约束：同一个 QQ 号不能在同一 NoneBot 进程里同时连接 OneBot V11 和 Milky，
NoneBot 会因 self_id 重复抛 RuntimeError。迁移期请用 PROTOCOL_PRIMARY
一次只连一个，或用独立测试账号。
"""

from __future__ import annotations

from typing import Any, Literal

from nonebot import get_bots
from nonebot.log import logger

from plugins.env_utils import _read_dotenv

from .errors import is_send_exception, wrap_send_error
from .identity import ChatRef
from .messaging import MessageLike, export

_ADAPTER_ALIASES = {
    "onebot": "OneBot V11",
    "onebot11": "OneBot V11",
    "onebot_v11": "OneBot V11",
    "onebot v11": "OneBot V11",
    "ob11": "OneBot V11",
    "milky": "Milky",
}


def adapter_name(bot: Any) -> str:
    """获取适配器名称。"""

    return bot.adapter.get_name()


def _configured_adapter() -> str | None:
    raw = _read_dotenv("PROTOCOL_PRIMARY").strip().lower()
    if not raw:
        return None
    return _ADAPTER_ALIASES.get(raw, raw)


def _configured_self_id() -> str | None:
    value = _read_dotenv("PROTOCOL_SELF_ID").strip()
    return value or None


def select_bot(
    *,
    adapter: str | None = None,
    self_id: str | None = None,
) -> Any | None:
    """选择一个 Bot；无法唯一确定时返回 None，绝不随机挑。"""

    bots = list(get_bots().values())
    if not bots:
        return None

    name = adapter or _configured_adapter()
    if name:
        bots = [bot for bot in bots if adapter_name(bot) == name]

    wanted_self_id = self_id or _configured_self_id()
    if wanted_self_id:
        bots = [bot for bot in bots if str(bot.self_id) == str(wanted_self_id)]

    if len(bots) == 1:
        return bots[0]

    if len(bots) > 1:
        logger.warning(
            "主动消息存在多个候选 Bot (adapter={}, self_id={})，拒绝随机选择；"
            "请配置 PROTOCOL_PRIMARY / PROTOCOL_SELF_ID",
            name,
            wanted_self_id,
        )
    return None


async def _send(
    kind: Literal["group", "private"],
    target: int,
    message: MessageLike,
    *,
    adapter: str | None = None,
    self_id: str | None = None,
) -> bool:
    bot = select_bot(adapter=adapter, self_id=self_id)
    if bot is None:
        logger.warning(
            "没有可用的 Bot 发送{}消息 (target={}, adapter={}, self_id={})",
            "群" if kind == "group" else "私聊",
            target,
            adapter,
            self_id,
        )
        return False

    try:
        exported = await export(message, bot)
        name = adapter_name(bot)

        if name == "Milky":
            api = "send_group_message" if kind == "group" else "send_private_message"
            payload: dict[str, Any] = {"message": exported}
        elif name == "OneBot V11":
            api = "send_group_msg" if kind == "group" else "send_private_msg"
            # OneBot V11 的 call_api 直接走 JSON；Message 先序列化成 CQ 码字符串
            payload = {"message": str(exported)}
        else:
            logger.warning("未知适配器 {}，无法发送主动消息", name)
            return False

        payload["group_id" if kind == "group" else "user_id"] = int(target)
        await bot.call_api(api, **payload)
        return True
    except Exception as exc:
        if is_send_exception(exc):
            raise wrap_send_error(exc) from exc
        raise


async def send_group(
    group_id: int | str,
    message: MessageLike,
    *,
    adapter: str | None = None,
    self_id: str | None = None,
) -> bool:
    """向群聊发送主动消息。"""

    return await _send(
        "group",
        int(group_id),
        message,
        adapter=adapter,
        self_id=self_id,
    )


async def send_private(
    user_id: int | str,
    message: MessageLike,
    *,
    adapter: str | None = None,
    self_id: str | None = None,
) -> bool:
    """向私聊发送主动消息。"""

    return await _send(
        "private",
        int(user_id),
        message,
        adapter=adapter,
        self_id=self_id,
    )


async def send_to_chat(
    ref: ChatRef,
    message: MessageLike,
    *,
    adapter: str | None = None,
    self_id: str | None = None,
) -> bool:
    """按 ChatRef 自动选择群聊/私聊发送。"""

    if ref.scene == "group":
        return await send_group(ref.peer_id, message, adapter=adapter, self_id=self_id)
    return await send_private(ref.peer_id, message, adapter=adapter, self_id=self_id)