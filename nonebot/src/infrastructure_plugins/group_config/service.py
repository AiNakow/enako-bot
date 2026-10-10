"""Immutable process snapshot and the single policy decision path."""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal, Mapping

from nonebot import get_plugin_config
from nonebot.matcher import Matcher
from pydantic import ValidationError

from .config import Config, PROJECT_ROOT, read_policies, validate_group_key, validation_locations


@dataclass(frozen=True)
class _Policy:
    default_enabled: bool
    private_enabled: bool
    groups: Mapping[str, bool]


@dataclass(frozen=True)
class _Snapshot:
    managed: frozenset[str]
    policies: Mapping[str, _Policy]


_snapshot: _Snapshot | None = None


def initialize_group_config(
    *, known_business_plugins: frozenset[str], managed_business_plugins: frozenset[str],
) -> None:
    global _snapshot
    if _snapshot is not None:
        raise RuntimeError("group config already initialized")
    try:
        configured_path = get_plugin_config(Config).group_config_file
    except ValidationError as error:
        raise RuntimeError(f"Invalid GROUP_CONFIG_FILE <unresolved>: {validation_locations(error)}") from None
    path = configured_path if configured_path.is_absolute() else PROJECT_ROOT / configured_path
    if not managed_business_plugins <= known_business_plugins:
        raise RuntimeError(f"Invalid group config {path}: $: managed_plugins_not_known")
    policies = read_policies(path, known_business_plugins)
    _snapshot = _Snapshot(
        managed=managed_business_plugins,
        policies=MappingProxyType({
            name: _Policy(
                default_enabled=policy.default_enabled,
                private_enabled=policy.private_enabled,
                groups=MappingProxyType({key: override.enabled for key, override in policy.groups.items()}),
            )
            for name, policy in policies.items()
        }),
    )


def _get_snapshot() -> _Snapshot:
    if _snapshot is None:
        raise RuntimeError("group config not initialized")
    return _snapshot


def resolve_business_plugin(matcher: Matcher) -> str | None:
    snapshot = _get_snapshot()
    plugin = matcher.plugin
    while plugin is not None:
        if plugin.name in snapshot.managed:
            return plugin.name
        plugin = plugin.parent_plugin
    return None


def has_policy(plugin_name: str) -> bool:
    return plugin_name in _get_snapshot().policies


def is_enabled(
    plugin_name: str, *, scope: Literal["group", "private"], group_key: str | None,
) -> bool:
    snapshot = _get_snapshot()
    if plugin_name not in snapshot.managed:
        raise ValueError("plugin is not managed")
    if scope == "group":
        validate_group_key(group_key)
    elif scope == "private":
        if group_key is not None:
            raise ValueError("private scope requires group_key=None")
    else:
        raise ValueError("invalid scope")
    policy = snapshot.policies.get(plugin_name)
    if policy is None:
        return True
    if scope == "private":
        return policy.private_enabled
    return policy.groups.get(group_key, policy.default_enabled)
