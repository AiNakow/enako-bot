import os

from nonebot import get_driver

from .base import AdapterBridge


def _load_bridge() -> AdapterBridge:
    config_adapter = None
    env_adapter = os.getenv("BOT_ADAPTER")

    if env_adapter is None:
        try:
            config_adapter = getattr(get_driver().config, "bot_adapter", None)
        except ValueError:
            config_adapter = None

    adapter = (env_adapter or config_adapter or "qq").lower()

    if adapter == "qq":
        from .qq import bridge

        return bridge
    if adapter in {"onebot11", "onebot-v11", "onebot_v11"}:
        from .onebot11 import bridge

        return bridge

    raise RuntimeError(f"Unsupported BOT_ADAPTER: {adapter}")


bridge = _load_bridge()
