from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata
from nonebot.permission import SUPERUSER
from nonebot import on_command
from nonebot.adapters import Message
from nonebot.params import CommandArg
from nonebot.params import Depends
from nonebot.exception import MatcherException
from nonebot.adapters.onebot.v11 import MessageSegment

from src.public.register import plugin_register
from typing import Annotated
from .config import Config
from .service import MahjongService

__usage_help__ = """
/日麻小助手
请按照如下格式发送指令：
/面麻计分器
/天凤牌理 <标准形/一般形> <天凤格式手牌>
/天凤牌理 <天凤格式手牌>
/吃鱼 <公式站昵称>
"""

__plugin_meta__ = PluginMetadata(
    name="nonebot-plugin-mahjong_assist",
    description="日麻小助手",
    usage=(
        __usage_help__
        ),
    config=Config,
)

plugin_register.register(__usage_help__)
config = get_plugin_config(Config)

get_help = on_command("日麻小助手", priority=10, block=True)
get_mahjong_helper = on_command("面麻计分器", priority=10, block=True)
get_tenhou_paili = on_command("天凤牌理", priority=10, block=True)
get_gsz_userinfo = on_command("吃鱼", priority=10, block=True)

@get_help.handle()
async def get_help_handler():
    try:
        await get_help.finish(__usage_help__, at_sender=True)
    except MatcherException:
        raise
    except Exception as e:
        pass 

@get_mahjong_helper.handle()
async def get_mahjong_helper_handler():
    try:
        await get_mahjong_helper.finish("https://dev-soragoto.github.io/mahjong_helper", at_sender=True)
    except MatcherException:
        raise
    except Exception as e:
        pass 

@get_tenhou_paili.handle()
async def get_tenhou_paili_handler(args: Annotated[Message, CommandArg()]):
    arg_text = args.extract_plain_text()
    if arg_text == "":
        try:
            await get_tenhou_paili.finish(__usage_help__, at_sender=True)
        except MatcherException:
            raise
        except Exception as e:
            pass 
    arg_list = arg_text.split(' ')
    analyse_type = 'q'
    if len(arg_list) == 1 and "标准" not in arg_list[0] and "一般" not in arg_list[0]:
        pic = MahjongService.tenhou_paili_analyse(analyse_type, arg_list[0])
    elif len(arg_list) > 1:
        if "一般" in arg_list[0]:
            analyse_type = 'p'
        pic = MahjongService.tenhou_paili_analyse(analyse_type, arg_list[1])
    else:
        try:
            await get_tenhou_paili.finish(__usage_help__, at_sender=True)
        except MatcherException:
            raise
        except Exception as e:
            pass 
    message = MessageSegment.image(file=pic)
        
    # run 1008.js to get result
    try:
        await get_tenhou_paili.finish(message=message, at_sender=True)
    except MatcherException:
        raise
    except Exception as e:
        pass 

@get_gsz_userinfo.handle()
async def get_gsz_userinfo_handler(args: Annotated[Message, CommandArg()]):
    arg_text = args.extract_plain_text()
    if arg_text == "":
        try:
            await get_gsz_userinfo.finish(__usage_help__, at_sender=True)
        except MatcherException:
            raise
        except Exception as e:
            pass
    
    arg_list = arg_text.split(' ')
    username = arg_list[0]
    pic = MahjongService.gsz_userinfo_get(username)
    message = MessageSegment.image(file=pic)
    
    try:
        await get_gsz_userinfo.finish(message=message, at_sender=True)
    except MatcherException:
        raise
    except Exception as e:
        pass