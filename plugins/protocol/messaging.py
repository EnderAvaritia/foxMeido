"""
messaging.py - 统一消息构建与发送

用 Alconna 的 UniMessage 作为协议中立的消息表示，在 matcher 边界
导出为当前适配器的 Message。插件只用 str | UniMessage。

注意：
- send/finish/reject 不会吞掉 FinishedException / RejectedException，
  它们仍是 NoneBot 的流程控制信号。
- UniMessage 导出必须带 bot；没有真实 bot 时无法导出 Milky 图片，
  因为 Milky 需要先把 raw/path 资源上传成 URI。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, NoReturn, Union

from nonebot.internal.matcher import current_bot
from nonebot_plugin_alconna import UniMessage

from .errors import is_send_exception, wrap_send_error

MessageLike = Union[str, UniMessage]


def text(content: str) -> UniMessage:
    """构建纯文本消息。"""

    return UniMessage.text(content)


def image(
    raw: bytes | None = None,
    *,
    url: str | None = None,
    path: str | Path | None = None,
) -> UniMessage:
    """构建图片消息；raw / url / path 三选一。"""

    initializers = sum(item is not None for item in (raw, url, path))
    if initializers != 1:
        raise ValueError("image() 需要且只能指定 raw / url / path 之一")
    return UniMessage.image(raw=raw, url=url, path=path)


def plaintext_of(message: MessageLike) -> str:
    """提取消息的纯文本，用于发图失败后的降级发送。"""

    if isinstance(message, UniMessage):
        return message.extract_plain_text()
    return str(message)


async def export(
    message: MessageLike,
    bot: Any | None = None,
    *,
    adapter: str | None = None,
) -> Any:
    """把协议中立消息导出为适配器 Message。"""

    if not isinstance(message, UniMessage):
        return message
    if bot is None and adapter is None:
        bot = current_bot.get()
    return await message.export(bot=bot, adapter=adapter)


async def send(
    matcher: Any,
    message: MessageLike,
    *,
    bot: Any | None = None,
    **kwargs: Any,
) -> Any:
    """发送消息，不结束事件处理。"""

    try:
        return await matcher.send(await export(message, bot), **kwargs)
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
    """发送最终消息并结束事件处理。"""

    try:
        await matcher.finish(await export(message, bot), **kwargs)
    except Exception as exc:
        if is_send_exception(exc):
            raise wrap_send_error(exc) from exc
        raise


async def reject(
    matcher: Any,
    message: MessageLike,
    *,
    bot: Any | None = None,
    **kwargs: Any,
) -> NoReturn:
    """拒绝当前输入并等待下一次交互。"""

    try:
        await matcher.reject(await export(message, bot), **kwargs)
    except Exception as exc:
        if is_send_exception(exc):
            raise wrap_send_error(exc) from exc
        raise