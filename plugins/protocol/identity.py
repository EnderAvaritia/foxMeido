"""
identity.py - 事件身份归一化

把 OneBot V11 / Milky 等适配器的事件字段收敛成稳定的小接口，
插件不再直接依赖 event.user_id / event.sender.nickname / event.group_id。

支持的事件形态：
- OneBot V11: event.user_id / event.group_id / event.message_id / event.sender
- Milky:      event.data.sender_id / event.data.peer_id /
              event.data.message_seq / event.data.message_scene / event.data.sender
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

Scene = Literal["group", "private"]


@dataclass(frozen=True)
class ChatRef:
    """聊天目标：群聊或私聊。"""

    scene: Scene
    peer_id: int
    """群聊时为群号，私聊时为用户 QQ 号。"""


@dataclass(frozen=True)
class MessageRef:
    """可回传给同一协议端的消息引用。"""

    chat: ChatRef
    seq: int
    """OneBot V11 为 message_id，Milky 为 message_seq。"""


def _milky_data(event: Any) -> Any | None:
    """识别 Milky 的 IncomingMessage 数据。"""

    data = getattr(event, "data", None)
    if data is not None and hasattr(data, "message_scene") and hasattr(data, "sender_id"):
        return data
    return None


def user_id(event: Any) -> int:
    """提取发送者 QQ 号。"""

    data = _milky_data(event)
    if data is not None:
        return int(data.sender_id)

    value = getattr(event, "user_id", None)
    if value is None:
        getter = getattr(event, "get_user_id", None)
        if callable(getter):
            value = getter()
    if value is None:
        raise ValueError(f"无法从事件中提取 user_id: {type(event).__name__}")
    return int(value)


def group_id(event: Any) -> int | None:
    """提取群号；私聊返回 None。"""

    data = _milky_data(event)
    if data is not None:
        if data.message_scene == "group":
            return int(data.peer_id)
        return None

    value = getattr(event, "group_id", None)
    if value is None:
        return None
    return int(value)


def nickname(event: Any) -> str:
    """提取发送者昵称；取不到时回退到 QQ 号。"""

    data = _milky_data(event)
    sender = None
    if data is not None:
        sender = getattr(data, "sender", None)
    else:
        sender = getattr(event, "sender", None)

    if sender is not None:
        name = getattr(sender, "nickname", "") or getattr(sender, "card", "")
        if name:
            return str(name)

    return str(user_id(event))


def plaintext(event: Any) -> str:
    """提取消息纯文本，兼容各适配器的 MessageEvent。"""

    getter = getattr(event, "get_plaintext", None)
    if callable(getter):
        return getter()

    getter = getattr(event, "get_message", None)
    if callable(getter):
        message = getter()
        extractor = getattr(message, "extract_plain_text", None)
        if callable(extractor):
            return extractor()

    return str(getattr(event, "message", "") or "")


def chat_ref(event: Any) -> ChatRef:
    """把事件归一化为 ChatRef。"""

    data = _milky_data(event)
    if data is not None:
        scene: Scene = "group" if data.message_scene == "group" else "private"
        return ChatRef(scene=scene, peer_id=int(data.peer_id))

    gid = getattr(event, "group_id", None)
    if gid is not None:
        return ChatRef(scene="group", peer_id=int(gid))
    return ChatRef(scene="private", peer_id=user_id(event))


def message_ref(event: Any) -> MessageRef | None:
    """把事件归一化为 MessageRef；不是消息事件时返回 None。"""

    data = _milky_data(event)
    if data is not None:
        return MessageRef(chat=chat_ref(event), seq=int(data.message_seq))

    value = getattr(event, "message_id", None)
    if value is None:
        value = getattr(event, "id", None)
    if value is None:
        return None

    try:
        seq = int(value)
    except (TypeError, ValueError):
        return None
    return MessageRef(chat=chat_ref(event), seq=seq)


def is_group_event(event: Any) -> bool:
    """是否群聊事件。"""

    return chat_ref(event).scene == "group"