from types import SimpleNamespace
from unittest.mock import patch

from plugins._adapter.qq import QQBridge


class FakeEvent:
    def __init__(self, user_id: str, username: str | None = None) -> None:
        self._user_id = user_id
        self.author = SimpleNamespace(username=username)

    def get_user_id(self) -> str:
        return self._user_id


def test_private_message_does_not_include_sender_mention() -> None:
    event = FakeEvent("123456", "Alice")

    assert QQBridge().message_with_sender_mention(event, "回复内容") == "回复内容"


def test_group_message_includes_sender_mention() -> None:
    event = FakeEvent("123456", "Alice")

    with patch("plugins._adapter.qq.GroupMessageCreateEvent", FakeEvent):
        message = QQBridge().message_with_sender_mention(event, "回复内容")

    assert str(message) == "@Alice\n回复内容"
