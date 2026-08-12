from types import SimpleNamespace
from unittest.mock import Mock, patch

from nonebot.adapters.qq.models import Dispatch

from src.qq_adapter import RawPayloadLoggingQQAdapter


GROUP_PAYLOAD = (
    '{"op":0,"s":42,"t":"GROUP_MESSAGE_CREATE","id":"event-id",'
    '"d":{"id":"message-id","content":" test","timestamp":"2026-08-13T00:00:00+09:00",'
    '"group_id":"group-id","group_openid":"group-openid",'
    '"author":{"id":"user-id","bot":false,"member_openid":"member-openid",'
    '"member_role":"owner"}}}'
)


def test_logs_the_original_group_payload_when_enabled() -> None:
    bot = SimpleNamespace(self_id="bot-id", on_dispatch=Mock())
    log = Mock()

    with (
        patch("src.qq_adapter._raw_group_payload_logging_enabled", return_value=True),
        patch("src.qq_adapter.logger.opt", return_value=log),
    ):
        payload = RawPayloadLoggingQQAdapter.data_to_payload(bot, GROUP_PAYLOAD)

    assert isinstance(payload, Dispatch)
    bot.on_dispatch.assert_called_once_with(payload)
    log.info.assert_called_once_with(
        f"[qq.raw_group_payload] bot_id=bot-id payload={GROUP_PAYLOAD}"
    )


def test_does_not_log_group_payload_when_disabled() -> None:
    bot = SimpleNamespace(self_id="bot-id", on_dispatch=Mock())

    with (
        patch("src.qq_adapter._raw_group_payload_logging_enabled", return_value=False),
        patch("src.qq_adapter.logger.opt") as logger_opt,
    ):
        RawPayloadLoggingQQAdapter.data_to_payload(bot, GROUP_PAYLOAD)

    logger_opt.assert_not_called()


def test_does_not_log_non_group_dispatches() -> None:
    bot = SimpleNamespace(self_id="bot-id", on_dispatch=Mock())
    payload = GROUP_PAYLOAD.replace("GROUP_MESSAGE_CREATE", "READY")

    with (
        patch("src.qq_adapter._raw_group_payload_logging_enabled", return_value=True),
        patch("src.qq_adapter.logger.opt") as logger_opt,
    ):
        RawPayloadLoggingQQAdapter.data_to_payload(bot, payload)

    logger_opt.assert_not_called()


def test_preserves_member_role_from_the_native_author() -> None:
    bot = SimpleNamespace(self_id="bot-id", on_dispatch=Mock())
    with patch(
        "src.qq_adapter._raw_group_payload_logging_enabled",
        return_value=False,
    ):
        payload = RawPayloadLoggingQQAdapter.data_to_payload(bot, GROUP_PAYLOAD)

    event = RawPayloadLoggingQQAdapter.payload_to_event(payload)

    assert getattr(event.author, "member_role", None) is None
    assert event.member_role == "owner"
