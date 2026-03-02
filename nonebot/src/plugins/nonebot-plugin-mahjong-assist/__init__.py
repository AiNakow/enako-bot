from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata
from nonebot.permission import SUPERUSER
from nonebot import on_command, require
from nonebot.adapters import Message
from nonebot.params import CommandArg
from nonebot.params import Depends
from nonebot.exception import MatcherException
from nonebot.adapters.onebot.v11 import MessageSegment, MessageEvent
from nonebot.typing import T_State

require("nonebot_plugin_waiter")
from nonebot_plugin_waiter import waiter

from typing import Annotated
from .common import *
from .config import Config
from .service import MahjongService
import os

__usage_help__ = """
/日麻小助手
请按照如下格式发送指令：
/面麻计分器
/天凤牌理 <标准形/一般形> <天凤格式手牌>
/天凤牌理 <天凤格式手牌>
/识图 牌理 <标准形/一般形>
"""

__plugin_meta__ = PluginMetadata(
    name="日麻小助手",
    description="日麻小助手，提供一些日麻常用小工具",
    usage=(
        __usage_help__
        ),
    config=Config,
)

if not os.path.exists(model_dir):
    os.mkdir(model_dir)

if not os.path.exists(data_dir):
    os.mkdir(data_dir)

get_help = on_command("日麻小助手", priority=10, block=True)
get_mahjong_helper = on_command("面麻计分器", priority=10, block=True)
get_tenhou_paili = on_command("天凤牌理", priority=10, block=True)
get_mahjong_ocr = on_command("识图", priority=10, block=True)

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

@get_mahjong_ocr.handle()
async def mahjong_ocr_start(args: Annotated[Message, CommandArg()], state: T_State):
    arg_text = args.extract_plain_text().strip()
    arg_list = arg_text.split(' ')
    if arg_text == "" or len(arg_list) == 0:
        await get_mahjong_ocr.finish(__usage_help__, at_sender=True)
    if arg_list[0] == "牌理":
        await get_mahjong_ocr.send("请发送要识别的图片。为了最佳识别效果，请将图片裁剪至仅有手牌区域。")
    else: 
        await get_mahjong_ocr.finish(__usage_help__, at_sender=True)

    @waiter(waits=["message"], keep_session=True)
    async def get_image(event: MessageEvent):
        return event
    
    resp = await get_image.wait(timeout=60)

    if resp is None:
        await get_mahjong_ocr.finish("等待超时，操作已取消", at_sender=True)

    msg = resp.get_message()
    image_segs = msg["image"]

    if not image_segs:
        await get_mahjong_ocr.finish("未收到图片，已取消操作", at_sender=True)

    url = image_segs[0].data["url"]
    await get_mahjong_ocr.send("推理中...")

    if arg_list[0] == "牌理":
        hand = MahjongService.get_hand_from_image(url)
        analyse_type = 'q'
        if len(arg_list) > 1 and "一般" in arg_list[1]:
            analyse_type = 'p'

        pic = MahjongService.tenhou_paili_analyse(analyse_type, hand)
        message = MessageSegment.image(file=pic)
        
        await get_mahjong_ocr.finish(message=message, at_sender=True)

