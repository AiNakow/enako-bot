from pydantic import BaseModel, Field
from nonebot import get_plugin_config


class Config(BaseModel):
    """Plugin Config Here"""
    input_img_size: int = Field(736,  doc="ocr模型的输入尺寸")

config = get_plugin_config(Config)