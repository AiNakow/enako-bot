from typing import Any

from nonebot.adapters.onebot.v11 import GroupMessageEvent, MessageSegment


class OneBotV11Bridge:
    name = "onebot11"

    def image_from_bytes(self, data: bytes) -> MessageSegment:
        return MessageSegment.image(data)

    def mention_user(self, user_id: str) -> MessageSegment:
        return MessageSegment.at(user_id)

    def message_with_sender_mention(self, event: Any, message: Any) -> Any:
        return self.mention_user(self.get_user_id(event)) + "\n" + message

    def get_user_id(self, event: Any) -> str:
        return str(event.get_user_id())

    def is_group_event(self, event: Any) -> bool:
        return isinstance(event, GroupMessageEvent)

    def get_group_id(self, event: Any) -> str | None:
        group_id = getattr(event, "group_id", None)
        return str(group_id) if group_id is not None else None

    def is_group_admin_or_owner(self, event: Any) -> bool:
        sender = getattr(event, "sender", None)
        role = getattr(sender, "role", None)
        return role in {"admin", "owner"}

    def get_mentioned_user_ids(self, event: Any) -> list[str]:
        message = getattr(event, "message", None)
        if message is None:
            return []
        return [
            str(segment.data["qq"])
            for segment in message
            if segment.type == "at" and segment.data.get("qq") is not None
        ]

    def extract_first_image_url(self, message: Any) -> str | None:
        image_segments = message["image"]
        if not image_segments:
            return None

        data = image_segments[0].data
        url = data.get("url")
        if url:
            return url

        file = data.get("file")
        return str(file) if file is not None else None


bridge = OneBotV11Bridge()
