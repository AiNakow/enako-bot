import nonebot
from nonebot.adapters.qq import Adapter as QQAdapter



nonebot.init()

driver = nonebot.get_driver()
driver.register_adapter(QQAdapter)


nonebot.load_plugin("nonebot_plugin_htmlrender")  # 第三方插件
nonebot.load_plugins("src/plugins")  # 本地插件

if __name__ == "__main__":
    nonebot.run()