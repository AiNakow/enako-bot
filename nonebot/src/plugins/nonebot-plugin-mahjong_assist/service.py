from nonebot_plugin_htmlrender import html_to_pic

from .common import *
from .template_env import *

class MahjongService:

    @staticmethod
    def tenhou_paili_analyse(type, tehai_input):
        t = jinja_env.get_template("tenhou_paili.html")
        content = t.render(jsPath=os.path.join(template_dir, "1008.js"), typeStr=type, tehaiInputStr=tehai_input)
        pic = html_to_pic(html=content, device_scale_factor=0.5)

        return pic
