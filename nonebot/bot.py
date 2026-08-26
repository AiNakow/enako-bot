from __future__ import annotations

import pkgutil

import nonebot
from pydantic import BaseModel


class PluginLoadingConfig(BaseModel):
    enabled_plugins: set[str] | None = None


INFRASTRUCTURE_PLUGINS = {
    "_adapter": "src.infrastructure_plugins._adapter",
}


def _discover_plugins(plugin_dir: str) -> dict[str, str]:
    module_prefix = plugin_dir.replace("/", ".")
    return {
        module.name: f"{module_prefix}.{module.name}"
        for module in pkgutil.iter_modules([plugin_dir])
        if not module.name.startswith("_")
    }


def _load_infrastructure_plugins() -> None:
    for plugin_name, module_path in INFRASTRUCTURE_PLUGINS.items():
        if nonebot.load_plugin(module_path) is None:
            raise RuntimeError(
                f"Failed to load infrastructure plugin: {plugin_name}"
            )


def _load_configured_business_plugins(adapter: str) -> None:
    common_plugins = {
        "nonebot_plugin_htmlrender": "nonebot_plugin_htmlrender",
        **_discover_plugins("src/plugins"),
    }
    qq_plugins = _discover_plugins("src/qq_plugins")
    enabled_plugins = nonebot.get_plugin_config(
        PluginLoadingConfig
    ).enabled_plugins

    if enabled_plugins is not None:
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

    for plugin_name, module_path in available_plugins.items():
        if enabled_plugins is None or plugin_name in enabled_plugins:
            nonebot.load_plugin(module_path)


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

_load_infrastructure_plugins()
_load_configured_business_plugins(adapter)

if __name__ == "__main__":
    nonebot.run()
