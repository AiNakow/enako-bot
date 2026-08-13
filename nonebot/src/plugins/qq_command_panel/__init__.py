from __future__ import annotations

import unicodedata
from collections.abc import Iterable, Mapping
from typing import Any, Literal

from nonebot import get_driver, logger
from nonebot.adapters import Bot
from nonebot.adapters.qq import Bot as QQBot
from nonebot.drivers import Request
from nonebot.matcher import Matcher, matchers as registered_matchers
from nonebot.permission import SuperUser
from nonebot.plugin import PluginMetadata
from nonebot.rule import CommandRule


PanelScope = Literal["c2c", "group", "channel", "dm"]

PANEL_METADATA_KEY = "qq_command_panel"
PANEL_REMARK = "Managed by NoneBot command panel sync"
PANEL_SCOPES: tuple[PanelScope, ...] = ("c2c", "group", "channel", "dm")
MAX_PANEL_ITEMS = 20
MAX_NAME_LENGTH = 14
MAX_DESCRIPTION_LENGTH = 30

__plugin_meta__ = PluginMetadata(
    name="QQ 指令面板同步",
    description="启动时将 NoneBot 指令同步到 QQ 官方机器人指令面板",
    usage="自动运行，无需手动触发",
    supported_adapters={"~qq"},
)

_synced_bot_ids: set[str] = set()
_syncing_bot_ids: set[str] = set()


def _command_name(command: tuple[str, ...]) -> str:
    separators = sorted(get_driver().config.command_sep)
    return (separators[0] if separators else ".").join(command)


def _display_width(text: str) -> int:
    return sum(
        2 if unicodedata.east_asian_width(char) in {"W", "F", "A"} else 1
        for char in text
    )


def _truncate_to_width(text: str, max_width: int) -> str:
    result: list[str] = []
    width = 0
    for char in text:
        char_width = _display_width(char)
        if width + char_width > max_width:
            break
        result.append(char)
        width += char_width
    return "".join(result)


def _is_superuser_only(matcher: type[Matcher]) -> bool:
    return any(
        isinstance(checker.call, SuperUser)
        for checker in matcher.permission.checkers
    )


def _matcher_panel_metadata(matcher: type[Matcher]) -> Mapping[str, Any]:
    metadata = matcher._default_state.get(PANEL_METADATA_KEY, {})
    return metadata if isinstance(metadata, Mapping) else {}


def collect_panel_items(
    matchers: Iterable[type[Matcher]],
) -> dict[PanelScope, list[dict[str, Any]]]:
    """Collect command matchers and convert them into QQ panel items."""

    commands: dict[str, dict[str, Any]] = {}
    command_scopes: dict[str, set[str]] = {}

    for matcher in matchers:
        metadata = _matcher_panel_metadata(matcher)
        description = metadata.get("description")
        canonical_name = metadata.get("name")
        only_admin = bool(metadata.get("only_admin")) or _is_superuser_only(matcher)
        configured_scopes = metadata.get("scopes", PANEL_SCOPES)
        scopes = {
            scope for scope in configured_scopes if scope in PANEL_SCOPES
        }

        for checker in matcher.rule.checkers:
            if not isinstance(checker.call, CommandRule):
                continue

            registered_commands = list(checker.call.cmds)
            if isinstance(canonical_name, str):
                registered_commands = [
                    command
                    for command in registered_commands
                    if _command_name(command) == canonical_name
                ]
                if not registered_commands:
                    logger.warning(
                        f"Skipping QQ command panel matcher: canonical command "
                        f"{canonical_name!r} was not found in its CommandRule"
                    )
            elif len(registered_commands) > 1:
                logger.warning(
                    "A QQ command panel matcher contains aliases but has no "
                    f"{PANEL_METADATA_KEY}.name metadata; using "
                    f"{_command_name(registered_commands[0])!r} only"
                )
                registered_commands = registered_commands[:1]

            for command in registered_commands:
                name = _command_name(command)
                if not name or _display_width(name) > MAX_NAME_LENGTH:
                    logger.warning(
                        f"Skipping QQ command panel item {name!r}: name exceeds "
                        f"{MAX_NAME_LENGTH} characters"
                    )
                    continue

                desc = (
                    str(description)
                    if description
                    else f"使用{name}指令"
                )
                desc = _truncate_to_width(desc, MAX_DESCRIPTION_LENGTH)

                item = commands.setdefault(
                    name,
                    {
                        "type": "command",
                        "name": name,
                        "desc": desc,
                        "only_admin": only_admin,
                    },
                )
                # If duplicate matchers register the same command, keep the stricter
                # permission and any explicit description.
                item["only_admin"] = bool(item["only_admin"] or only_admin)
                if description:
                    item["desc"] = desc
                command_scopes.setdefault(name, set()).update(scopes)

    result: dict[PanelScope, list[dict[str, Any]]] = {}
    for scope in PANEL_SCOPES:
        items = [
            commands[name]
            for name in commands
            if scope in command_scopes[name]
        ]
        if len(items) > MAX_PANEL_ITEMS:
            skipped = ", ".join(item["name"] for item in items[MAX_PANEL_ITEMS:])
            logger.warning(
                f"QQ command panel scope {scope} supports at most "
                f"{MAX_PANEL_ITEMS} items; skipped: {skipped}"
            )
        result[scope] = items[:MAX_PANEL_ITEMS]
    return result


