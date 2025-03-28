from nonebot_plugin_htmlrender import html_to_pic
from PIL import Image
import httpx
import json
import base64
import asyncio
import nest_asyncio
from io import BytesIO

from .common import *
from .template_env import *

nest_asyncio.apply()

async def convert_html_to_pic(content): 
    result = await html_to_pic(html=content, type="jpeg", quality=80, device_scale_factor=2) 
    return result
class MahjongService:

    @staticmethod
    def tenhou_paili_analyse(analyse_type, tehai_input) -> BytesIO:
        t = jinja_env.get_template("tenhou_paili.html")
        content = t.render(jsPath=os.path.join(template_dir, "1008.js"), typeStr=analyse_type, tehaiInputStr=tehai_input)
        
        pic = asyncio.run(convert_html_to_pic(content=content))

        image = Image.open(BytesIO(pic))
        rect = ((2560 - 1400) / 2, 0, (2560 - 1400) / 2 + 1400, 1400)
        crop_image = image.crop(rect)
        result_pic = BytesIO()
        crop_image.save(result_pic, format="jpeg")

        return result_pic
    
    
        
