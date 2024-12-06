import time
from nonebot.adapters.onebot.v11 import Message
from nonebot.adapters.onebot.v11 import MessageSegment
from nonebot.permission import SUPERUSER
from nonebot.log import logger
from nonebot_plugin_htmlrender import html_to_pic
from nonebot.exception import FinishedException
from nonebot.adapters.onebot.v11.bot import Bot
from nonebot.adapters import Event
from nonebot.internal.rule import Rule
from nonebot.plugin import on
from nonebot.plugin import on_startswith
from nonebot.plugin import on_fullmatch
from nonebot.plugin import on_message
from nonebot.internal.matcher import Matcher
from .services import PanelService
from .config import config
from .config import SHELL_ADMIN
from .shell.ssh_shell import SSHShell
from .shell.feak_shell import FakeShell
from .shell.shell import Shell
from typing import Dict
import html

time_stamp = time.time()

fake_shell_dict = {}
ssh_shell_dict = {}

shell_role = Rule(lambda event: str(event.raw_message).startswith("> "))
fake_shell_role = Rule(lambda event: str(event.raw_message).startswith(">> "))
close_role = Rule(lambda event: str(event.raw_message) == "> #close")
close_all_role = Rule(lambda event: str(event.raw_message) == "> #closeall")


def on_self_message(*args,  **kwargs) -> type[Matcher]:
    kwargs.setdefault("block", True)
    return on("message_sent", *args, **kwargs)


on_shell = on_message(rule=shell_role, permission=SHELL_ADMIN, priority=10, block=True)
on_fake_shell = on_message(rule=fake_shell_role, permission=SHELL_ADMIN, priority=10, block=False)
on_close = on_message(rule=shell_role & close_role, permission=SHELL_ADMIN, priority=1, block=True)
on_close_all = on_message(rule=shell_role & close_all_role, permission=SHELL_ADMIN, priority=1, block=True)
on_everyone = on_startswith("> ", priority=11, block=False)
on_everyone_close = on_fullmatch("> #close", priority=2, block=True)


def exec(shell: Shell, command: str):
    command = html.unescape(command[2:])
    if shell.is_connect():
        shell.exec(command)
    else:
        logger.error("Shell 连接失败，请确认连接配置")
        raise FinishedException
    return shell.get_output()


@on_shell.handle()
async def shell_handler(event: Event, bot: Bot):

    user_id = event.get_user_id()  # type: ignore

    ssh_shell = ssh_shell_dict.setdefault(user_id, SSHShell(hostname=config.qqshell_host, port=config.qqshell_port,
                                                            username=config.qqshell_host_user, keypath=config.qqshell_host_key_path))

    text = exec(shell=ssh_shell, command=event.raw_message)  # type: ignore

    text = "" if text == None else text

    pic = await html_to_pic(PanelService.render_text_xterm(text=text))

    message = MessageSegment.image(file=pic)

    if event.message_type == 'private':  # type: ignore
        id = event.get_user_id()  # type: ignore

        await bot.send_private_msg(user_id=id, message=Message(message), auto_escape=False)
        raise FinishedException

    await on_shell.finish(message=message)


@on_fake_shell.handle()
async def fake_shell_handler(event: Event, bot: Bot):
    user_id = event.get_user_id()  # type: ignore
    fake_shell = fake_shell_dict.setdefault(user_id, FakeShell(hostname=config.qqshell_host, port=config.qqshell_port,
                                                               username=config.qqshell_host_user, keypath=config.qqshell_host_key_path,
                                                               api_key=config.feak_shell_api_key, base_url=config.feak_shell_base_url))

    text = exec(shell=fake_shell, command=event.raw_message)  # type: ignore
    text = "" if text == None else text
    pic = await html_to_pic(PanelService.render_text_xterm(text=text))
    message = MessageSegment.image(file=pic)

    if event.message_type == 'private':  # type: ignore
        id = event.get_user_id()  # type: ignore
        await bot.send_private_msg(user_id=id, message=Message(message), auto_escape=False)
        raise FinishedException

    await on_fake_shell.finish(message=message)


@on_close.handle()
async def close_handler(event: Event, bot: Bot):

    if event.get_user_id() in ssh_shell_dict:  # type: ignore
        del ssh_shell_dict[event.get_user_id()]  # type: ignore

    if event.get_user_id() in fake_shell_dict:  # type: ignore
        del fake_shell_dict[event.get_user_id()]  # type: ignore

    if event.message_type == 'private':  # type: ignore
        id = event.get_user_id()  # type: ignore

        await bot.send_private_msg(user_id=id, message="已关闭", auto_escape=False)
        raise FinishedException

    await on_shell.finish("已关闭")


@on_close_all.handle()
async def close_user_handler(event: Event, bot: Bot):

    fake_shell_dict.clear()
    ssh_shell_dict.clear()

    if event.message_type == 'private':  # type: ignore
        id = event.get_user_id()  # type: ignore

        await bot.send_private_msg(user_id=id, message="已关闭", auto_escape=False)
        raise FinishedException

    await on_shell.finish("已关闭")


@on_everyone.handle()
async def everyone_handle(event: Event):

    user_id = event.get_user_id()

    global time_stamp

    if time.time() - time_stamp < 15:
        await on_everyone.finish(f"你先别急, 还有{15 - int(time.time() - time_stamp)}秒cd")

    time_stamp = time.time()

    fakeShell = fake_shell_dict.setdefault(user_id, FakeShell(hostname=config.qqshell_host, port=config.qqshell_port,
                                                              username=config.qqshell_host_user, keypath=config.qqshell_host_key_path,
                                                              api_key=config.feak_shell_api_key, base_url=config.feak_shell_base_url))

    text = exec(shell=fakeShell, command=event.raw_message)  # type: ignore
    text = "" if text == None else text
    pic = await html_to_pic(PanelService.render_text_xterm(text=text))
    message = MessageSegment.image(file=pic)
    await on_everyone.finish(message=message)  # type: ignore


@on_everyone_close.handle()
async def everyone_close_handle(event: Event):
    if event.get_user_id() in fake_shell_dict:
        del fake_shell_dict[event.get_user_id()]
    await on_everyone_close.finish("已关闭")
