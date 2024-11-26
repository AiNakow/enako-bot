import os

from nonebot import get_plugin_config
from nonebot.plugin import PluginMetadata
from nonebot.permission import SUPERUSER
from nonebot import on_command
from nonebot.rule import to_me
from nonebot.adapters import Message
from nonebot.params import CommandArg
from nonebot.params import Depends
from nonebot.exception import MatcherException

from typing import Annotated
from .config import Config
from .event_functions import *
from .role_check import *
from .userdata_manage import *
from .auto_naga import *


__plugin_meta__ = PluginMetadata(
    name="naga-assist",
    description="本插件用于将雀魂牌谱格式转换为天凤牌谱格式，以及使用naga对牌谱进行分析",
    usage=(
        "/np分配 「qq号」「np」 (仅限NAGA_ADMIN)",
        "/np查询 「qq号」",
        "/np查询",
        "/牌谱格式转换 「雀魂牌谱链接」",
        "/牌谱分析 天凤 「天凤牌谱链接」",
        "/牌谱分析 自定义 「自定义牌谱编号」",
    ),
    type="application",
    config=Config,
)

__usage_help__ = """
本插件用于将雀魂牌谱格式转换为天凤牌谱格式，以及使用naga对牌谱进行分析
请按照如下格式发送指令：
/np分配 「qq号」「np」 (仅限NAGA_ADMIN)
/np查询 「qq号」
/np查询
/牌谱格式转换 「雀魂牌谱链接」
/牌谱分析 天凤 「天凤牌谱链接」 (每半庄消耗50np)
/牌谱分析 自定义 「自定义牌谱编号」 「小局编号」(每小局消耗10np)
"""

if not os.path.exists(data_dir):
    os.mkdir(data_dir)
if not os.path.exists(haihu_dir):
    os.mkdir(haihu_dir)
if not os.path.exists(userdata_dir):
    os.mkdir(userdata_dir)

config = get_plugin_config(Config)
naga_help = on_command("naga帮助", rule=to_me(), priority=10, block=True)
np_allocate = on_command("np分配", permission=NAGA_ADMIN, rule=to_me(), priority=10, block=True)
np_query = on_command("np查询", rule=to_me(), priority=10, block=True)
haihu_transfer = on_command("牌谱格式转换", rule=to_me(), priority=10, block=True)
haihu_analyse = on_command("牌谱分析", rule=to_me(), priority=10, block=True)

@naga_help.handle()
async def handle_function():
    try:
        await np_allocate.finish(__usage_help__, at_sender=True)
    except MatcherException:
        raise
    except Exception as e:
        pass 

@np_allocate.handle()
async def handle_function(args: Annotated[Message, CommandArg()], user_id: Annotated[str, Depends(get_user_id)]):
    arg_text = args.extract_plain_text()
    arg_list = arg_text.split(' ')
    if len(arg_list) < 2:
        try:
            await np_allocate.finish(__usage_help__, at_sender=True)
        except MatcherException:
            raise
        except Exception as e:
            pass 
    target_uid = arg_list[0]
    target_np = arg_list[1]
    userdata_list = [
        {
            "uid": target_uid,
            "np": target_np
        }
    ]
    userdata_manager = Userdata_manager()
    if userdata_manager.update_userdata(userdata_list=userdata_list):
        try:
            await np_allocate.finish("分配成功！ 剩余NP: {0}".format(target_np), at_sender=True)
        except MatcherException:
            raise
        except Exception as e:
            pass 
    else:
        try:
            await np_allocate.finish("np分配失败, 请联系NAGA账户管理员", at_sender=True)
        except MatcherException:
            raise
        except Exception as e:
            pass 


@np_query.handle()
async def handle_function(args: Annotated[Message, CommandArg()], user_id: Annotated[str, Depends(get_user_id)]):
    arg_text = args.extract_plain_text()
    if arg_text == "":
        target_uid = user_id
    else:
        target_uid = arg_text.split(" ")[0]
    userdata_manager = Userdata_manager()
    if userdata_manager.ifexist_userdata(uid=target_uid):
        target_np = userdata_manager.get_userdata(uid_list=[target_uid])[0]["np"]
    else:
        target_np = 0
        userdata_new = [
            {
                "uid": target_uid,
                "np":target_np
            }
        ]
        userdata_manager.update_userdata(userdata_list=userdata_new)

    try:
        await np_query.finish("剩余np: {0}".format(target_np), at_sender=True)
    except MatcherException:
        raise
    except Exception as e:
        pass


