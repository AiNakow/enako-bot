from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata
from nonebot.permission import SUPERUSER
from nonebot import on_command
from nonebot import on_fullmatch
from nonebot import on_message
from nonebot.rule import to_me
from nonebot.adapters import Message
from nonebot.adapters import Event
from nonebot.params import CommandArg
from nonebot.params import Depends
from nonebot.exception import MatcherException
from nonebot.adapters.onebot.v11 import MessageSegment
from nonebot import get_loaded_plugins
from nonebot import get_driver
from nonebot.drivers import Driver
from typing import Annotated

import random
from .register import plugin_register
from .config import Config
from .config import PLUGIN_ADMIN
from .common import *

__usage_help__ = """
/插件管理小助手
用于管理当前机器人的插件
/help
/list
/enable <插件名> （仅插件管理员）
/disable <插件名> （仅插件管理员）
"""

__plugin_meta__ = PluginMetadata(
    name="插件管理小助手",
    description="用于管理当前机器人的插件",
    usage=__usage_help__,
    config=Config,
)

config = get_plugin_config(Config)

driver = get_driver()

check_enable = on_fullmatch("enako", priority=1, block=True)
message_gateway = on_message(priority=1, block=False)
help_plugin = on_command("help", priority=10, block=True)
list_plugin = on_command("list", priority=10, block=True)
enable_plugin = on_command("enable", permission=PLUGIN_ADMIN, priority=10, block=True)
disable_plugin = on_command("disable", permission=PLUGIN_ADMIN, priority=10, block=True)

@driver.on_startup
async def on_startup():
    print("插件管理小助手启动")

@driver.on_shutdown
async def on_shutdown():
    print("插件管理小助手关闭")

@message_gateway.handle()
async def message_gateway_handler(event: Event):
    if event.message_type != "group":
        return
    if event.message_type == "group":
        print(event.message)

@check_enable.handle()
async def check_enable_handler():
    response = random.choice(RAND_RESPONSE)
    try:
        await check_enable.finish(response)
    except MatcherException:
        raise
    except Exception as e:
        pass

@help_plugin.handle()
async def get_plgin_list_handler():
    message = "可用的插件帮助：\n"
    for plugin in plugin_register.get_plugin_help_list():
        message += plugin.strip('\n') + "\n\n"
        
    message = message.strip('\n')
    try:
        await help_plugin.finish(message, at_sender=True)
    except MatcherException:
        raise
    except Exception as e:
        pass 

@list_plugin.handle()
async def list_plugin_handler():
    message = "当前已启用的插件：\n"
    for plugin in plugin_register.get_plugin_list():
        message += plugin.strip('\n') + "\n"
    message = message.strip('\n')
    await list_plugin.finish(message, at_sender=True)

@enable_plugin.handle()
async def enable_plugin_handler(args: Annotated[Message, CommandArg()]):
    plugin_name = args.extract_plain_text().strip()
    if not plugin_name:
        await enable_plugin.finish("请输入插件名")
    plugin_register.enable_plugin(plugin_name)
    await enable_plugin.finish(f"已启用插件：{plugin_name}")

@disable_plugin.handle()
async def disable_plugin_handler(args: Annotated[Message, CommandArg()]):
    plugin_name = args.extract_plain_text().strip()
    if not plugin_name:
        await disable_plugin.finish("请输入插件名")
    plugin_register.disable_plugin(plugin_name)
    await disable_plugin.finish(f"已禁用插件：{plugin_name}")
