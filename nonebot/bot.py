import nonebot


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

nonebot.load_plugin("nonebot_plugin_htmlrender")  # 第三方插件
nonebot.load_plugins("src/plugins")  # 本地插件

if __name__ == "__main__":
    nonebot.run()
