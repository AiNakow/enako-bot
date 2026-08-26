from types import SimpleNamespace
from unittest.mock import patch

from src.infrastructure_plugins._adapter.qq import QQBridge


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

    with patch("src.infrastructure_plugins._adapter.qq.GroupMessageCreateEvent", FakeEvent):
        message = QQBridge().message_with_sender_mention(event, "回复内容")

    assert str(message) == "@Alice\n回复内容"


def test_group_owner_is_authorized() -> None:
    event = SimpleNamespace(member_role="owner")

    assert QQBridge().is_group_admin_or_owner(event) is True


def test_group_admin_is_authorized() -> None:
    event = SimpleNamespace(author=SimpleNamespace(member_role="admin"))

    assert QQBridge().is_group_admin_or_owner(event) is True


def test_regular_group_member_is_not_authorized() -> None:
    event = SimpleNamespace(member_role="member")

    assert QQBridge().is_group_admin_or_owner(event) is False


def test_missing_group_member_role_is_not_authorized() -> None:
    event = SimpleNamespace()

    assert QQBridge().is_group_admin_or_owner(event) is False
