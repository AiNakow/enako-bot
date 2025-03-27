from pydantic import BaseModel, Field
from nonebot import get_plugin_config
from nonebot.permission import Permission
from nonebot.adapters import Event


class Config(BaseModel):
    """Plugin Config Here"""
    plugin_admin: list = Field([], doc="插件管理员")
    hidden_plugins: list = Field([], doc="隐藏插件")

config = get_plugin_config(Config)

def get_user_id(event: Event) -> int:
    return event.get_user_id()

async def _plugin_admin(event: Event) -> bool:
    uid = get_user_id(event)
    return uid in config.plugin_admin

PLUGIN_ADMIN: Permission = Permission(_plugin_admin)
