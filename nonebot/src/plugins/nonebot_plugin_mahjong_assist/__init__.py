from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata
from nonebot.permission import SUPERUSER
from nonebot import on_command
from nonebot.rule import to_me
from nonebot.adapters import Message
from nonebot.params import CommandArg
from nonebot.params import Depends
from nonebot.exception import MatcherException

from .config import Config

__plugin_meta__ = PluginMetadata(
    name="nonebot-plugin-mahjong_helper",
    description="日麻小助手",
    usage=(
        "/面麻计分器"
        ),
    config=Config,
)

__usage_help__ = """
日麻小助手
请按照如下格式发送指令：
/面麻计分器
"""

config = get_plugin_config(Config)

get_help = on_command("日麻小助手", rule=to_me(), priority=10, block=True)
get_mahjong_helper = on_command("面麻计分器", rule=to_me(), priority=10, block=True)

@get_help.handle()
async def get_help_handle():
    try:
        await get_help.finish(__usage_help__, at_sender=True)
    except MatcherException:
        raise
    except Exception as e:
        pass 

@get_mahjong_helper.handle()
async def get_mahjong_helper_handle():
    try:
        await get_help.finish("https://dev-soragoto.github.io/mahjong_helper", at_sender=True)
    except MatcherException:
        raise
    except Exception as e:
        pass 




