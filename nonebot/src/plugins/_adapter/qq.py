from typing import Any

from nonebot.adapters.qq import GroupMessageCreateEvent, MessageSegment


class QQBridge:
    name = "qq"

    def image_from_bytes(self, data: bytes) -> MessageSegment:
        return MessageSegment.file_image(data=data)

    def mention_user(self, user_id: str) -> MessageSegment:
        return MessageSegment.mention_user(user_id)

    def message_with_sender_mention(self, event: Any, message: Any) -> Any:
        author = getattr(event, "author", None)
        username = getattr(author, "username", None)
        sender = username or self.get_user_id(event)
        return MessageSegment.text(f"@{sender}\n") + message

    def get_user_id(self, event: Any) -> str:
        return str(event.get_user_id())

    def is_group_event(self, event: Any) -> bool:
        return isinstance(event, GroupMessageCreateEvent)

    def get_group_id(self, event: Any) -> str | None:
        group_id = getattr(event, "group_id", None)
        return str(group_id) if group_id is not None else None

    def is_group_admin_or_owner(self, event: Any) -> bool:
        return True

    def get_mentioned_user_ids(self, event: Any) -> list[str]:
        mentions = getattr(event, "mentions", []) or []
        return [str(mention_user.id) for mention_user in mentions]

    def extract_first_image_url(self, message: Any) -> str | None:
        image_segments = message["image"]
        if not image_segments:
            return None
        return image_segments[0].data.get("url")


bridge = QQBridge()
