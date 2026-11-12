from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from nonebot.adapters.onebot.v11.exception import ActionFailed
from nonebot_plugin_alconna import UniMessage

from plugins.protocol import (
    ChatRef,
    MessageRef,
    Received,
    SendError,
    chat_ref,
    export,
    finish,
    get_reaction_ops,
    group_id,
    image,
    message_ref,
    nickname,
    plaintext,
    plaintext_of,
    receive,
    send,
    send_group,
    send_private,
    text,
    user_id,
)
from plugins.protocol import notify


def _ob11_event(**overrides):
    values = {
        "user_id": 10001,
        "group_id": 20002,
        "message_id": 333,
        "sender": SimpleNamespace(nickname="alice", card=""),
        "get_plaintext": lambda: "hello",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _milky_event(scene="group", **overrides):
    values = {
        "get_plaintext": lambda: "hello",
        "data": SimpleNamespace(
            sender_id=10001,
            peer_id=20002,
            message_seq=444,
            message_scene=scene,
            sender=SimpleNamespace(nickname="bob", card="cardbob"),
        ),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class _FakeAdapter:
    def __init__(self, name: str) -> None:
        self._name = name

    def get_name(self) -> str:
        return self._name


class _FakeBot:
    def __init__(self, name: str, self_id: str = "10000") -> None:
        self.adapter = _FakeAdapter(name)
        self.self_id = self_id
        self.calls: list[tuple[str, dict]] = []

    async def call_api(self, api: str, **data):
        self.calls.append((api, data))
        return None

    async def send_group_message_reaction(self, **data):
        self.calls.append(("send_group_message_reaction", data))
        return None


def test_identity_onebot_group():
    event = _ob11_event()
    assert user_id(event) == 10001
    assert group_id(event) == 20002
    assert nickname(event) == "alice"
    assert plaintext(event) == "hello"
    assert chat_ref(event) == ChatRef(scene="group", peer_id=20002)
    assert message_ref(event) == MessageRef(
        chat=ChatRef(scene="group", peer_id=20002), seq=333
    )


def test_identity_onebot_private():
    event = _ob11_event(group_id=None)
    assert group_id(event) is None
    assert chat_ref(event) == ChatRef(scene="private", peer_id=10001)


def test_identity_milky_group():
    event = _milky_event()
    assert user_id(event) == 10001
    assert group_id(event) == 20002
    assert nickname(event) == "bob"
    assert plaintext(event) == "hello"
    assert chat_ref(event) == ChatRef(scene="group", peer_id=20002)
    assert message_ref(event) == MessageRef(
        chat=ChatRef(scene="group", peer_id=20002), seq=444
    )


def test_identity_milky_private():
    event = _milky_event(scene="friend")
    assert group_id(event) is None
    assert chat_ref(event) == ChatRef(scene="private", peer_id=20002)


def test_receive_onebot_group():
    received = receive(_ob11_event())
    assert isinstance(received, Received)
    assert received.adapter == "OneBot V11"
    assert received.user_id == 10001
    assert received.group_id == 20002
    assert received.nickname == "alice"
    assert received.text == "hello"
    assert received.chat == ChatRef(scene="group", peer_id=20002)
    assert received.message == MessageRef(
        chat=ChatRef(scene="group", peer_id=20002), seq=333
    )
    assert received.is_group is True


def test_receive_milky_private():
    received = receive(_milky_event(scene="friend"))
    assert isinstance(received, Received)
    assert received.adapter == "Milky"
    assert received.group_id is None
    assert received.chat == ChatRef(scene="private", peer_id=20002)
    assert received.message == MessageRef(
        chat=ChatRef(scene="private", peer_id=20002), seq=444
    )
    assert received.is_group is False


def test_receive_non_message_returns_none():
    assert receive(SimpleNamespace(get_plaintext=lambda: "x")) is None


def test_plaintext_falls_back_to_message():
    class Message:
        def extract_plain_text(self):
            return "from-message"

    event = SimpleNamespace(get_message=lambda: Message())
    assert plaintext(event) == "from-message"


def test_image_builder_validation():
    with pytest.raises(ValueError):
        image()
    with pytest.raises(ValueError):
        image(raw=b"x", url="https://example.com/x.png")
    assert isinstance(image(raw=b"x"), UniMessage)
    assert isinstance(image(url="https://example.com/x.png"), UniMessage)


def test_export_onebot_text_and_image():
    exported_text = asyncio.run(export(text("hi"), adapter="OneBot V11"))
    exported_image = asyncio.run(export(image(raw=b"abc"), adapter="OneBot V11"))
    assert str(exported_text) == "hi"
    assert "base64://YWJj" in str(exported_image)


def test_send_wraps_known_adapter_error():
    class FailingMatcher:
        async def send(self, message, **kwargs):
            raise ActionFailed(retcode=1200, message="failed")

    with pytest.raises(SendError) as exc_info:
        asyncio.run(send("hi", matcher=FailingMatcher(), bot=_FakeBot("OneBot V11")))
    assert exc_info.value.retryable is True
    assert isinstance(exc_info.value.cause, ActionFailed)


def test_finish_rethrows_control_flow_exception():
    class Stop(Exception):
        pass

    class StoppingMatcher:
        async def finish(self, message, **kwargs):
            raise Stop

    with pytest.raises(Stop):
        asyncio.run(finish(StoppingMatcher(), "hi", bot=_FakeBot("OneBot V11")))


def test_send_matcher_branch():
    class RecordingMatcher:
        def __init__(self):
            self.sent: list = []

        async def send(self, message, **kwargs):
            self.sent.append(message)

    matcher = RecordingMatcher()
    assert asyncio.run(send("hi", matcher=matcher, bot=_FakeBot("OneBot V11"))) is True
    assert matcher.sent == ["hi"]


def test_send_finish_requires_matcher():
    with pytest.raises(ValueError):
        asyncio.run(send("hi", finish=True))


def test_send_non_message_event_without_target_raises():
    with pytest.raises(ValueError):
        asyncio.run(send("hi", event=SimpleNamespace(get_plaintext=lambda: "x")))


def test_plaintext_of():
    assert plaintext_of("hi") == "hi"
    assert plaintext_of(text("hi") + image(raw=b"x")) == "hi"


def test_reaction_onebot_group_only():
    bot = _FakeBot("OneBot V11")
    ops = get_reaction_ops(bot)
    group_ref = MessageRef(chat=ChatRef(scene="group", peer_id=20002), seq=333)
    private_ref = MessageRef(chat=ChatRef(scene="private", peer_id=10001), seq=333)

    assert asyncio.run(ops.add(group_ref, "32")) is True
    assert bot.calls == [
        (
            "set_msg_emoji_like",
            {"message_id": "333", "emoji_id": "32", "set": True},
        )
    ]
    assert asyncio.run(ops.add(private_ref, "32")) is False


def test_reaction_milky_group():
    bot = _FakeBot("Milky")
    ops = get_reaction_ops(bot)
    ref = MessageRef(chat=ChatRef(scene="group", peer_id=20002), seq=444)

    assert asyncio.run(ops.add(ref, "32")) is True
    assert bot.calls == [
        (
            "send_group_message_reaction",
            {
                "group_id": 20002,
                "message_seq": 444,
                "reaction": "32",
                "reaction_type": "face",
                "is_add": True,
            },
        )
    ]


def test_reaction_unsupported_cache_is_per_bot():
    class UnsupportedBot(_FakeBot):
        async def call_api(self, api: str, **data):
            self.calls.append((api, data))
            raise ActionFailed(retcode=1404, message="unsupported")

    old_bot = UnsupportedBot("OneBot V11")
    new_bot = _FakeBot("OneBot V11")
    ref = MessageRef(chat=ChatRef(scene="group", peer_id=20002), seq=333)

    assert asyncio.run(get_reaction_ops(old_bot).add(ref, "32")) is False
    assert asyncio.run(get_reaction_ops(old_bot).add(ref, "32")) is False
    assert len(old_bot.calls) == 1
    assert asyncio.run(get_reaction_ops(new_bot).add(ref, "32")) is True


def test_notify_select_bot(monkeypatch):
    ob11 = _FakeBot("OneBot V11", "10000")
    milky = _FakeBot("Milky", "10000")

    monkeypatch.setattr(notify, "get_bots", lambda: {"10000": ob11})
    monkeypatch.setattr(notify, "_configured_adapter", lambda: None)
    monkeypatch.setattr(notify, "_configured_self_id", lambda: None)
    assert notify.select_bot() is ob11

    monkeypatch.setattr(notify, "get_bots", lambda: {"ob11": ob11, "milky": milky})
    assert notify.select_bot() is None
    assert notify.select_bot(adapter="Milky") is milky
    assert notify.select_bot(adapter="OneBot V11", self_id="10000") is ob11
    assert notify.select_bot(adapter="Milky", self_id="20000") is None


def test_notify_send_group_dispatch(monkeypatch):
    ob11 = _FakeBot("OneBot V11")
    milky = _FakeBot("Milky")
    monkeypatch.setattr(notify, "_configured_adapter", lambda: None)
    monkeypatch.setattr(notify, "_configured_self_id", lambda: None)

    monkeypatch.setattr(notify, "get_bots", lambda: {"1": ob11})
    assert asyncio.run(send_group(20002, "hi")) is True
    assert ob11.calls == [("send_group_msg", {"message": "hi", "group_id": 20002})]

    monkeypatch.setattr(notify, "get_bots", lambda: {"2": milky})
    assert asyncio.run(send_private(10001, "hi")) is True
    assert milky.calls == [
        ("send_private_message", {"message": "hi", "user_id": 10001})
    ]


def test_notify_without_bot_returns_false(monkeypatch):
    monkeypatch.setattr(notify, "get_bots", lambda: {})
    monkeypatch.setattr(notify, "_configured_adapter", lambda: None)
    monkeypatch.setattr(notify, "_configured_self_id", lambda: None)
    assert asyncio.run(send_group(20002, "hi")) is False


def test_reaction_cleanup_onebot_group(monkeypatch):
    from plugins import message_reaction

    bot = _FakeBot("OneBot V11")
    event = _ob11_event()
    monkeypatch.setattr(message_reaction, "get_reaction_config", lambda: (True, "32", False))

    cleanup = asyncio.run(message_reaction.reaction_cleanup(bot, event))
    assert cleanup is None
    assert bot.calls == [
        (
            "set_msg_emoji_like",
            {"message_id": "333", "emoji_id": "32", "set": True},
        )
    ]


def test_reaction_cleanup_auto_remove(monkeypatch):
    from plugins import message_reaction

    bot = _FakeBot("OneBot V11")
    event = _ob11_event()
    monkeypatch.setattr(message_reaction, "get_reaction_config", lambda: (True, "32", True))

    cleanup = asyncio.run(message_reaction.reaction_cleanup(bot, event))
    assert cleanup is not None
    asyncio.run(cleanup())
    assert [call[0] for call in bot.calls] == [
        "set_msg_emoji_like",
        "set_msg_emoji_like",
    ]
    assert bot.calls[0][1]["set"] is True
    assert bot.calls[1][1]["set"] is False


def test_reaction_cleanup_private_returns_none(monkeypatch):
    from plugins import message_reaction

    bot = _FakeBot("OneBot V11")
    event = _ob11_event(group_id=None)
    monkeypatch.setattr(message_reaction, "get_reaction_config", lambda: (True, "32", True))

    assert asyncio.run(message_reaction.reaction_cleanup(bot, event)) is None
    assert bot.calls == []


def test_reaction_cleanup_milky_group(monkeypatch):
    from plugins import message_reaction

    bot = _FakeBot("Milky")
    event = _milky_event()
    monkeypatch.setattr(message_reaction, "get_reaction_config", lambda: (True, "32", False))

    assert asyncio.run(message_reaction.reaction_cleanup(bot, event)) is None
    assert bot.calls == [
        (
            "send_group_message_reaction",
            {
                "group_id": 20002,
                "message_seq": 444,
                "reaction": "32",
                "reaction_type": "face",
                "is_add": True,
            },
        )
    ]