def collect_registered_panel_items() -> dict[PanelScope, list[dict[str, Any]]]:
    matchers = (
        matcher
        for priority_matchers in registered_matchers.values()
        for matcher in priority_matchers
    )
    return collect_panel_items(matchers)


async def _request_panel_api(
    bot: QQBot,
    method: str,
    *path: str,
    params: dict[str, Any] | None = None,
    json: dict[str, Any] | None = None,
) -> Any:
    request = Request(
        method,
        bot.adapter.get_api_base().joinpath("v2", "panels", *path),
        params=params,
        json=json,
    )
    return await bot._request(request)


def _normalized_items(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    return [
        {
            "type": item.get("type"),
            "name": item.get("name"),
            "desc": item.get("desc", ""),
            "only_admin": bool(item.get("only_admin", False)),
        }
        for item in items
        if isinstance(item, Mapping) and item.get("type") == "command"
    ]


async def _sync_scope(
    bot: QQBot,
    scope: PanelScope,
    items: list[dict[str, Any]],
) -> Literal["created", "updated", "unchanged"]:
    response = await _request_panel_api(
        bot,
        "GET",
        params={"scope": scope, "limit": 50},
    )
    if not isinstance(response, Mapping):
        raise RuntimeError(f"Invalid QQ panel list response: {response!r}")

    records = response.get("records", [])
    if not isinstance(records, list):
        raise RuntimeError(f"Invalid QQ panel records: {records!r}")

    global_records = [
        record
        for record in records
        if isinstance(record, Mapping) and record.get("target_type") == "all"
    ]
    managed = next(
        (
            record
            for record in global_records
            if isinstance(record.get("panel"), Mapping)
            and record["panel"].get("remark") == PANEL_REMARK
        ),
        None,
    )
    existing = managed or (global_records[0] if global_records else None)
    desired_panel = {"items": items, "remark": PANEL_REMARK}

    if existing is None:
        await _request_panel_api(
            bot,
            "POST",
            json={
                "scope": scope,
                "target_type": "all",
                "panel": desired_panel,
            },
        )
        return "created"

    panel_id = existing.get("panel_id")
    if not isinstance(panel_id, str) or not panel_id:
        raise RuntimeError(f"QQ panel record has no panel_id: {existing!r}")

    current_panel = existing.get("panel", {})
    current_items = (
        current_panel.get("items", [])
        if isinstance(current_panel, Mapping)
        else []
    )
    current_remark = (
        current_panel.get("remark", "")
        if isinstance(current_panel, Mapping)
        else ""
    )
    if (
        _normalized_items(current_items) == _normalized_items(items)
        and current_remark == PANEL_REMARK
    ):
        return "unchanged"

    await _request_panel_api(
        bot,
        "PUT",
        panel_id,
        json={"panel": desired_panel},
    )
    return "updated"


async def synchronize_command_panels(bot: QQBot) -> dict[PanelScope, str]:
    items_by_scope = collect_registered_panel_items()
    results: dict[PanelScope, str] = {}
    for scope in PANEL_SCOPES:
        results[scope] = await _sync_scope(bot, scope, items_by_scope[scope])
    return results


async def _sync_on_connect(bot: Bot) -> None:
    # The plugin can be discovered while another adapter is selected, but it must
    # never call QQ APIs for those bots.
    if (
        not isinstance(bot, QQBot)
        or bot.self_id in _synced_bot_ids
        or bot.self_id in _syncing_bot_ids
    ):
        return

    _syncing_bot_ids.add(bot.self_id)
    try:
        results = await synchronize_command_panels(bot)
    except Exception:
        logger.exception(
            f"Failed to synchronize QQ command panels for bot {bot.self_id}"
        )
        return
    finally:
        _syncing_bot_ids.discard(bot.self_id)

    _synced_bot_ids.add(bot.self_id)
    summary = ", ".join(f"{scope}={status}" for scope, status in results.items())
    logger.info(
        f"Synchronized QQ command panels for bot {bot.self_id}: {summary}"
    )


get_driver().on_bot_connect(_sync_on_connect)
