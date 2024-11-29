from nonebot_plugin_htmlrender import html_to_pic
from PIL import Image
import asyncio

from .common import *
from .template_env import *

class MahjongService:

    @staticmethod
    def tenhou_paili_analyse(analyse_type, tehai_input):
        t = jinja_env.get_template("tenhou_paili.html")
        content = t.render(jsPath=os.path.join(template_dir, "1008.js"), typeStr=analyse_type, tehaiInputStr=tehai_input)
        
        async def convert_html_to_pic(content): 
            result = await html_to_pic(html=content, type="jpeg", quality=80, device_scale_factor=2) 
            return result
        
        loop = asyncio.get_event_loop() 
        pic = loop.run_until_complete(convert_html_to_pic(content=content))
        print(type(pic))

        image = Image.frombytes(mode="RGB", size=(2560, 1440), data=pic)
        rect = ((2560 - 1200) / 2, 0, (2560 - 1200) / 2 + 1200, 1400)
        crop_image = image.crop(rect)
        result_pic = crop_image.tobytes()

        return result_pic
