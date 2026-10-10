from __future__ import annotations

import pkgutil

import nonebot
from pydantic import BaseModel


class PluginLoadingConfig(BaseModel):
    enabled_plugins: set[str] | None = None


INFRASTRUCTURE_PLUGINS = {
    "_adapter": "src.infrastructure_plugins._adapter",
    "group_config": "src.infrastructure_plugins.group_config",
}

QQ_INFRASTRUCTURE_PLUGINS = {
    "qq_command_panel": "src.infrastructure_plugins.qq_command_panel",
}

def _discover_plugins(plugin_dir: str) -> dict[str, str]:
    module_prefix = plugin_dir.replace("/", ".")
    return {
        module.name: f"{module_prefix}.{module.name}"
        for module in pkgutil.iter_modules([plugin_dir])
        if not module.name.startswith("_")
    }


def _load_infrastructure_plugins(adapter: str) -> None:
    plugins = dict(INFRASTRUCTURE_PLUGINS)

    if adapter == "qq":
        plugins.update(QQ_INFRASTRUCTURE_PLUGINS)

    for plugin_name, module_path in plugins.items():
        if nonebot.load_plugin(module_path) is None:
            raise RuntimeError(
                f"Failed to load infrastructure plugin: {plugin_name}"
            )


def _load_configured_business_plugins(adapter: str) -> None:
    from src.infrastructure_plugins.group_config import initialize_group_config

    local_common_plugins = _discover_plugins("src/plugins")
    common_plugins = {
        "nonebot_plugin_htmlrender": "nonebot_plugin_htmlrender",
        **local_common_plugins,
    }
    qq_plugins = _discover_plugins("src/qq_plugins")
    enabled_plugins = nonebot.get_plugin_config(
        PluginLoadingConfig
    ).enabled_plugins

    if enabled_plugins is not None:
        if "group_config" in enabled_plugins:
            raise RuntimeError("group_config cannot be selected in ENABLED_PLUGINS")
        unknown_plugins = (
            enabled_plugins
            - INFRASTRUCTURE_PLUGINS.keys()
            - common_plugins.keys()
            - qq_plugins.keys()
        )
        if unknown_plugins:
            names = ", ".join(sorted(unknown_plugins))
            raise RuntimeError(f"Unknown ENABLED_PLUGINS: {names}")

    available_plugins = dict(common_plugins)
    if adapter == "qq":
        available_plugins.update(qq_plugins)

    selected_plugins = {
        name: path for name, path in available_plugins.items()
        if enabled_plugins is None or name in enabled_plugins
    }
    known_business_plugins = frozenset(local_common_plugins.keys() | qq_plugins.keys())
    initialize_group_config(
        known_business_plugins=known_business_plugins,
        managed_business_plugins=frozenset(selected_plugins.keys() & known_business_plugins),
    )
    for plugin_name, module_path in selected_plugins.items():
        if nonebot.load_plugin(module_path) is None:
            raise RuntimeError(f"Failed to load selected plugin: {plugin_name}")


nonebot.init()

driver = nonebot.get_driver()

adapter = getattr(driver.config, "bot_adapter", "qq").lower()

if adapter == "qq":
    from src.qq_adapter import RawPayloadLoggingQQAdapter

    driver.register_adapter(RawPayloadLoggingQQAdapter)
elif adapter in {"onebot11", "onebot-v11", "onebot_v11"}:
    from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter

    driver.register_adapter(OneBotV11Adapter)
else:
    raise RuntimeError(f"Unsupported BOT_ADAPTER: {adapter}")

_load_infrastructure_plugins(adapter)
_load_configured_business_plugins(adapter)

if __name__ == "__main__":
    nonebot.run()
