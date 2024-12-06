from pathlib import Path
from pydantic import BaseModel, Field
from nonebot import get_plugin_config
from nonebot.internal.permission import Permission as Permission
from nonebot.adapters import Event

class Config(BaseModel):
    """Plugin Config Here"""
    qqshell_admin: list = Field([], doc="shell管理员")
    qqshell_host: str = Field("localhost", doc="要连接的主机名") # type: ignore
    qqshell_port: int = Field(22, doc="要连接的主机 SSH 端口") # type: ignore
    qqshell_host_user: str = Field("root", doc="用户名") # type: ignore
    qqshell_host_key_path: str = Field("~/.ssh/id_ras", doc="密钥路径") # type: ignore
    feak_shell_api_key: str = Field("none", doc="openai key") # type: ignore
    feak_shell_base_url: str = Field("https://api.openai.com/v1", doc="openai base url") # type: ignore
    qqshell_priority: int = Field(10, doc="QQShell 响应优先级") # type: ignore

    # 以下配置为插件默认配置
    base_dir: Path = Path(__file__).parent
    template_dir: Path = base_dir.joinpath("templates")
    static_dir: Path = base_dir.joinpath("static")


config = get_plugin_config(Config)


def get_user_id(event: Event) -> int:
    return event.get_user_id()

async def _SHELL_admin(event: Event) -> bool:
    uid = get_user_id(event)
    return uid in config.qqshell_admin

SHELL_ADMIN: Permission = Permission(_SHELL_admin)
