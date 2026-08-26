from typing import Any, Protocol


class AdapterBridge(Protocol):
    name: str

    def image_from_bytes(self, data: bytes) -> Any:
        ...

    def mention_user(self, user_id: str) -> Any:
        ...

    def message_with_sender_mention(self, event: Any, message: Any) -> Any:
        ...

    def get_user_id(self, event: Any) -> str:
        ...

    def is_group_event(self, event: Any) -> bool:
        ...

    def get_group_id(self, event: Any) -> str | None:
        ...

    def is_group_admin_or_owner(self, event: Any) -> bool:
        ...

    def get_mentioned_user_ids(self, event: Any) -> list[str]:
        ...

    def extract_first_image_url(self, message: Any) -> str | None:
        ...
