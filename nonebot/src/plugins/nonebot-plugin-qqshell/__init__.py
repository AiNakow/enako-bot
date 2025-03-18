from nonebot import require
require("nonebot_plugin_htmlrender")

from nonebot.plugin import PluginMetadata

from .config import Config
from .handler import shell_handler

__plugin_meta__ = PluginMetadata(
    name="shell",
    description="shell",
    usage=">shell <你的指令>",
    config=Config,
    homepage="",
    type="application",
    supported_adapters={"~onebot.v11"}
)