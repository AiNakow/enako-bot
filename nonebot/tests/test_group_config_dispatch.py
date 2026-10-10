"""Real NoneBot dispatch, real adapter events and business matchers.

Only outbound transport, camera/model and external business services are replaced.
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import sqlite3
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, Mock

import nonebot
import nonebot.plugin
import pytest
from nonebot.adapters import Event
from nonebot.adapters.onebot.v11 import Bot as OneBot, GroupMessageEvent, PrivateMessageEvent, GroupIncreaseNoticeEvent
from nonebot.adapters.qq import Bot as QQBot, C2CMessageCreateEvent, DirectMessageCreateEvent, GroupAtMessageCreateEvent, GroupMessageCreateEvent, MessageCreateEvent
from nonebot.adapters.qq.config import BotInfo
from nonebot.internal.matcher import MatcherSource
from nonebot.matcher import Matcher, matchers
from nonebot.message import handle_event
from nonebot.permission import Permission
from nonebot.plugin import Plugin
from nonebot.rule import Rule
from PIL import Image
from io import BytesIO

from src.infrastructure_plugins._adapter.onebot11 import OneBotV11Bridge
from src.infrastructure_plugins._adapter.qq import QQBridge
from src.infrastructure_plugins import group_config
from src.infrastructure_plugins.group_config import config, service

KNOWN = frozenset({"bot_assist", "gsz-assist", "mahjong-assist", "hyw_assist"})
ROOT = Path(__file__).parents[1]


def make_event(adapter, text="hello", *, scope="group", group="123", user="10", image=False, admin=True):
    if adapter == "qq":
        values = dict(id="message-id", content=text, timestamp="2026-10-10T12:00:00Z", author={"id": user, "bot": False, "member_openid": user, "user_openid": user, "username": "tester"})
        if image:
            values["attachments"] = [{"url": "https://example.test/hand.png", "content_type": "image/png", "filename": "hand.png"}]
        if scope in {"channel", "direct"}:
            values.update(channel_id="channel", guild_id="guild", to_me=True)
            return (DirectMessageCreateEvent if scope == "direct" else MessageCreateEvent).model_validate(values)
        if scope == "private":
            return C2CMessageCreateEvent.model_validate(values)
        values.update(group_id=group, group_openid=f"different-openid-{group}")
        event = GroupAtMessageCreateEvent.model_validate(values)
        # The bridge reads existing admin metadata from the author.
        event.author.__dict__["member_role"] = "admin" if admin else "member"
        return event
    text = "[CQ:image,file=https://example.test/hand.png]" if image else text
    values = dict(time=1, self_id=100, post_type="message", sub_type="friend" if scope == "private" else "normal", user_id=int(user), message_type=scope, message_id=1, message=text, original_message=text, raw_message=text, font=0, sender={"user_id": int(user), "role": "admin" if admin else "member"}, to_me=True)
    if scope == "private":
        return PrivateMessageEvent.model_validate(values)
    values["group_id"] = int(group)
    return GroupMessageEvent.model_validate(values)


@pytest.fixture(params=["qq", "onebot11"])
def runtime(request, tmp_path, monkeypatch):
    adapter = request.param
    bridge = QQBridge() if adapter == "qq" else OneBotV11Bridge()
    monkeypatch.setattr(group_config, "bridge", bridge)
    monkeypatch.setattr(service, "_snapshot", None)
    path = tmp_path / "group_config.json"
    monkeypatch.setattr(service, "get_plugin_config", lambda _: config.Config(group_config_file=str(path)))
    previous = {key: list(value) for key, value in matchers.items()}
    matchers.clear()
    messages = []
    bot_adapter = SimpleNamespace(config=nonebot.get_driver().config, get_name=lambda: "QQ" if adapter == "qq" else "OneBot V11")
    bot = QQBot(bot_adapter, "100", BotInfo(id="100", token="test", secret="test")) if adapter == "qq" else OneBot(bot_adapter, "100")

    async def send(self, event, message, **kwargs):
        messages.append(message)
        return {}

    monkeypatch.setattr(type(bot), "send", send)

    def initialize(policies):
        path.write_text(json.dumps(policies), encoding="utf-8")
        service.initialize_group_config(known_business_plugins=KNOWN, managed_business_plugins=KNOWN)

    result = SimpleNamespace(adapter=adapter, bridge=bridge, bot=bot, messages=messages, initialize=initialize, path=path, event=lambda *a, **kw: make_event(adapter, *a, **kw))
    yield result
    matchers.clear()
    matchers.update(previous)


def policy(default=False, private=False, groups=None):
    return dict(default_enabled=default, private_enabled=private, groups=groups or {})


def register(monkeypatch, name, handler, *, priority=1, block=True, type_="message", permission=None, rule=None, parent=None, temp=False):
    plugin = Plugin(name=name, module=ModuleType(name), module_name=name, manager=None, parent_plugin=parent)
    monkeypatch.setitem(nonebot.plugin._plugins, plugin.id_, plugin)
    return Matcher.new(type_, handlers=[handler], source=MatcherSource(plugin_id=plugin.id_), priority=priority, block=block, permission=permission, rule=rule, temp=temp)


@pytest.mark.parametrize("enabled", [True, False])
def test_disabled_block_matcher_allows_later_business_matcher(runtime, monkeypatch, enabled):
    runtime.initialize({"hyw_assist": policy(enabled)})
    calls = []

    async def first():
        calls.append("first")

    async def later():
        calls.append("later")

    register(monkeypatch, "hyw_assist", first)
    register(monkeypatch, "bot_assist", later, priority=2)
    asyncio.run(handle_event(runtime.bot, runtime.event()))
    assert calls == (["first"] if enabled else ["later"])
    assert runtime.messages == []


@pytest.mark.parametrize("private_enabled", [True, False])
def test_private_dispatch(runtime, monkeypatch, private_enabled):
    runtime.initialize({"bot_assist": policy(True, private_enabled)})
    handler = AsyncMock()

    async def run():
        await handler()

    register(monkeypatch, "bot_assist", run)
    asyncio.run(handle_event(runtime.bot, runtime.event(scope="private")))
    assert handler.await_count == int(private_enabled)


@pytest.mark.parametrize("allowed", [True, False])
def test_original_permission_and_rule_remain_effective(runtime, monkeypatch, allowed):
    runtime.initialize({"bot_assist": policy(True)})
    calls = []

    async def permission():
        return allowed

    async def rule():
        return allowed

    async def handler():
        calls.append(True)

    register(monkeypatch, "bot_assist", handler, permission=Permission(permission), rule=Rule(rule))
    asyncio.run(handle_event(runtime.bot, runtime.event()))
    assert calls == ([True] if allowed else [])


@pytest.mark.parametrize("name", ["_adapter", "group_config", "qq_command_panel", "nonebot_plugin_waiter", "nonebot_plugin_htmlrender", None])
def test_infrastructure_dependencies_and_unowned_matchers_are_uncontrolled(runtime, monkeypatch, name):
    runtime.initialize({"bot_assist": policy()})
    calls = []

    async def handler():
        calls.append(True)

    if name is None:
        Matcher.new("message", handlers=[handler])
    else:
        register(monkeypatch, name, handler)
    asyncio.run(handle_event(runtime.bot, runtime.event()))
    assert calls == [True]


def test_non_message_business_event_is_uncontrolled(runtime, monkeypatch):
    runtime.initialize({"bot_assist": policy()})
    calls = []

    async def handler():
        calls.append(True)

    register(monkeypatch, "bot_assist", handler, type_="notice")
    event = GroupIncreaseNoticeEvent.model_validate(dict(time=1, self_id=100, post_type="notice", notice_type="group_increase", sub_type="approve", group_id=123, operator_id=10, user_id=11))
    asyncio.run(handle_event(runtime.bot, event))
    assert calls == [True]


@pytest.mark.parametrize("group_id", [None, "", "has space", "a:b", "x" * 257])
def test_invalid_runtime_group_is_skipped_without_message_leak(runtime, monkeypatch, group_id):
    runtime.initialize({"bot_assist": policy(True)})
    calls = []
    logs = []
    monkeypatch.setattr(group_config.logger, "warning", logs.append)

    async def handler():
        calls.append(True)

    register(monkeypatch, "bot_assist", handler)
    event = runtime.event("SECRET-MESSAGE")
    event.__dict__["group_id"] = group_id
    asyncio.run(handle_event(runtime.bot, event))
    assert calls == []
    assert len(logs) == 1
    assert "bot_assist" in logs[0] and "SECRET-MESSAGE" not in logs[0]


@pytest.mark.parametrize("group_id", ["01", "0", "１２"])
def test_numeric_group_ids_follow_each_adapter_contract(runtime, monkeypatch, group_id):
    runtime.initialize({"bot_assist": policy(True)})
    calls = []

    async def handler():
        calls.append(True)

    register(monkeypatch, "bot_assist", handler)
    event = runtime.event()
    event.__dict__["group_id"] = group_id
    asyncio.run(handle_event(runtime.bot, event))
    assert bool(calls) is (runtime.adapter == "qq")


def test_unconfigured_business_does_not_validate_group(runtime, monkeypatch):
    runtime.initialize({})
    calls = []

    async def handler():
        calls.append(True)

    register(monkeypatch, "bot_assist", handler)
    event = runtime.event()
    event.__dict__["group_id"] = None
    asyncio.run(handle_event(runtime.bot, event))
    assert calls == [True]


def test_group_id_source_and_adapter_prefix(runtime, monkeypatch):
    other = "onebot11" if runtime.adapter == "qq" else "qq"
    runtime.initialize({"bot_assist": policy(groups={f"{runtime.adapter}:123": {"enabled": True}, f"{other}:123": {"enabled": False}})})
    calls = []

    async def handler():
        calls.append(True)

    register(monkeypatch, "bot_assist", handler)
    asyncio.run(handle_event(runtime.bot, runtime.event()))
    assert calls == [True]


@pytest.mark.parametrize("scope", ["channel", "direct"])
def test_qq_guild_messages_are_not_c2c(runtime, monkeypatch, scope):
    if runtime.adapter != "qq":
        pytest.skip("QQ guild events do not apply to OneBot")
    runtime.initialize({"bot_assist": policy(False, False)})
    calls = []

    async def handler():
        calls.append(True)

    register(monkeypatch, "bot_assist", handler)
    asyncio.run(handle_event(runtime.bot, runtime.event(scope=scope)))
    assert calls == [True]


def test_business_owned_temporary_matcher_is_controlled(runtime, monkeypatch):
    runtime.initialize({"bot_assist": policy()})
    parent = Plugin(name="bot_assist", module=ModuleType("bot_assist"), module_name="bot_assist", manager=None)
    calls = []

    async def handler():
        calls.append(True)

    register(monkeypatch, "child", handler, parent=parent, temp=True)
    asyncio.run(handle_event(runtime.bot, runtime.event()))
    assert calls == []


@pytest.fixture
def businesses(runtime, tmp_path, monkeypatch):
    driver_config = nonebot.get_driver().config
    monkeypatch.setattr(driver_config, "people_counter_device_serial", "TEST-DEVICE", raising=False)
    monkeypatch.setattr(driver_config, "people_counter_access_token", "test-token", raising=False)
    modules = {}
    for name in ("bot_assist", "hyw_assist", "gsz-assist", "mahjong-assist"):
        path = f"src.plugins.{name}"
        plugin = nonebot.get_plugin(name)
        if plugin is None:
            if name in {"gsz-assist", "mahjong-assist"}:
                spec = importlib.util.spec_from_file_location(f"{path}.common", ROOT / f"src/plugins/{name}/common.py")
                common = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(common)
                common.data_dir = str(tmp_path / name)
                Path(common.data_dir).mkdir()
                if name == "gsz-assist":
                    common.database_dir = str(tmp_path / name / "database")
                    common.gsz_userdata_file = str(Path(common.database_dir) / "users.db")
                    common.gsz_ratedata_file = str(Path(common.database_dir) / "rates.db")
                else:
                    common.data_collection_file = str(Path(common.data_dir) / "images.txt")
                sys.modules[spec.name] = common
            plugin = nonebot.load_plugin(path)
            assert plugin is not None
        modules[name] = plugin.module
        if hasattr(plugin.module, "bridge"):
            monkeypatch.setattr(plugin.module, "bridge", runtime.bridge)
        for matcher in plugin.matcher:
            if matcher not in matchers[matcher.priority]:
                matchers[matcher.priority].append(matcher)
    return modules


@pytest.mark.parametrize("enabled", [True, False])
@pytest.mark.parametrize("text", ["音游几", "中二几", "舞萌几"])
def test_people_count_capture_inference_and_reply(runtime, businesses, monkeypatch, enabled, text):
    runtime.initialize({"hyw_assist": policy(enabled)})
    counter = businesses["hyw_assist"].service
    capture = Mock()
    model = Mock()
    with Image.new("RGB", counter.settings.machine_areas.reference_size) as image:
        data = BytesIO()
        image.save(data, format="PNG")
    capture.capture.return_value = data.getvalue()
    model.predict.return_value = ([], [], [])
    monkeypatch.setattr(counter, "_capture", capture)
    monkeypatch.setattr(counter, "_model", model)
    monkeypatch.setattr(businesses["hyw_assist"], "busy", asyncio.Lock())
    asyncio.run(handle_event(runtime.bot, runtime.event(text)))
    assert capture.capture.call_count == model.predict.call_count == int(enabled)
    if enabled:
        assert "音游房当前有 0 人" in str(runtime.messages[-1])
    else:
        assert runtime.messages == []


@pytest.mark.parametrize("text", ["公式战小助手", "日麻小助手", "/面麻计分器", "/牌理", "/天凤牌理", "enako"])
@pytest.mark.parametrize("enabled", [True, False])
def test_business_help_commands_and_aliases(runtime, businesses, text, enabled):
    runtime.initialize({name: policy(enabled, enabled) for name in KNOWN})
    asyncio.run(handle_event(runtime.bot, runtime.event(text)))
    assert bool(runtime.messages) is enabled


@pytest.mark.parametrize("text", ["/公式战绑定 player", "/吃鱼 player", "/仇恨榜 player", "/好人榜 player", "/雀庄绑定 shop", "/排行榜"])
def test_disabled_formula_has_no_api_or_database_side_effects(runtime, businesses, monkeypatch, text):
    runtime.initialize({"gsz-assist": policy()})
    gsz = businesses["gsz-assist"]
    calls = {}
    for name in ("bind_userinfo", "get_userinfo_by_name", "get_rank_top", "get_rank_last", "bind_rateinfo", "get_rateinfo_by_group_id"):
        calls[name] = AsyncMock()
        monkeypatch.setattr(gsz.GszService, name, calls[name])
    module = sys.modules[f"{gsz.__name__}.service"]
    api = Mock()
    connect = Mock()
    monkeypatch.setattr(module, "FormulaApiClient", api)
    monkeypatch.setattr(module.sqlite3, "connect", connect)
    asyncio.run(handle_event(runtime.bot, runtime.event(text)))
    assert all(call.await_count == 0 for call in calls.values())
    api.assert_not_called()
    connect.assert_not_called()
    assert runtime.messages == []


@pytest.mark.parametrize("enabled,admin,expected", [(False, True, False), (True, False, False), (True, True, True)])
def test_formula_binding_preserves_group_id_and_admin_rule(runtime, businesses, monkeypatch, enabled, admin, expected):
    runtime.initialize({"gsz-assist": policy(enabled)})
    bind = AsyncMock(return_value=True)
    monkeypatch.setattr(businesses["gsz-assist"].GszService, "bind_rateinfo", bind)
    asyncio.run(handle_event(runtime.bot, runtime.event("/雀庄绑定 shop", admin=admin)))
    assert bind.await_count == int(expected)
    if expected:
        bind.assert_awaited_once_with(group_id="123", rate_name="shop")


def test_formula_real_database_binding_survives_disabling(runtime, businesses, tmp_path, monkeypatch):
    runtime.initialize({"gsz-assist": policy(True)})
    gsz = businesses["gsz-assist"]
    module = sys.modules[f"{gsz.__name__}.service"]
    manager = type(gsz.GszService.ratedata_manager)()
    manager._db_path = str(tmp_path / "binding.db")
    monkeypatch.setattr(gsz.GszService, "ratedata_manager", manager)
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.get.return_value = {"records": [{"id": 7, "name": "shop"}]}
    factory = Mock(return_value=client)
    monkeypatch.setattr(module, "FormulaApiClient", factory)
    asyncio.run(handle_event(runtime.bot, runtime.event("/雀庄绑定 shop")))
    assert "绑定成功" in str(runtime.messages[-1])
    assert factory.call_count == 1
    with sqlite3.connect(manager._db_path) as connection:
        assert connection.execute("SELECT groupId, rateId, rateName FROM ratedata").fetchall() == [("123", 7, "shop")]
    runtime.path.write_text(json.dumps({"gsz-assist": policy()}))
    monkeypatch.setattr(service, "_snapshot", None)
    service.initialize_group_config(known_business_plugins=KNOWN, managed_business_plugins=KNOWN)
    runtime.messages.clear()
    asyncio.run(handle_event(runtime.bot, runtime.event("/雀庄绑定 other")))
    assert runtime.messages == []
    assert factory.call_count == 1
    assert manager.get_ratedata(["123"]) == [{"groupId": "123", "rateId": 7, "rateName": "shop"}]


def test_private_business_rules_are_preserved(runtime, businesses, monkeypatch):
    runtime.initialize({"hyw_assist": policy(False, False), "gsz-assist": policy(False, True), "mahjong-assist": policy(False, True), "bot_assist": policy(False, True)})
    count = AsyncMock()
    bind = AsyncMock()
    monkeypatch.setattr(businesses["hyw_assist"].service, "count_with_occupancy_async", count)
    monkeypatch.setattr(businesses["gsz-assist"].GszService, "bind_rateinfo", bind)

    async def scenario():
        for text in ("音游几", "enako", "/面麻计分器", "/雀庄绑定 shop"):
            await handle_event(runtime.bot, runtime.event(text, scope="private"))

    asyncio.run(scenario())
    count.assert_not_awaited()
    bind.assert_not_awaited()
    assert len(runtime.messages) == 3
    assert "该命令只能在群聊中使用" in str(runtime.messages[-1])


def test_ocr_disabled_does_not_prompt_or_create_waiter(runtime, businesses, monkeypatch):
    runtime.initialize({"mahjong-assist": policy()})
    waiter = Mock()
    monkeypatch.setattr(businesses["mahjong-assist"], "waiter", waiter)
    asyncio.run(handle_event(runtime.bot, runtime.event("/识图牌理")))
    waiter.assert_not_called()
    assert runtime.messages == []


def test_ocr_session_completes_only_for_same_group_and_user(runtime, businesses, monkeypatch):
    runtime.initialize({"mahjong-assist": policy(groups={f"{runtime.adapter}:123": {"enabled": True}})})
    mahjong = businesses["mahjong-assist"]
    infer = Mock(return_value="123m123p123s111z22z")
    analyse = AsyncMock(return_value=b"image")
    monkeypatch.setattr(mahjong.MahjongService, "get_hand_from_image", infer)
    monkeypatch.setattr(mahjong.MahjongService, "tenhou_paili_analyse", analyse)

    async def scenario():
        original = set(m for values in matchers.values() for m in values)
        task = asyncio.create_task(handle_event(runtime.bot, runtime.event("/识图牌理")))
        try:
            for _ in range(1000):
                if matchers.get(0):
                    break
                await asyncio.sleep(.001)
            assert matchers.get(0), "OCR did not create waiter"
            for waiter_matcher in matchers[0]:
                assert service.resolve_business_plugin(waiter_matcher()) is None
            await handle_event(runtime.bot, runtime.event(image=True, group="456"))
            await handle_event(runtime.bot, runtime.event(image=True, user="11"))
            assert not task.done()
            infer.assert_not_called()
            assert len(runtime.messages) == 1
            await handle_event(runtime.bot, runtime.event(image=True))
            await asyncio.wait_for(task, 2)
            assert len(runtime.messages) == 3
            assert "推理中" in str(runtime.messages[1])
            infer.assert_called_once_with("https://example.test/hand.png")
            analyse.assert_awaited_once_with("123m123p123s111z22z", 0)
            assert all(m in original for values in matchers.values() for m in values)
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    asyncio.run(scenario())


def test_dispatch_retains_snapshot_until_new_initialization(runtime, businesses, monkeypatch):
    runtime.initialize({"bot_assist": policy(True)})
    asyncio.run(handle_event(runtime.bot, runtime.event("enako")))
    assert len(runtime.messages) == 1
    runtime.path.write_text(json.dumps({"bot_assist": policy()}))
    asyncio.run(handle_event(runtime.bot, runtime.event("enako")))
    assert len(runtime.messages) == 2
    monkeypatch.setattr(service, "_snapshot", None)
    service.initialize_group_config(known_business_plugins=KNOWN, managed_business_plugins=KNOWN)
    asyncio.run(handle_event(runtime.bot, runtime.event("enako")))
    assert len(runtime.messages) == 2


@pytest.mark.parametrize("group,expected", [("123", False), ("456", True), ("789", True)])
def test_explicit_disable_overrides_enabled_default_in_dispatch(runtime, businesses, group, expected):
    runtime.initialize({"bot_assist": policy(True, True, {f"{runtime.adapter}:123": {"enabled": False}})})
    asyncio.run(handle_event(runtime.bot, runtime.event("enako", group=group)))
    assert bool(runtime.messages) is expected


def test_qq_bridge_scope_boundaries_and_group_id():
    bridge = QQBridge()
    for scope in ("group", "private", "channel", "direct"):
        event = make_event("qq", scope=scope)
        assert bridge.is_private_event(event) is (scope == "private")
        assert bridge.is_group_event(event) is (scope == "group")
    event = make_event("qq")
    assert bridge.get_group_id(event) == "123"
    assert event.group_openid != bridge.get_group_id(event)
    plain = GroupMessageCreateEvent.model_validate(event.model_dump())
    assert bridge.is_group_event(plain)
    assert bridge.get_group_id(SimpleNamespace()) is None
    assert not bridge.is_private_event(SimpleNamespace())


def test_onebot_bridge_private_and_group_boundaries():
    bridge = OneBotV11Bridge()
    assert bridge.is_private_event(make_event("onebot11", scope="private"))
    event = make_event("onebot11")
    assert not bridge.is_private_event(event)
    assert bridge.is_group_event(event)
    assert bridge.get_group_id(event) == "123"
    assert bridge.get_group_id(SimpleNamespace()) is None
