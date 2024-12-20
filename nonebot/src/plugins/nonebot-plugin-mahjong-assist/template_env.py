from jinja2 import Environment, FileSystemLoader

from .common import *


def create_jinja2_env():
    """创建 Jinja2 环境"""
    env = Environment(loader=FileSystemLoader(template_dir))
    return env


jinja_env = create_jinja2_env()
