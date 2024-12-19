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
from src.public.register import plugin_register

from .config import Config

__plugin_meta__ = PluginMetadata(
    name="插件管理",
    description="",
    usage="",
    config=Config,
)

config = get_plugin_config(Config)
neko_count = 0

check_enable = on_fullmatch("enako", priority=1, block=True)
echo_neko = on_message(priority=1, block=False)
plugin_list = on_command("help", priority=10, block=True)

@check_enable.handle()
async def check_enable_handler():
    try:
        await check_enable.finish("喵呜")
    except MatcherException:
        raise
    except Exception as e:
        pass
    
@echo_neko.handle()
async def echo_neko_handler(event: Event):
    if event.get_plaintext() == "喵呜":
        neko_count += 1
    else:
        neko_count = 0
    if neko_count == 2:
        neko_count = 0
        try:
            await echo_neko.finish("喵呜")
        except MatcherException:
            raise
        except Exception as e:
            pass

@plugin_list.handle()
async def get_plgin_list_handler():
    message = "\n可用的插件帮助：\n"
    for plugin in plugin_register.get_plugin_help_list():
        message += plugin.strip('\n') + "\n\n"
        
    message = message.strip('\n')
    try:
        await plugin_list.finish(message, at_sender=True)
    except MatcherException:
        raise
    except Exception as e:
        pass 
