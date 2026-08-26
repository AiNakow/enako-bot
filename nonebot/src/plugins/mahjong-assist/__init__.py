from nonebot.plugin import PluginMetadata
from nonebot.permission import SUPERUSER
from nonebot import on_command, require, on_fullmatch
from nonebot.adapters import Event, Message
from nonebot.params import CommandArg
from nonebot.params import Depends
from nonebot.exception import MatcherException
from nonebot.typing import T_State

require("nonebot_plugin_waiter")
from nonebot_plugin_waiter import waiter

from typing import Annotated
from src.infrastructure_plugins._adapter import bridge
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
get_mahjong_helper = on_command(
    "面麻计分器",
    priority=10,
    block=True,
    state={"qq_command_panel": {"description": "获取面麻计分器"}},
)
get_tenhou_paili = on_command(
    "牌理",
    aliases={"天凤牌理"},
    priority=10,
    block=True,
    state={
        "qq_command_panel": {
            "name": "牌理",
            "description": "分析牌理",
        }
    },
)
get_mahjong_ocr = on_command(
    "识图牌理",
    priority=10,
    block=True,
    state={"qq_command_panel": {"description": "识别手牌并分析牌理"}},
)


@get_help.handle()
async def get_help_handler(event: Event):
    await get_help.finish(bridge.message_with_sender_mention(event, __usage_help__))

@get_mahjong_helper.handle()
async def get_mahjong_helper_handler(event: Event):
    await get_mahjong_helper.finish(bridge.message_with_sender_mention(event, "https://dev-soragoto.github.io/mahjong_helper"))

@get_tenhou_paili.handle()
async def get_tenhou_paili_handler(args: Annotated[Message, CommandArg()], event: Event):
    arg_text = args.extract_plain_text()
    if arg_text == "":
        await get_tenhou_paili.finish(bridge.message_with_sender_mention(event, __usage_help__))

    arg_list = arg_text.split(' ')
    hand_str = arg_list[0]
    mode = 0

    if len(arg_list) > 1 and "一般" in arg_list[0]:
        hand_str = arg_list[1]
        mode = 1

    if not mahjong_analyzer.is_valid_handstr(hand_str):
        await get_tenhou_paili.finish(bridge.message_with_sender_mention(event, "手牌不符合规则，请修改后重新发送"))

    pic = await MahjongService.tenhou_paili_analyse(hand_str, mode)
    message = bridge.image_from_bytes(pic)

    await get_tenhou_paili.finish(message=bridge.message_with_sender_mention(event, message))

@get_mahjong_ocr.handle()
async def mahjong_ocr_start(args: Annotated[Message, CommandArg()], state: T_State, event: Event):
    arg_text = args.extract_plain_text().strip()
    arg_list = arg_text.split(' ')
    await get_mahjong_ocr.send("请发送要识别的图片。为了最佳识别效果，请将图片裁剪至仅有手牌区域。")

    @waiter(waits=["message"], keep_session=True)
    async def get_image(event: Event):
        return event

    resp = await get_image.wait(timeout=60)

    if resp is None:
        await get_mahjong_ocr.finish(bridge.message_with_sender_mention(event, "等待超时，操作已取消"))

    url = bridge.extract_first_image_url(resp.get_message())

    if url is None:
        await get_mahjong_ocr.finish(bridge.message_with_sender_mention(event, "未收到图片，已取消操作"))

    await get_mahjong_ocr.send("推理中...")

    hand = MahjongService.get_hand_from_image(url)
    mode = 0
    if len(arg_list) > 0 and "一般" in arg_list[0]:
        mode = 1

    if not mahjong_analyzer.is_valid_handstr(hand):
        await get_tenhou_paili.finish(bridge.message_with_sender_mention(event, "未识别到长度符合规则的手牌"))

    pic = await MahjongService.tenhou_paili_analyse(hand, mode)
    message = bridge.image_from_bytes(pic)

    await get_mahjong_ocr.finish(message=bridge.message_with_sender_mention(event, message))
