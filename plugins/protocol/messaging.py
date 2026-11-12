"""
messaging.py - 协议中立消息构建与导出

用 Alconna 的 UniMessage 作为协议中立的消息表示，在 matcher 边界
导出为当前适配器的 Message。插件只用 str | UniMessage。

注意：本模块只负责「构建 / 导出」消息，发送入口统一在 ``notify.send``。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Union

from nonebot.internal.matcher import current_bot
from nonebot_plugin_alconna import UniMessage

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
