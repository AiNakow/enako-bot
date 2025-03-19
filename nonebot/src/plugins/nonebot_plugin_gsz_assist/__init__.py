from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata
from nonebot.permission import SUPERUSER
from nonebot import on_command
from nonebot.adapters import Message
from nonebot.params import CommandArg
from nonebot.params import Depends
from nonebot.exception import MatcherException
from nonebot.adapters.onebot.v11 import MessageSegment
from nonebot.adapters import Event, Message, Bot

from typing import Annotated

from src.public.register import plugin_register
from .config import Config
from .service import GszService
from .common import *
__usage_help__ = """
/公式战小助手
用于查询用户的公式战信息
/公式战绑定 <用户名>
/吃鱼
/吃鱼 @群友
/吃鱼 <用户名>
/仇恨榜
/仇恨榜 @群友
/仇恨榜 <用户名>
/好人榜
/好人榜 @群友
/好人榜 <用户名>
"""

__plugin_meta__ = PluginMetadata(
    name="nonebot-plugin-gsz-assist",
    description="用于查询用户的公式战信息",
    usage=__usage_help__,
    config=Config,
)

plugin_register.register(__usage_help__)
config = get_plugin_config(Config)

if not os.path.exists(data_dir):
    os.mkdir(data_dir)
if not os.path.exists(database_dir):
    os.mkdir(database_dir)

def get_at_list(message: Message) -> list[str]:
    """获取消息中所有@的QQ号列表"""
    return [segment.data["qq"] for segment in message if segment.type == "at"]


gsz_help = on_command("公式战小助手", priority=10, block=True)
bind_gsz_userinfo = on_command("公式战绑定", priority=10, block=True)
get_gsz_userinfo = on_command("吃鱼", priority=10, block=True)
get_gsz_rank_top = on_command("仇恨榜", priority=10, block=True)
get_gsz_rank_last = on_command("好人榜", priority=10, block=True)

@gsz_help.handle()
async def gsz_help_handler(event: Event):
    try:
        await gsz_help.finish(__usage_help__, at_sender=True)
    except MatcherException:
        raise
    except Exception as e:
        pass

@bind_gsz_userinfo.handle()
async def bind_gsz_userinfo_handler(args: Annotated[Message, CommandArg()], event: Event):
    arg_text = args.extract_plain_text()
    if arg_text == "":
        try:
            await bind_gsz_userinfo.finish(__usage_help__, at_sender=True)
        except MatcherException:
            raise
    username = arg_text
    if GszService.bind_userinfo(uid=event.get_user_id(), username=username):
        await bind_gsz_userinfo.finish(f"绑定成功，{username}的公式战信息已绑定到{event.get_user_id()}", at_sender=True)
    else:
        await bind_gsz_userinfo.finish(f"绑定失败", at_sender=True)

@get_gsz_userinfo.handle()
async def get_gsz_userinfo_handler(args: Annotated[Message, CommandArg()], event: Event):
    if event.message_type == "group" and get_at_list(event.message) != []:
        at_list = get_at_list(event.message)
        username = GszService.get_userinfo_by_uid(uid=at_list[0])
        if username is None:
            try:
                await get_gsz_userinfo.finish(f"该用户未绑定公式战信息！", at_sender=True)
            except MatcherException:
                raise
            except Exception as e:
                pass
            return
    else:
        arg_text = args.extract_plain_text()
        arg_list = arg_text.split(' ')
        if arg_text == "":
            username = GszService.get_userinfo_by_uid(uid=event.get_user_id())
            if username is None:
                try:
                    await get_gsz_userinfo.finish(f"未绑定公式战信息，请使用\n/公式战绑定 <用户名>\n绑定公式战信息", at_sender=True)
                except MatcherException:
                    raise
                except Exception as e:
                    pass
                return
        else:
            username = arg_list[0]
    try:
        await get_gsz_userinfo.send(f"正在获取{username}的吃鱼信息，请稍等...", at_sender=True)
    except MatcherException:
        raise
    except Exception as e:
        pass

    try:
        pic = GszService.get_userinfo_by_name(username)
    except Exception as e:
        try:
            await get_gsz_userinfo.finish(f"获取{username}的吃鱼信息失败，请检查是否输入有误", at_sender=True)
        except MatcherException:
            raise
        except Exception as e:
            pass
        return

    message = MessageSegment.image(file=pic)
    
    try:
        await get_gsz_userinfo.finish(message=message, at_sender=True)
    except MatcherException:
        raise
    except Exception as e:
        pass

