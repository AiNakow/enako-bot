from nonebot import require
require("nonebot_plugin_htmlrender")

from nonebot.plugin import PluginMetadata

from .config import Config
from .handler import *
from .handler import __usage_help__

__plugin_meta__ = PluginMetadata(
    name="qqshell`",
    description="qqshell",
    usage=__usage_help__,
    config=Config,
    homepage="",
    type="application",
    supported_adapters={"~onebot.v11"}
)