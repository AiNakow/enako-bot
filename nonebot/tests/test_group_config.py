from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from src.infrastructure_plugins.group_config import config, service

KNOWN = frozenset({"bot_assist", "gsz-assist", "mahjong-assist", "hyw_assist"})


def policy(default=True, private=True, groups=None):
    return {"default_enabled": default, "private_enabled": private, "groups": groups or {}}


@pytest.fixture
def initialize(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "_snapshot", None)
    path = tmp_path / "group_config.json"
    monkeypatch.setattr(service, "get_plugin_config", lambda _: config.Config(group_config_file=str(path)))

    def load(value, managed=KNOWN):
        path.write_text(json.dumps(value), encoding="utf-8")
        service.initialize_group_config(known_business_plugins=KNOWN, managed_business_plugins=managed)
        return path

    return load


def test_example_and_all_expected_decisions(initialize):
    example = Path(__file__).parents[2] / "docs/examples/group_config.json"
    initialize(json.loads(example.read_text(encoding="utf-8")))
    expected = {
        "qq:group_a": [True, True, True, True],
        "qq:group_b": [True, False, True, True],
        "qq:group_c": [False, True, False, True],
        "qq:unlisted": [False, True, True, True],
        "onebot11:123456789": [True, True, True, True],
    }
    names = ["hyw_assist", "mahjong-assist", "gsz-assist", "bot_assist"]
    for key, enabled in expected.items():
        assert [service.is_enabled(name, scope="group", group_key=key) for name in names] == enabled
    assert [service.is_enabled(name, scope="private", group_key=None) for name in names] == [False, True, True, True]


def test_unconfigured_plugin_and_snapshot_restart(initialize, monkeypatch):
    path = initialize({})
    for name in KNOWN:
        assert service.is_enabled(name, scope="private", group_key=None)
        assert service.is_enabled(name, scope="group", group_key="qq:unlisted")
    path.write_text(json.dumps({"bot_assist": policy(False, False)}), encoding="utf-8")
    assert service.is_enabled("bot_assist", scope="group", group_key="qq:unlisted")
    path.unlink()
    assert service.is_enabled("bot_assist", scope="private", group_key=None)
    monkeypatch.setattr(service, "_snapshot", None)
    initialize({"bot_assist": policy(False, False)})
    assert not service.is_enabled("bot_assist", scope="private", group_key=None)


def test_snapshot_is_recursively_immutable(initialize):
    initialize({"bot_assist": policy(groups={"qq:a": {"enabled": True}})})
    snapshot = service._get_snapshot()
    with pytest.raises(TypeError):
        snapshot.policies["bot_assist"] = None
    with pytest.raises(FrozenInstanceError):
        snapshot.managed = frozenset()
    with pytest.raises(FrozenInstanceError):
        snapshot.policies["bot_assist"].default_enabled = False
    with pytest.raises(TypeError):
        snapshot.policies["bot_assist"].groups["qq:a"] = False


@pytest.mark.parametrize("default", [True, False])
@pytest.mark.parametrize("private", [True, False])
def test_defaults_and_overrides(initialize, default, private):
    initialize({"bot_assist": policy(default, private, {"qq:123": {"enabled": not default}, "onebot11:123": {"enabled": default}})})
    assert service.is_enabled("bot_assist", scope="group", group_key="qq:other") is default
    assert service.is_enabled("bot_assist", scope="group", group_key="qq:123") is not default
    assert service.is_enabled("bot_assist", scope="group", group_key="onebot11:123") is default
    assert service.is_enabled("bot_assist", scope="private", group_key=None) is private


def test_initialization_contract(initialize, monkeypatch):
    with pytest.raises(RuntimeError, match="not initialized"):
        service.is_enabled("bot_assist", scope="private", group_key=None)
    with pytest.raises(RuntimeError, match="managed_plugins_not_known"):
        initialize({}, managed=frozenset({"unknown"}))
    initialize({})
    with pytest.raises(RuntimeError, match="already initialized"):
        initialize({})