@get_gsz_rank_top.handle()
async def get_gsz_rank_top_handler(args: Annotated[Message, CommandArg()], event: Event):
    if event.message_type == "group" and get_at_list(event.message) != []:
        at_list = get_at_list(event.message)
        username = GszService.get_userinfo_by_uid(uid=at_list[0])
        if username is None:
            try:
                await get_gsz_rank_top.finish(f"该用户未绑定公式战信息！", at_sender=True)
            except MatcherException:
                raise
            except Exception as e:
                pass
            return
    else:
        arg_text = args.extract_plain_text()
        arg_list = arg_text.split(' ')
        if arg_text == "":
            username = GszService.get_userinfo_by_uid(uid=event.get_user_id())
            if username is None:
                try:
                    await get_gsz_rank_top.finish(f"未绑定公式战信息，请使用\n/公式战绑定 <用户名>\n绑定公式战信息", at_sender=True)
                except MatcherException:
                    raise
                except Exception as e:
                    pass
                return
        else:
            username = arg_list[0]
    try:
        await get_gsz_rank_top.send(f"正在获取{username}的仇恨榜信息，请稍等...", at_sender=True)
    except MatcherException:
        raise
    except Exception as e:
        pass

    try:
        pic = GszService.get_rank_top(username)
    except Exception as e:
        try:
            await get_gsz_rank_top.finish(f"获取{username}的仇恨榜失败，请检查是否输入有误", at_sender=True)
        except MatcherException:
            raise
        except Exception as e:
            pass
        return

    message = MessageSegment.image(file=pic)
    
    try:
        await get_gsz_rank_top.finish(message=message, at_sender=True)
    except MatcherException:
        raise
    except Exception as e:
        pass

@get_gsz_rank_last.handle()
async def get_gsz_rank_last_handler(args: Annotated[Message, CommandArg()], event: Event):
    if event.message_type == "group" and get_at_list(event.message) != []:
        at_list = get_at_list(event.message)
        username = GszService.get_userinfo_by_uid(uid=at_list[0])
        if username is None:
            try:
                await get_gsz_rank_last.finish(f"该用户未绑定公式战信息！", at_sender=True)
            except MatcherException:
                raise
            except Exception as e:
                pass
            return
    else:
        arg_text = args.extract_plain_text()
        arg_list = arg_text.split(' ')
        if arg_text == "":
            username = GszService.get_userinfo_by_uid(uid=event.get_user_id())
            if username is None:
                try:
                    await get_gsz_rank_last.finish(f"未绑定公式战信息，请使用\n/公式战绑定 <用户名>\n绑定公式战信息", at_sender=True)
                except MatcherException:
                    raise
                except Exception as e:
                    pass
                return
        else:
            username = arg_list[0]
    try:
        await get_gsz_rank_last.send(f"正在获取{username}的好人榜信息，请稍等...", at_sender=True)
    except MatcherException:
        raise
    except Exception as e:
        pass

    try:
        pic = GszService.get_rank_last(username)
    except Exception as e:
        try:
            await get_gsz_rank_last.finish(f"获取{username}的好人榜失败，请检查是否输入有误", at_sender=True)
        except MatcherException:
            raise
        except Exception as e:
            pass
        return

    message = MessageSegment.image(file=pic)
    
    try:
        await get_gsz_rank_last.finish(message=message, at_sender=True)
    except MatcherException:
        raise
    except Exception as e:
        pass