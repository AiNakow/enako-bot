from nonebot import require
require("nonebot_plugin_htmlrender")

from nonebot.plugin import PluginMetadata

from src.public.register import plugin_register
from .config import Config
from .handler import shell_handler

__plugin_meta__ = PluginMetadata(
    name="shell",
    description="shell",
    usage=">shell <你的指令>",
    config=Config,
    homepage="",
    type="application",
    supported_adapters={"~onebot.v11"}
)

__usage_help__ = """
/qqshell
> 「命令」 发送一条shell命令，可能会执行，也可能会被辱骂
> #close  关闭当前会话
> #closeall 关闭所有会话（仅管理员）
"""

plugin_register.register(__usage_help__)