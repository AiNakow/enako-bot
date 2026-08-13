# 标准库
import os
from typing import Annotated

# nonebot 核心
from nonebot import (
    get_plugin_config,
    on_command,
    on_fullmatch
)
from nonebot.adapters import Bot, Event, Message
from nonebot.exception import MatcherException
from nonebot.params import CommandArg, Depends
from nonebot.permission import SUPERUSER
from nonebot.plugin import PluginMetadata
from nonebot.log import logger

# 本地模块
from src.plugins._adapter.runtime import bridge
from .common import *
from .config import Config
from .service import GszService

__usage_help__ = """公式战小助手
用于查询用户的公式战信息
/公式战绑定 用户名
/吃鱼
/吃鱼 用户名
/吃鱼 @群友
/仇恨榜
/仇恨榜 用户名
/仇恨榜 @群友
/好人榜
/好人榜 用户名
/好人榜 @群友
/雀庄绑定 雀庄名称 （仅限群管理员）
/排行榜
"""

__plugin_meta__ = PluginMetadata(
    name="公式战小助手",
    description="用于查询用户的公式战信息",
    usage=__usage_help__,
    config=Config,
)

config = get_plugin_config(Config)

os.makedirs(data_dir, exist_ok=True)
os.makedirs(database_dir, exist_ok=True)

def get_at_list(event: Event) -> list[str]:
    """获取消息中所有@的QQ号列表"""
    return bridge.get_mentioned_user_ids(event)

def at(user_id: str):
    return bridge.mention_user(user_id)



gsz_help = on_fullmatch("公式战小助手", priority=10, block=True)
bind_gsz_userinfo = on_command(
    "公式战绑定",
    priority=10,
    block=True,
    state={"qq_command_panel": {"description": "绑定公式战账号"}},
)
get_gsz_userinfo = on_command(
    "吃鱼",
    priority=10,
    block=True,
    state={"qq_command_panel": {"description": "查询公式战信息"}},
)
get_gsz_rank_top = on_command(
    "仇恨榜",
    priority=10,
    block=True,
    state={"qq_command_panel": {"description": "查询仇恨榜"}},
)
get_gsz_rank_last = on_command(
    "好人榜",
    priority=10,
    block=True,
    state={"qq_command_panel": {"description": "查询好人榜"}},
)
bind_gsz_rateinfo = on_command(
    "雀庄绑定",
    priority=10,
    block=True,
    state={
        "qq_command_panel": {
            "description": "绑定本群雀庄",
            "only_admin": True,
            "scopes": ["group"],
        }
    },
)
get_gsz_rank_list = on_command(
    "排行榜",
    priority=10,
    block=True,
    state={
        "qq_command_panel": {
            "description": "查询雀庄排行榜",
            "scopes": ["group"],
        }
    },
)

@gsz_help.handle()
async def gsz_help_handler(event: Event, bot: Bot):
    await gsz_help.finish(__usage_help__)

@bind_gsz_userinfo.handle()
async def bind_gsz_userinfo_handler(args: Annotated[Message, CommandArg()], event: Event):
    arg_text = args.extract_plain_text()
    if arg_text == "":
        await bind_gsz_userinfo.finish(bridge.message_with_sender_mention(event, __usage_help__))

    username = arg_text
    if await GszService.bind_userinfo(uid=bridge.get_user_id(event), username=username):
        await bind_gsz_userinfo.finish(f"绑定成功，{username}的公式战信息已绑定到qq")
    else:
        await bind_gsz_userinfo.finish(bridge.message_with_sender_mention(event, "绑定失败，用户名可能不存在，请检查是否输入有误"))

@get_gsz_userinfo.handle()
async def get_gsz_userinfo_handler(args: Annotated[Message, CommandArg()], event: Event):
    if bridge.is_group_event(event) and len(get_at_list(event)) > 1:
        at_list = get_at_list(event)
        logger.warning(f"[diag] /吃鱼@ at_list={at_list} sender_uid={bridge.get_user_id(event)}")
        username = await GszService.get_userinfo_by_uid(uid=at_list[1])
        if username is None:
            await get_gsz_userinfo.finish(bridge.message_with_sender_mention(event, "该用户未绑定公式战信息！"))
    else:
        arg_text = args.extract_plain_text().strip()
        arg_list = arg_text.split(' ')
        if arg_text == "":
            username = await GszService.get_userinfo_by_uid(uid=bridge.get_user_id(event))
            if username is None:
                await get_gsz_userinfo.finish(bridge.message_with_sender_mention(event, "未绑定公式战信息，请使用\n/公式战绑定 用户名\n绑定公式战信息"))
        else:
            username = arg_list[0]
    await get_gsz_userinfo.send(bridge.message_with_sender_mention(event, f"正在获取{username}的公式战信息，请稍等..."))

    try:
        pic = await GszService.get_userinfo_by_name(username)
    except Exception as e:
        await get_gsz_userinfo.finish(bridge.message_with_sender_mention(event, f"获取{username}的公式战信息失败，请检查是否输入有误"))

    message = bridge.image_from_bytes(pic)

    await get_gsz_userinfo.finish(message=bridge.message_with_sender_mention(event, message))

