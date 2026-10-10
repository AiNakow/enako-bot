from types import SimpleNamespace

from nonebot.adapters.onebot.v11 import Message, MessageSegment

from src.infrastructure_plugins._adapter.onebot11 import OneBotV11Bridge


def test_onebot_message_and_mentions():
    bridge = OneBotV11Bridge()
    event = SimpleNamespace(get_user_id=lambda: "10")
    assert bridge.image_from_bytes(b"image").type == "image"
    assert bridge.mention_user("10").type == "at"
    assert bridge.get_user_id(event) == "10"
    assert str(bridge.message_with_sender_mention(event, "reply")) == "[CQ:at,qq=10]\nreply"
    assert bridge.get_mentioned_user_ids(event) == []
    message = Message([MessageSegment.at("10"), MessageSegment.text("hello"), MessageSegment("at", {}), MessageSegment.at("20")])
    assert bridge.get_mentioned_user_ids(SimpleNamespace(message=message)) == ["10", "20"]


def test_onebot_image_sources():
    bridge = OneBotV11Bridge()
    assert bridge.extract_first_image_url(Message("text")) is None
    message = Message([MessageSegment("image", {"url": "https://example.test/image.png", "file": "ignored"})])
    assert bridge.extract_first_image_url(message) == "https://example.test/image.png"
    assert bridge.extract_first_image_url(Message(MessageSegment.image("https://example.test/file.png"))) == "https://example.test/file.png"
    assert bridge.extract_first_image_url(Message(MessageSegment("image", {}))) is None


def test_onebot_admin_roles():
    bridge = OneBotV11Bridge()
    assert bridge.is_group_admin_or_owner(SimpleNamespace()) is False
    for role in ("admin", "owner", "member"):
        assert bridge.is_group_admin_or_owner(SimpleNamespace(sender=SimpleNamespace(role=role))) is (role != "member")