@pytest.mark.parametrize("kwargs", [
    {"plugin_name": "unknown", "scope": "private", "group_key": None},
    {"plugin_name": "bot_assist", "scope": "channel", "group_key": None},
    {"plugin_name": "bot_assist", "scope": "private", "group_key": "qq:a"},
    {"plugin_name": "bot_assist", "scope": "group", "group_key": None},
    {"plugin_name": "bot_assist", "scope": "group", "group_key": ""},
    {"plugin_name": "bot_assist", "scope": "group", "group_key": "qq:a\n"},
])
def test_invalid_interface_calls(initialize, kwargs):
    initialize({})
    with pytest.raises(ValueError):
        service.is_enabled(**kwargs)


def test_known_but_not_managed_policy_is_fully_validated(initialize):
    initialize({"hyw_assist": policy(False, False)}, managed=frozenset({"bot_assist"}))
    with pytest.raises(ValueError, match="not managed"):
        service.is_enabled("hyw_assist", scope="private", group_key=None)


@pytest.mark.parametrize("name", ["unknown", "BOT_ASSIST", "机器人小助手", "_adapter", "group_config", "qq_command_panel", "nonebot_plugin_htmlrender", "nonebot_plugin_waiter", "version", "defaults", "plugins", "$schema", "src.plugins.bot_assist"])
def test_unknown_plugin_names(initialize, name):
    with pytest.raises(RuntimeError, match="unknown_business_plugin"):
        initialize({name: policy()})


@pytest.mark.parametrize("key", ["qq:a", "qq:ABC_-中文", "qq:" + "a" * 256, "onebot11:1", "onebot11:" + "1" * 256])
def test_valid_group_keys(key):
    config.validate_group_key(key)


@pytest.mark.parametrize("key", ["QQ:a", "onebot-v11:1", "onebot_v11:1", "qq:", "qq:a:b", "qq:a b", "qq:a\n", "qq:\t", "qq:a\u00a0", "qq:" + "a" * 257, "onebot11:0", "onebot11:01", "onebot11:+1", "onebot11:1.0", "onebot11:a", "onebot11:１２", "onebot11:" + "1" * 257, "onebot11:1\n", "qq", None, 1])
def test_invalid_group_keys(key):
    with pytest.raises(ValueError):
        config.validate_group_key(key)


def test_unloaded_disabled_other_adapter_entries_validated(initialize):
    with pytest.raises(RuntimeError, match="invalid_group_key"):
        initialize({"hyw_assist": policy(groups={"onebot11:01": {"enabled": False}})}, managed=frozenset({"bot_assist"}))


INVALID_POLICIES = [
    None, True, [], "x", 1,
    {},
    {"private_enabled": True, "groups": {}},
    {"default_enabled": True, "groups": {}},
    {"default_enabled": True, "private_enabled": True},
    *[{**policy(), field: value} for field in ("default_enabled", "private_enabled") for value in (None, "true", "false", 0, 1)],
    *[{**policy(), "groups": value} for value in (None, [], "x", True)],
    *[{**policy(), field: {}} for field in ("config", "credential_ref", "camera", "regions_file", "channel_enabled")],
    *[policy(groups={"qq:a": value}) for value in (None, [], True, {}, {"enabled": None}, {"enabled": 0}, {"enabled": 1}, {"enabled": "true"}, {"enabled": "false"}, {"enabled": False, "config": {}}, {"enabled": False, "credential_ref": "SECRET-MARKER"})],
]


@pytest.mark.parametrize("value", INVALID_POLICIES)
def test_invalid_policy_fields_are_redacted(initialize, value):
    with pytest.raises(RuntimeError) as exc:
        initialize({"hyw_assist": value}, managed=frozenset())
    assert "$.hyw_assist" in str(exc.value)
    assert "SECRET-MARKER" not in str(exc.value)
    assert exc.value.__suppress_context__


