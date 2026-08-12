from __future__ import annotations

import os
from typing import Any

from nonebot import get_driver, logger
from nonebot.adapters.qq import Adapter as QQAdapter
from nonebot.adapters.qq import Bot, Event
from nonebot.adapters.qq.models import Dispatch, Payload


_GROUP_MESSAGE_EVENT_TYPES = {
    "GROUP_AT_MESSAGE_CREATE",
    "GROUP_MESSAGE_CREATE",
}


def _raw_group_payload_logging_enabled() -> bool:
    value: Any = os.getenv("QQ_LOG_RAW_GROUP_PAYLOAD")
    if value is None:
        value = getattr(
            get_driver().config,
            "qq_log_raw_group_payload",
            False,
        )
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


class RawPayloadLoggingQQAdapter(QQAdapter):
    """QQ adapter that preserves fields missing from the upstream event model."""

    @staticmethod
    def data_to_payload(bot: Bot, data: str | bytes) -> Payload:
        # Let the upstream adapter perform its normal parsing and dispatch bookkeeping.
        payload = QQAdapter.data_to_payload(bot, data)

        if (
            _raw_group_payload_logging_enabled()
            and isinstance(payload, Dispatch)
            and payload.type in _GROUP_MESSAGE_EVENT_TYPES
        ):
            raw_data = (
                data.decode("utf-8", errors="replace")
                if isinstance(data, bytes)
                else data
            )
            logger.opt(colors=False).info(
                f"[qq.raw_group_payload] bot_id={bot.self_id} payload={raw_data}"
            )

        return payload

    @staticmethod
    def payload_to_event(payload: Dispatch) -> Event:
        event = QQAdapter.payload_to_event(payload)

        if payload.type in _GROUP_MESSAGE_EVENT_TYPES:
            author = payload.data.get("author")
            if isinstance(author, dict):
                member_role = author.get("member_role")
                if isinstance(member_role, str):
                    # GroupMemberAuthor in nonebot-adapter-qq 1.7.1 does not declare
                    # member_role, so Pydantic drops it while parsing the nested model.
                    # Group message events allow extra fields; preserve it there.
                    setattr(event, "member_role", member_role)

        return event
