"""
notify.py - 统一发送入口

``send`` 同时处理两类发送：
- matcher 回复：传入 ``matcher``，走 ``matcher.send`` / ``matcher.finish``；
- 主动消息：传入 ``target`` 或 ``event``，从 ``get_bots()`` 里显式选 Bot 后 call_api。

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

from typing import Any, NoReturn

from nonebot import get_bots
from nonebot.internal.matcher import current_bot
from nonebot.log import logger

from plugins.env_utils import _read_dotenv

from .errors import is_send_exception, wrap_send_error
from .identity import ChatRef, receive
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


async def send(
    message: MessageLike,
    *,
    matcher: Any | None = None,
    event: Any | None = None,
    target: ChatRef | None = None,
    bot: Any | None = None,
    adapter: str | None = None,
    self_id: str | None = None,
    finish: bool = False,
    **kwargs: Any,
) -> bool:
    """发送消息：有 matcher 时回复当前事件，否则按 target/event 主动发送。

    Args:
        message: 协议中立消息（str 或 UniMessage）。
        matcher: 事件处理 matcher；提供时走 matcher 回复分支。
        event: 事件；主动发送且未给 target 时用于推断聊天目标。
        target: 主动发送的目标聊天。
        bot: 显式指定 Bot；不传时 matcher 分支用 current_bot，
            主动分支用 select_bot 从 get_bots() 里筛选。
        adapter / self_id: 主动发送时限定 Bot 的协议端 / self_id。
        finish: True 时调用 matcher.finish 并结束事件处理。

    Returns:
        bool: matcher 分支发送成功返回 True；主动分支 call_api 成功返回 True，
        没有可用 Bot 时返回 False。
    """

    if finish and matcher is None:
        raise ValueError("finish=True 需要 matcher")

    if matcher is not None:
        active_bot = bot or current_bot.get()
        exported = await export(message, active_bot)
        try:
            if finish:
                await matcher.finish(exported, **kwargs)
            else:
                await matcher.send(exported, **kwargs)
            return True
        except Exception as exc:
            if is_send_exception(exc):
                raise wrap_send_error(exc) from exc
            raise

    received = receive(event) if event is not None else None
    ref = target or (received.chat if received is not None else None)
    if ref is None:
        raise ValueError("send() 需要 matcher，或 target/event")

    active_bot = bot or select_bot(adapter=adapter, self_id=self_id)
    if active_bot is None:
        logger.warning(
            "没有可用的 Bot 发送{}消息 (target={}, adapter={}, self_id={})",
            "群" if ref.scene == "group" else "私聊",
            ref.peer_id,
            adapter,
            self_id,
        )
        return False

    try:
        exported = await export(message, active_bot)
        name = adapter_name(active_bot)

        if name == "Milky":
            api = "send_group_message" if ref.scene == "group" else "send_private_message"
            payload: dict[str, Any] = {"message": exported}
        elif name == "OneBot V11":
            api = "send_group_msg" if ref.scene == "group" else "send_private_msg"
            # OneBot V11 的 call_api 直接走 JSON；Message 先序列化成 CQ 码字符串
            payload = {"message": str(exported)}
        else:
            logger.warning("未知适配器 {}，无法发送主动消息", name)
            return False

        payload["group_id" if ref.scene == "group" else "user_id"] = ref.peer_id
        await active_bot.call_api(api, **payload)
        return True
    except Exception as exc:
        if is_send_exception(exc):
            raise wrap_send_error(exc) from exc
        raise


async def finish(
    matcher: Any,
    message: MessageLike,
    *,
    bot: Any | None = None,
    **kwargs: Any,
) -> NoReturn:
    """发送最终消息并结束事件处理（兼容旧接口）。"""

    await send(message, matcher=matcher, bot=bot, finish=True, **kwargs)
    raise RuntimeError("matcher.finish() did not raise FinishedException")


async def reject(
    matcher: Any,
    message: MessageLike,
    *,
    bot: Any | None = None,
    **kwargs: Any,
) -> NoReturn:
    """拒绝当前输入并等待下一次交互（兼容旧接口）。"""

    try:
        await matcher.reject(await export(message, bot), **kwargs)
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

    return await send(
        message,
        target=ChatRef(scene="group", peer_id=int(group_id)),
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

    return await send(
        message,
        target=ChatRef(scene="private", peer_id=int(user_id)),
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

    return await send(
        message,
        target=ref,
        adapter=adapter,
        self_id=self_id,
    )
