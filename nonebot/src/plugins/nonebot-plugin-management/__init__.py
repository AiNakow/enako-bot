# 标准库
import random
from typing import Annotated

# nonebot 核心
from nonebot import (
    get_driver,
    get_loaded_plugins,
    get_plugin,
    get_plugin_config,
    on_command,
    on_fullmatch,
    on_message,
)
from nonebot.adapters import Event, Message
from nonebot.adapters.onebot.v11 import GroupMessageEvent, MessageEvent, MessageSegment
from nonebot.drivers import Driver
from nonebot.exception import IgnoredException, MatcherException
from nonebot.log import logger
from nonebot.matcher import Matcher
from nonebot.message import run_preprocessor
from nonebot.params import CommandArg, Depends
from nonebot.permission import SUPERUSER
from nonebot.plugin import Plugin, PluginMetadata
from nonebot.rule import to_me

# 本地模块
from .common import *
from .config import Config, PLUGIN_ADMIN
from .register import plugin_register

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
help_plugin = on_command("help", priority=10, block=True)
list_plugin = on_command("list", priority=10, block=True)
enable_plugin = on_command("启用", priority=10, block=True)
disable_plugin = on_command("禁用", priority=10, block=True)

def get_group_id(event: GroupMessageEvent):
    return str(event.group_id)

@driver.on_startup
async def on_startup():
    plugins: set[Plugin] = get_loaded_plugins()
    for plugin in plugins:
        plugin_register.register(plugin)

@driver.on_shutdown
async def on_shutdown():
    pass

@run_preprocessor
async def messageEvent_preprocessor(event: GroupMessageEvent, matcher: Matcher):
    plugin_name = get_plugin(matcher.plugin_name).metadata.name
    if plugin_register.if_plugin_disable(plugin_name, get_group_id(event)):
        logger.info(f"插件 {plugin_name} 已在群 {get_group_id(event)} 被禁用")
        raise IgnoredException(f"插件 {plugin_name} 已在群 {get_group_id(event)} 被禁用")

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
async def get_plgin_list_handler(event: GroupMessageEvent):
    message = "可用的插件帮助：\n"
    for plugin in plugin_register.get_plugin_help_list(get_group_id(event)):
        message += plugin.strip('\n') + "\n\n"
        
    message = message.strip('\n')
    try:
        await help_plugin.finish(message, at_sender=True)
    except MatcherException:
        raise
    except Exception as e:
        pass 

@list_plugin.handle()
async def list_plugin_handler(event: GroupMessageEvent):

    message = "当前已启用的插件：\n"
    for plugin in plugin_register.get_plugin_list(get_group_id(event))["enable"]:
        message += plugin.strip('\n') + "\n"
    message += "\n当前已禁用的插件：\n"
    for plugin in plugin_register.get_plugin_list(get_group_id(event))["disable"]:
        message += plugin.strip('\n') + "\n"
    message = message.strip('\n')
    await list_plugin.finish(message, at_sender=True)

@enable_plugin.handle()
async def enable_plugin_handler(args: Annotated[Message, CommandArg()], event: GroupMessageEvent):
    if event.sender.role not in ["admin", "owner"] and not PLUGIN_ADMIN(event):
        await enable_plugin.finish("您没有权限执行该指令", at_sender=True)

    plugin_name = args.extract_plain_text().strip()
    if not plugin_name:
        await enable_plugin.finish("请输入插件名", at_sender=True)
    plugin_register.enable_plugin(plugin_name, get_group_id(event))
    await enable_plugin.finish(f"已启用插件：{plugin_name}", at_sender=True)

@disable_plugin.handle()
async def disable_plugin_handler(args: Annotated[Message, CommandArg()], event: GroupMessageEvent):
    if event.sender.role not in ["admin", "owner"] and not PLUGIN_ADMIN(event):
        await disable_plugin.finish("您没有权限执行该指令", at_sender=True)

    plugin_name = args.extract_plain_text().strip()
    if not plugin_name:
        await disable_plugin.finish("请输入插件名", at_sender=True)
    plugin_register.disable_plugin(plugin_name, get_group_id(event))
    await disable_plugin.finish(f"已禁用插件：{plugin_name}", at_sender=True)
