from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata
from nonebot.permission import SUPERUSER
from nonebot import on_command
from nonebot import on_fullmatch
from nonebot.rule import to_me
from nonebot.adapters import Message
from nonebot.params import CommandArg
from nonebot.params import Depends
from nonebot.exception import MatcherException
from nonebot.adapters.onebot.v11 import MessageSegment
from .register import plugin_register

from .config import Config

__plugin_meta__ = PluginMetadata(
    name="插件管理",
    description="",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)

check_enable = on_everyone_close = on_fullmatch("enako", priority=1, block=True)
plugin_list = on_command("插件列表", priority=10, block=True)

@check_enable.handle()
async def check_enable_handler():
    try:
        await check_enable.finish("喵呜", at_sender=True)
    except MatcherException:
        raise
    except Exception as e:
        pass

@plugin_list.handle()
async def get_plgin_list_handler():
    message = "可用的插件帮助：\n"
    for plugin in plugin_register.get_plugin_help_list():
        message += plugin + "\n"
        
    message = message.strip('\n')
    try:
        await plugin_list.finish(message, at_sender=True)
    except MatcherException:
        raise
    except Exception as e:
        pass 
