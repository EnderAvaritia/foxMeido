"""
errors.py - 协议错误归一化

插件只需要关心「发送失败是否值得重试」，不需要知道失败来自
OneBot V11 的 ActionFailed 还是 Milky 的 ActionFailed。
"""

from __future__ import annotations


_KNOWN_SEND_EXCEPTIONS = {
    "ActionFailed",
    "NetworkError",
    "ApiNotAvailable",
    "ApiTimeout",
}

_RETRYABLE_SEND_EXCEPTIONS = {
    "ActionFailed",
    "NetworkError",
    "ApiTimeout",
}


class SendError(Exception):
    """消息发送失败。"""

    def __init__(self, *, retryable: bool, cause: BaseException) -> None:
        self.retryable = retryable
        self.cause = cause
        super().__init__(f"{type(cause).__name__}: {cause}")


def is_send_exception(exc: BaseException) -> bool:
    """是否为已知的协议端发送异常。"""

    return type(exc).__name__ in _KNOWN_SEND_EXCEPTIONS


def wrap_send_error(exc: BaseException) -> SendError:
    """把协议端异常包装为插件可见的 SendError。"""

    return SendError(
        retryable=type(exc).__name__ in _RETRYABLE_SEND_EXCEPTIONS,
        cause=exc,
    )