@pytest.mark.parametrize("raw", [
    "", "// comment\n{}", "{,}", '{"bot_assist": {}} trailing',
    '{"bot_assist": {},}', "\ufeff{}", "NaN", "Infinity", "-Infinity",
    '{"bot_assist": {"default_enabled": NaN}}',
    '{"bot_assist": {}, "bot_assist": {}}',
    '{"bot_assist": {"groups": {}, "groups": {}}}',
    '{"bot_assist": {"groups": {"qq:a": {}, "qq:a": {}}}}',
    '{"bot_assist": {"groups": {"qq:a": {"enabled": true, "enabled": false}}}}',
    '[{"x":1,"x":2}]', "[]", "null", "1", '"object"',
])
def test_invalid_json_files(tmp_path, raw):
    path = tmp_path / "group.json"
    path.write_text(raw, encoding="utf-8")
    with pytest.raises(RuntimeError) as exc:
        config.read_policies(path, KNOWN)
    assert str(path) in str(exc.value)
    assert "$" in str(exc.value)


def test_duplicate_error_has_full_location(tmp_path):
    path = tmp_path / "group.json"
    path.write_text('{"bot_assist":{"groups":{"qq:a":{"enabled":true,"enabled":false}}}}')
    with pytest.raises(RuntimeError, match=r"\$\.bot_assist\.groups\.qq:a\.enabled: duplicate_key"):
        config.read_policies(path, KNOWN)


@pytest.mark.parametrize("kind", ["missing", "directory", "encoding", "permission"])
def test_unreadable_files(tmp_path, monkeypatch, kind):
    path = tmp_path / "group.json"
    if kind == "directory":
        path.mkdir()
    elif kind == "encoding":
        path.write_bytes(b"\xff\xfe")
    elif kind == "permission":
        path.write_text("{}")
        # Deterministic even when CI runs as root.
        monkeypatch.setattr(Path, "read_text", lambda *a, **k: (_ for _ in ()).throw(PermissionError("SECRET-MARKER")))
    with pytest.raises(RuntimeError) as exc:
        config.read_policies(path, KNOWN)
    assert "SECRET-MARKER" not in str(exc.value)


@pytest.mark.parametrize("value", ["", " \n\t", None, 123])
def test_invalid_environment_path(monkeypatch, value):
    monkeypatch.setattr(service, "_snapshot", None)
    monkeypatch.setattr(service, "get_plugin_config", lambda _: config.Config(group_config_file=value))
    with pytest.raises(RuntimeError, match="GROUP_CONFIG_FILE <unresolved>"):
        service.initialize_group_config(known_business_plugins=KNOWN, managed_business_plugins=KNOWN)


@pytest.mark.parametrize("configured", [None, "custom/groups.json", "absolute"])
def test_path_resolution_does_not_follow_cwd(tmp_path, monkeypatch, configured):
    monkeypatch.setattr(service, "_snapshot", None)
    monkeypatch.setattr(service, "PROJECT_ROOT", tmp_path / "project")
    path = (tmp_path / "absolute.json" if configured == "absolute" else service.PROJECT_ROOT / (configured or "plugin_data/group_config.json"))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(service, "get_plugin_config", lambda _: config.Config() if configured is None else config.Config(group_config_file=str(path) if configured == "absolute" else configured))
    service.initialize_group_config(known_business_plugins=KNOWN, managed_business_plugins=KNOWN)
    assert service._get_snapshot().policies == {}
    assert config.PROJECT_ROOT == Path(__file__).resolve().parents[1]


def test_owner_resolution_uses_nearest_plugin(initialize):
    initialize({})
    outer = SimpleNamespace(name="bot_assist", parent_plugin=None)
    inner = SimpleNamespace(name="mahjong-assist", parent_plugin=outer)
    dependency = SimpleNamespace(name="nonebot_plugin_waiter", parent_plugin=inner)
    assert service.resolve_business_plugin(SimpleNamespace(plugin=dependency)) == "mahjong-assist"
    assert service.resolve_business_plugin(SimpleNamespace(plugin=outer)) == "bot_assist"
    assert service.resolve_business_plugin(SimpleNamespace(plugin=None)) is None
    assert service.resolve_business_plugin(SimpleNamespace(plugin=SimpleNamespace(name="unknown", parent_plugin=None))) is None


def test_models_are_strict_and_frozen():
    override = config.GroupOverride(enabled=True)
    with pytest.raises(ValidationError):
        override.enabled = False
    with pytest.raises(ValidationError):
        config.POLICIES.validate_python({1: policy()}, strict=True)
