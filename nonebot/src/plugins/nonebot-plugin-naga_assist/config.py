from pydantic import BaseModel, Field
from nonebot import get_plugin_config


class Config(BaseModel):
    """Plugin Config Here"""
    naga_assist_server: str = Field("localhost", doc="server host")
    naga_assist_secret: str = Field("none", doc="auto naga secret")
    naga_assist_admin: list = Field([], doc="naga管理员")

config = get_plugin_config(Config)
