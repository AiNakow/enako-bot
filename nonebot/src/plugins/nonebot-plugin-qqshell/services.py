from .template_env import jinja_env
from .config import config


class PanelService:
    
    @staticmethod
    def render_text_xterm(text: str):
        t = jinja_env.get_template("xterm.html")
        content = t.render(pre_content=text)
        return content
