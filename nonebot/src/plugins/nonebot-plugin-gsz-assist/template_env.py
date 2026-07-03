import json

from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup

from .common import *


def _tojson(obj):
    """Serialize to JSON, escaping characters unsafe in <script> context."""
    s = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    s = (
        s.replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace("'", "\\u0027")
    )
    return Markup(s)


def create_jinja2_env():
    """创建 Jinja2 环境"""
    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=True,
    )
    env.filters["tojson"] = _tojson
    return env


jinja_env = create_jinja2_env()
