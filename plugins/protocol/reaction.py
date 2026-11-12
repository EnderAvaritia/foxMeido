"""
reaction.py - 跨协议表情回应

当前只有群消息支持反应：
- OneBot V11: set_msg_emoji_like（NapCat 扩展）
- Milky:      send_group_message_reaction

不支持时返回 False，不向插件抛异常。不支持状态按 Bot 实例缓存，
避免一个协议的失败影响另一个协议。
"""

from __future__ import annotations

from typing import Any, Protocol
from weakref import WeakKeyDictionary

from nonebot.log import logger

from .identity import MessageRef


class ReactionOps(Protocol):
    """单个协议端的表情回应能力。"""

    def supports(self, ref: MessageRef) -> bool: ...

    async def add(self, ref: MessageRef, face_id: str) -> bool: ...

    async def remove(self, ref: MessageRef, face_id: str) -> bool: ...


_unsupported_bots: "WeakKeyDictionary[Any, bool]" = WeakKeyDictionary()


def _bot_unsupported(bot: Any) -> bool:
    return _unsupported_bots.get(bot, False)


def _mark_bot_unsupported(bot: Any) -> None:
    try:
        _unsupported_bots[bot] = True
    except TypeError:
        # Bot 不可弱引用时退化为不缓存，功能仍可用
        pass


def _is_unsupported(exc: BaseException) -> bool:
    info = getattr(exc, "info", None)
    if not isinstance(info, dict):
        return False

    if str(info.get("retcode")) == "1404":
        return True

    message = str(info.get("message") or info.get("msg") or "")
    lowered = message.lower()
    return "unsupported" in lowered or "not support" in lowered or "不支持" in message


def _log_failure(bot: Any, ref: MessageRef, face_id: str, is_add: bool, exc: BaseException) -> None:
    action = "添加" if is_add else "移除"
    logger.warning(
        "表情回复{}失败 adapter={} scene={} peer={} seq={} face={}: {}: {}",
        action,
        _adapter_name(bot),
        ref.chat.scene,
        ref.chat.peer_id,
        ref.seq,
        face_id,
        type(exc).__name__,
        exc,
    )


def _adapter_name(bot: Any) -> str:
    return bot.adapter.get_name()


def _is_milky(bot: Any) -> bool:
    return _adapter_name(bot) == "Milky" or ".milky" in type(bot).__module__


def _is_onebot_v11(bot: Any) -> bool:
    return _adapter_name(bot) == "OneBot V11" or ".onebot.v11" in type(bot).__module__


class _OneBotV11ReactionOps:
    def __init__(self, bot: Any) -> None:
        self.bot = bot

    def supports(self, ref: MessageRef) -> bool:
        return ref.chat.scene == "group"

    async def add(self, ref: MessageRef, face_id: str) -> bool:
        return await self._send(ref, face_id, True)

    async def remove(self, ref: MessageRef, face_id: str) -> bool:
        return await self._send(ref, face_id, False)

    async def _send(self, ref: MessageRef, face_id: str, is_add: bool) -> bool:
        if not self.supports(ref) or _bot_unsupported(self.bot):
            return False
        try:
            await self.bot.call_api(
                "set_msg_emoji_like",
                message_id=str(ref.seq),
                emoji_id=str(face_id),
                set=is_add,
            )
            return True
        except Exception as exc:  # noqa: BLE001 - 能力探测，失败降级
            if _is_unsupported(exc):
                _mark_bot_unsupported(self.bot)
                logger.warning(
                    "协议端 {} 不支持 set_msg_emoji_like，已禁用该 Bot 的表情回复",
                    _adapter_name(self.bot),
                )
            else:
                _log_failure(self.bot, ref, face_id, is_add, exc)
            return False


class _MilkyReactionOps:
    def __init__(self, bot: Any) -> None:
        self.bot = bot

    def supports(self, ref: MessageRef) -> bool:
        return ref.chat.scene == "group"

    async def add(self, ref: MessageRef, face_id: str) -> bool:
        return await self._send(ref, face_id, True)

    async def remove(self, ref: MessageRef, face_id: str) -> bool:
        return await self._send(ref, face_id, False)

    async def _send(self, ref: MessageRef, face_id: str, is_add: bool) -> bool:
        if not self.supports(ref) or _bot_unsupported(self.bot):
            return False
        try:
            await self.bot.send_group_message_reaction(
                group_id=ref.chat.peer_id,
                message_seq=ref.seq,
                reaction=str(face_id),
                reaction_type="face",
                is_add=is_add,
            )
            return True
        except Exception as exc:  # noqa: BLE001 - 能力探测，失败降级
            if _is_unsupported(exc):
                _mark_bot_unsupported(self.bot)
                logger.warning(
                    "协议端 {} 不支持 send_group_message_reaction，已禁用该 Bot 的表情回复",
                    _adapter_name(self.bot),
                )
            else:
                _log_failure(self.bot, ref, face_id, is_add, exc)
            return False


class _NullReactionOps:
    def supports(self, ref: MessageRef) -> bool:
        return False

    async def add(self, ref: MessageRef, face_id: str) -> bool:
        return False

    async def remove(self, ref: MessageRef, face_id: str) -> bool:
        return False


def get_reaction_ops(bot: Any) -> ReactionOps:
    """按适配器返回反应能力实现。"""

    if _is_milky(bot):
        return _MilkyReactionOps(bot)
    if _is_onebot_v11(bot):
        return _OneBotV11ReactionOps(bot)
    return _NullReactionOps()