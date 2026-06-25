from nonebot import get_plugin_config
from nonebot.rule import to_me
from nonebot.plugin import PluginMetadata
from nonebot.permission import SUPERUSER
from nonebot import on_command, require, on_fullmatch
from nonebot.adapters import Message
from nonebot.params import CommandArg
from nonebot.params import Depends
from nonebot.exception import MatcherException
from nonebot.adapters.qq import MessageSegment, MessageEvent
from nonebot.typing import T_State

require("nonebot_plugin_waiter")
from nonebot_plugin_waiter import waiter

from typing import Annotated
from .common import *
from .config import Config
from .service import MahjongService
from . import mahjong_analyzer
import os

__usage_help__ = """日麻小助手
请按照如下格式发送指令：
/面麻计分器
/牌理 <标准形/一般形> <天凤格式手牌>
/牌理 <天凤格式手牌>
/识图牌理 <标准形/一般形>
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

get_help = on_fullmatch("日麻小助手", priority=10, block=True)
get_mahjong_helper = on_command("面麻计分器", rule=to_me(), priority=10, block=True)
get_tenhou_paili = on_command("牌理", rule=to_me(), aliases={"天凤牌理"}, priority=10, block=True)
get_mahjong_ocr = on_command("识图牌理", rule=to_me(), priority=10, block=True)

@get_help.handle()
async def get_help_handler():
    await get_help.finish(__usage_help__, at_sender=True)

@get_mahjong_helper.handle()
async def get_mahjong_helper_handler():
    await get_mahjong_helper.finish("https://dev-soragoto.github.io/mahjong_helper", at_sender=True)

@get_tenhou_paili.handle()
async def get_tenhou_paili_handler(args: Annotated[Message, CommandArg()]):
    arg_text = args.extract_plain_text()
    if arg_text == "":
        await get_tenhou_paili.finish(__usage_help__, at_sender=True)

    arg_list = arg_text.split(' ')
    hand_str = arg_list[0]
    mode = 0

    if len(arg_list) > 1 and "一般" in arg_list[0]:
        hand_str = arg_list[1]
        mode = 1
        
    if not mahjong_analyzer.is_valid_handstr(hand_str):
        await get_tenhou_paili.finish("手牌不符合规则，请修改后重新发送", at_sender=True)
        
    pic = MahjongService.tenhou_paili_analyse(hand_str, mode)
    message = MessageSegment.file_image(data=pic)
        
    await get_tenhou_paili.finish(message=message, at_sender=True) 

@get_mahjong_ocr.handle()
async def mahjong_ocr_start(args: Annotated[Message, CommandArg()], state: T_State):
    arg_text = args.extract_plain_text().strip()
    arg_list = arg_text.split(' ')
    await get_mahjong_ocr.send("请发送要识别的图片。为了最佳识别效果，请将图片裁剪至仅有手牌区域。")

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

    hand = MahjongService.get_hand_from_image(url)
    mode = 0
    if len(arg_list) > 0 and "一般" in arg_list[0]:
        mode = 1

    pic = MahjongService.tenhou_paili_analyse(hand, mode)
    message = MessageSegment.file_image(data=pic)
    
    await get_mahjong_ocr.finish(message=message, at_sender=True)

