from PIL import Image
import httpx
import json
import base64
import asyncio
import nest_asyncio
from io import BytesIO
from nonebot_plugin_htmlrender import get_new_page, html_to_pic
from nonebot.log import logger

from .config import config
from .common import *
from .template_env import *
from .infer_hand import *

nest_asyncio.apply()

async def convert_html_to_pic(content): 
    result = await html_to_pic(html=content, type="jpeg", quality=70, device_scale_factor=2, wait=1000) 
    return result

async def convert_html_to_pic2(content: str) -> BytesIO:
    async with get_new_page(2.0) as page:
        try:
            page.on("console", lambda msg: logger.debug(f"浏览器控制台: {msg.text}"))
            await page.goto(f"file://{os.getcwd()}")
            await page.set_content(content, wait_until="networkidle")
            await page.wait_for_timeout(1000)
            pic = await page.screenshot(full_page=True, type="jpeg", quality=70, timeout=30000)
            await page.close()
            return pic
        except Exception as e:
            print(e)
            raise e
        
class MahjongService:

    @staticmethod
    def tenhou_paili_analyse(analyse_type: str, tehai_input: str) -> BytesIO:
        t = jinja_env.get_template("tenhou_paili.html")
        content = t.render(static_path=os.path.join(template_dir, "static/"), typeStr=analyse_type, tehaiInputStr=tehai_input)
        
        pic = asyncio.run(convert_html_to_pic2(content=content))

        image = Image.open(BytesIO(pic))
        rect = ((2560 - 1400) / 2, 0, (2560 - 1400) / 2 + 1400, 1400)
        crop_image = image.crop(rect)
        result_pic = BytesIO()
        crop_image.save(result_pic, format="jpeg")

        return result_pic
    
    @staticmethod
    def get_hand_from_image(image_url: str) -> str:
        with httpx.Client() as client:
            resp = client.get(image_url)
            resp.raise_for_status()
            image = resp.content
        imgsz = config.model_img_size

        model_path = os.path.join(model_dir, f"best_{imgsz}.onnx")
        names_path = os.path.join(model_dir, "names.json")
        rt = MahjongONNXRuntime(model_path, names_path, imgsz=imgsz, ort_intra_threads=1, ort_inter_threads=1)

        out = rt.predict_bytes(image)

        return out["tenhou"]
    
        
