from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, patch

import nonebot
from nonebot.matcher import Matcher
from nonebot.permission import SUPERUSER
from nonebot.rule import CommandRule, Rule


try:
    nonebot.get_driver()
except ValueError:
    nonebot.init()

from src.qq_plugins.qq_command_panel import (  # noqa: E402
    PANEL_REMARK,
    _sync_on_connect,
    _sync_scope,
    collect_panel_items,
)


def make_command_matcher(
    *commands: tuple[str, ...],
    metadata: dict[str, Any] | None = None,
    superuser_only: bool = False,
) -> type[Matcher]:
    class TestMatcher(Matcher):
        rule = Rule(CommandRule(list(commands)))
        permission = SUPERUSER if superuser_only else Matcher.permission
        _default_state = {"qq_command_panel": metadata or {}}

    return TestMatcher


def test_collect_panel_items_excludes_aliases_and_keeps_metadata() -> None:
    matcher = make_command_matcher(
        ("牌理",),
        ("天凤牌理",),
        metadata={"name": "牌理", "description": "分析日麻牌理"},
    )
    admin_matcher = make_command_matcher(
        ("雀庄绑定",),
        metadata={
            "description": "绑定本群雀庄",
            "only_admin": True,
            "scopes": ["group"],
        },
    )

    items = collect_panel_items([matcher, admin_matcher])

    assert [item["name"] for item in items["c2c"]] == ["牌理"]
    assert [item["name"] for item in items["group"]] == [
        "牌理",
        "雀庄绑定",
    ]
    admin_item = next(item for item in items["group"] if item["name"] == "雀庄绑定")
    assert admin_item["only_admin"] is True
    assert admin_item["desc"] == "绑定本群雀庄"


def test_collect_panel_items_keeps_matcher_registration_order() -> None:
    first = make_command_matcher(("乙",))
    second = make_command_matcher(("A",))

    items = collect_panel_items([first, second])

    assert [item["name"] for item in items["group"]] == [
        "乙",
        "A",
    ]


def test_collect_panel_items_marks_superuser_commands_as_admin_only() -> None:
    matcher = make_command_matcher(("维护",), superuser_only=True)

    items = collect_panel_items([matcher])

    assert items["group"][0]["only_admin"] is True


def test_connect_hook_ignores_non_qq_bots() -> None:
    synchronize = AsyncMock()

    with patch(
        "src.qq_plugins.qq_command_panel.synchronize_command_panels",
        synchronize,
    ):
        asyncio.run(_sync_on_connect(object()))  # type: ignore[arg-type]

    synchronize.assert_not_awaited()


def test_sync_scope_creates_panel_when_global_panel_is_missing() -> None:
    request = AsyncMock(side_effect=[{"records": []}, {"panel_id": "new-panel"}])
    items = [
        {
            "type": "command",
            "name": "牌理",
            "desc": "分析日麻牌理",
            "only_admin": False,
        }
    ]
    bot = object()

    with patch("src.qq_plugins.qq_command_panel._request_panel_api", request):
        result = asyncio.run(
            _sync_scope(bot, "group", items)  # type: ignore[arg-type]
        )

    assert result == "created"
    assert request.await_args_list[1].args[1] == "POST"
    assert request.await_args_list[1].kwargs["json"] == {
        "scope": "group",
        "target_type": "all",
        "panel": {"items": items, "remark": PANEL_REMARK},
    }


def test_sync_scope_updates_existing_global_panel() -> None:
    request = AsyncMock(
        side_effect=[
            {
                "records": [
                    {
                        "panel_id": "panel-1",
                        "target_type": "all",
                        "panel": {"items": [], "remark": "manual"},
                    }
                ]
            },
            {"version": 2},
        ]
    )
    items = [
        {
            "type": "command",
            "name": "雀庄绑定",
            "desc": "绑定本群雀庄",
            "only_admin": True,
        }
    ]
    bot = object()

    with patch("src.qq_plugins.qq_command_panel._request_panel_api", request):
        result = asyncio.run(
            _sync_scope(bot, "group", items)  # type: ignore[arg-type]
        )

    assert result == "updated"
    assert request.await_args_list[1].args == (bot, "PUT", "panel-1")


def test_sync_scope_skips_unchanged_panel() -> None:
    items = [
        {
            "type": "command",
            "name": "牌理",
            "desc": "分析日麻牌理",
            "only_admin": False,
        }
    ]
    request = AsyncMock(
        return_value={
            "records": [
                {
                    "panel_id": "panel-1",
                    "target_type": "all",
                    "panel": {"items": items, "remark": PANEL_REMARK},
                }
            ]
        }
    )
    with patch("src.qq_plugins.qq_command_panel._request_panel_api", request):
        result = asyncio.run(
            _sync_scope(object(), "group", items)  # type: ignore[arg-type]
        )

    assert result == "unchanged"
    request.assert_awaited_once()
