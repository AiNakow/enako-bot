from pydantic import BaseModel, Field
from nonebot import get_plugin_config


class Config(BaseModel):
    """Plugin Config Here"""
    plugin_admin: list = Field([], doc="插件管理员")
    hidden_plugins: list = Field([], doc="隐藏插件")

config = get_plugin_config(Config)

