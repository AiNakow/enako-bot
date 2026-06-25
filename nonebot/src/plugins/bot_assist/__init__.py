import random
from nonebot import (
    get_plugin_config,
    on_fullmatch,
)

from nonebot.plugin import PluginMetadata

from .common import *
from .config import Config

__usage_help__ = """
机器人小助手
用于管理当前机器人的插件
"""

__plugin_meta__ = PluginMetadata(
    name=manager_name,
    description="用于管理当前机器人的插件",
    usage=__usage_help__,
    config=Config,
)

config = get_plugin_config(Config)

check_enable = on_fullmatch("enako", priority=1, block=True)

@check_enable.handle()
async def check_enable_handler():
    response = random.choice(RAND_RESPONSE)
    await check_enable.finish(response)