@haihu_transfer.handle()
async def handle_function(args: Annotated[Message, CommandArg()], user_id: Annotated[str, Depends(get_user_id)]):
    arg_text = args.extract_plain_text()
    if arg_text == "":
        try:
            await np_allocate.finish(__usage_help__, at_sender=True)
        except MatcherException:
            raise
        except Exception as e:
            pass 
    arg_list = arg_text.split(' ')
    majsoul_url = arg_list[0]

    try:
        await haihu_transfer.send("牌谱正在转换中，可能需要数十秒，请耐心等待", at_sender=True)
    except MatcherException:
        raise
    except Exception as e:
        pass
    auto_naga = Auto_naga()
    result = auto_naga.convert_majsoul(majsoul_url=majsoul_url)
    if result["status"] == 200:
        haihu_id = result["haihu_id"]
        title = result["title"]
        player = result["player"]
        preview = ""
        for i in range(len(result["preview"])):
            preview += "{0} - {1}".format(i, result["preview"][i])
            if i < len(result["preview"]) - 1:
                preview += "\n"
        try:
            await haihu_transfer.send(template_game_preview.format(haihu_id, title, player, preview), at_sender=True)
            await haihu_transfer.finish(template_analyse_hint.format(haihu_id, 0, 0, len(result["preview"]) - 1), at_sender=True)
        except MatcherException:
            raise
        except Exception as e:
            pass
    else:
        try:
            await haihu_transfer.finish("牌谱转换失败", at_sender=True)
        except MatcherException:
            raise
        except Exception as e:
            pass

@haihu_analyse.handle()
async def handle_function(args: Annotated[Message, CommandArg()], user_id: Annotated[str, Depends(get_user_id)]):
    auto_naga = Auto_naga()
    userdata_manager = Userdata_manager()
    arg_text = args.extract_plain_text()
    if arg_text == "":
        try:
            await np_allocate.finish(__usage_help__, at_sender=True)
        except MatcherException:
            raise
        except Exception as e:
            pass 
    arg_list = arg_text.split(' ')
    if arg_list[0] == "天凤":
        np_use = 50
        if userdata_manager.check_user_np(uid=user_id, np=np_use):
            try:
                await haihu_transfer.send("牌谱正在分析中，可能需要数十秒，请耐心等待", at_sender=True)
            except MatcherException:
                raise
            except Exception as e:
                pass
            analyse_result = auto_naga.analyse_tenhou(tenhou_url=arg_list[1])
        else:
            try:
                await haihu_analyse.finish("np不足，请从NAGA管理员处获取np额度", at_sender=True)
            except MatcherException:
                raise
            except Exception as e:
                pass
    elif arg_list[0] == "自定义":
        tmp = arg_list[2].split("-")
        if len(tmp) < 1 or len(tmp) > 2:
            try:
                await np_allocate.finish(__usage_help__, at_sender=True)
            except MatcherException:
                raise
            except Exception as e:
                pass 
        elif len(tmp) == 1:
            game_list = [int(tmp[0])]
        else:
            game_list = range(int(tmp[0]), int(tmp[1]) + 1)
        np_use = 10 * len(game_list)
        if userdata_manager.check_user_np(uid=user_id, np=np_use):
            try:
                await haihu_transfer.send("牌谱正在分析中，可能需要数十秒，请耐心等待", at_sender=True)
            except MatcherException:
                raise
            except Exception as e:
                pass
            analyse_result = auto_naga.analyse_custom(haihu_id=arg_list[1], game_list=game_list)
        else:
            try:
                await haihu_analyse.finish("np不足，请从NAGA管理员处获取np额度", at_sender=True)
            except MatcherException:
                raise
            except Exception as e:
                pass
    else:
        try:
            await haihu_analyse.finish(__usage_help__, at_sender=True)
        except MatcherException:
            raise
        except Exception as e:
            pass
    if analyse_result["status"] == 200:
        user_np = userdata_manager.get_userdata(uid_list=[user_id])[0]["np"]
        userdata_manager.update_userdata([
            {
                "uid": user_id,
                "np": user_np - np_use
            }
        ])
        try:
            await haihu_analyse.finish("牌谱分析成功！分析报告：{0}".format(analyse_result["report"]), at_sender=True)
        except MatcherException:
            raise
        except Exception as e:
            pass
    else:
        try:
            await haihu_analyse.finish("获取牌谱分析结果失败，请检查上传的牌谱格式", at_sender=True)
        except MatcherException:
            raise
        except Exception as e:
            pass
