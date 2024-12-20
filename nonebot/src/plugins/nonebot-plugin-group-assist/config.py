from pydantic import BaseModel, Field


class Config(BaseModel):
    """Plugin Config Here"""
    repeat_threshold: int = Field(2, doc="复读的阈值")
    repeat_cd: int = Field(60, doc="复读冷却时间")
    repeat_white_list: list = Field([], doc="白名单群聊")