@get_gsz_rank_top.handle()
async def get_gsz_rank_top_handler(args: Annotated[Message, CommandArg()], event: Event):
    if bridge.is_group_event(event) and len(get_at_list(event)) > 1:
        at_list = get_at_list(event)
        username = await GszService.get_userinfo_by_uid(uid=at_list[1])
        if username is None:
            await get_gsz_rank_top.finish(bridge.message_with_sender_mention(event, "该用户未绑定公式战信息！"))
    else:
        arg_text = args.extract_plain_text()
        arg_list = arg_text.split(' ')
        if arg_text == "":
            username = await GszService.get_userinfo_by_uid(uid=bridge.get_user_id(event))
            if username is None:
                await get_gsz_rank_top.finish(bridge.message_with_sender_mention(event, "未绑定公式战信息，请使用\n/公式战绑定 用户名\n绑定公式战信息"))
        else:
            username = arg_list[0]

    await get_gsz_rank_top.send(bridge.message_with_sender_mention(event, f"正在获取{username}的仇恨榜信息，请稍等..."))

    try:
        pic = await GszService.get_rank_top(username)
    except Exception as e:
        await get_gsz_rank_top.finish(bridge.message_with_sender_mention(event, f"获取{username}的仇恨榜失败，请检查是否输入有误"))

    message = bridge.image_from_bytes(pic)

    await get_gsz_rank_top.finish(message=bridge.message_with_sender_mention(event, message))


@get_gsz_rank_last.handle()
async def get_gsz_rank_last_handler(args: Annotated[Message, CommandArg()], event: Event):
    if bridge.is_group_event(event) and len(get_at_list(event)) > 1:
        at_list = get_at_list(event)
        username = await GszService.get_userinfo_by_uid(uid=at_list[1])
        if username is None:
            await get_gsz_rank_last.finish(bridge.message_with_sender_mention(event, "该用户未绑定公式战信息！"))
    else:
        arg_text = args.extract_plain_text()
        arg_list = arg_text.split(' ')
        if arg_text == "":
            username = await GszService.get_userinfo_by_uid(uid=bridge.get_user_id(event))
            if username is None:
                await get_gsz_rank_last.finish(bridge.message_with_sender_mention(event, "未绑定公式战信息，请使用\n/公式战绑定 用户名\n绑定公式战信息"))
        else:
            username = arg_list[0]
    await get_gsz_rank_last.send(bridge.message_with_sender_mention(event, f"正在获取{username}的好人榜信息，请稍等..."))

    try:
        pic = await GszService.get_rank_last(username)
    except Exception as e:
        await get_gsz_rank_last.finish(bridge.message_with_sender_mention(event, f"获取{username}的好人榜失败，请检查是否输入有误"))

    message = bridge.image_from_bytes(pic)

    await get_gsz_rank_last.finish(message=bridge.message_with_sender_mention(event, message))

@bind_gsz_rateinfo.handle()
async def bind_gsz_rateinfo_handler(args: Annotated[Message, CommandArg()], event: Event):
    arg_text = args.extract_plain_text()
    if arg_text == "":
        await bind_gsz_rateinfo.finish(bridge.message_with_sender_mention(event, __usage_help__))
    
    group_id = bridge.get_group_id(event)
    if group_id is None:
        await bind_gsz_rateinfo.finish(bridge.message_with_sender_mention(event, "该命令只能在群聊中使用"))

    if not bridge.is_group_admin_or_owner(event):
        return

    rate_name = arg_text
    if await GszService.bind_rateinfo(group_id=group_id, rate_name=rate_name):
        await bind_gsz_rateinfo.finish(bridge.message_with_sender_mention(event, f"绑定成功，{rate_name}的雀庄信息已绑定到群聊"))
    else:
        await bind_gsz_rateinfo.finish(bridge.message_with_sender_mention(event, "绑定失败，雀庄名称可能不存在，请检查是否输入有误"))
        
@get_gsz_rank_list.handle()
async def get_gsz_rank_list_handler(event: Event):
    group_id = bridge.get_group_id(event)
    if group_id is None:
        return
    rateinfo = await GszService.get_rateinfo_by_group_id(group_id=group_id)

    if rateinfo is None:
        await get_gsz_rank_list.finish(bridge.message_with_sender_mention(event, "未绑定雀庄信息，请群管使用\n/雀庄绑定 雀庄名称\n绑定雀庄信息"))

    rate_id = rateinfo["rateId"]
    rate_name = rateinfo["rateName"]
    await get_gsz_rank_list.send(bridge.message_with_sender_mention(event, f"正在获取{rate_name}的排行榜，请稍等..."))

    try:
        pic = await GszService.get_rank_list(rate_id=rate_id)
    except Exception as e:
        await get_gsz_rank_list.finish(bridge.message_with_sender_mention(event, "获取排行榜失败，可能是网络波动，请稍后再试"))
    
    message = bridge.image_from_bytes(pic)

    await get_gsz_rank_list.finish(message=bridge.message_with_sender_mention(event, message))
