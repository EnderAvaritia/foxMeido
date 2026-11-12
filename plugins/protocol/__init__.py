"""
protocol - 协议中立接口

插件只从这里导入协议相关能力，不再直接 import onebot.v11 / milky。

统一收 / 发入口：
- ``receive(event)`` 把消息事件归一化为 ``Received``；
- ``send(message, matcher=...)`` 回复当前事件，或
  ``send(message, target=...)`` 主动发送。
"""

from .errors import SendError, is_send_exception, wrap_send_error
from .identity import (
    ChatRef,
    MessageRef,
    Received,
    chat_ref,
    group_id,
    is_group_event,
    message_ref,
    nickname,
    plaintext,
    receive,
    user_id,
)
from .messaging import (
    MessageLike,
    export,
    image,
    plaintext_of,
    text,
)
from .notify import (
    adapter_name,
    finish,
    reject,
    select_bot,
    send,
    send_group,
    send_private,
    send_to_chat,
)
from .reaction import ReactionOps, get_reaction_ops

__all__ = [
    "ChatRef",
    "MessageLike",
    "MessageRef",
    "ReactionOps",
    "Received",
    "SendError",
    "adapter_name",
    "chat_ref",
    "export",
    "finish",
    "get_reaction_ops",
    "group_id",
    "image",
    "is_group_event",
    "is_send_exception",
    "message_ref",
    "nickname",
    "plaintext",
    "plaintext_of",
    "receive",
    "reject",
    "select_bot",
    "send",
    "send_group",
    "send_private",
    "send_to_chat",
    "text",
    "user_id",
    "wrap_send_error",
]