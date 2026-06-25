from PIL import Image
import httpx
import json
import base64
import asyncio
from io import BytesIO
from nonebot_plugin_htmlrender import html_to_pic
from nonebot.log import logger

from .config import config
from .common import *
from .template_env import *
from .infer_hand import *
from . import mahjong_analyzer

async def convert_html_to_pic(content):
    result = await html_to_pic(html=content, type="jpeg", quality=70, device_scale_factor=2, wait=1000) 
    return result

async def convert_html_to_pic2(content: str) -> BytesIO:
    return await html_to_pic(
        html=content,
        type="jpeg",
        quality=70,
        device_scale_factor=2,
        wait=1000,
    )
        
class MahjongService:

    @staticmethod
    async def tenhou_paili_analyse(tehai_input: str, mode: int) -> BytesIO:
        t = jinja_env.get_template("paili_result.html")
        tile_base_url = os.path.join(template_dir, "static/tiles")

        result = mahjong_analyzer.analyze_hand(tehai_input, mode)
        content = t.render(
            result=result,
            mode=mode,
            mode_label=MODE_LABELS[mode],
            tile_base_url=tile_base_url,
        )

        pic = await convert_html_to_pic2(content=content)

        image = Image.open(BytesIO(pic))
        rect = ((2560 - 1400) / 2, 0, (2560 - 1400) / 2 + 1400, 1400)
        crop_image = image.crop(rect)
        result_pic = BytesIO()
        image.save(result_pic, format="jpeg")

        return result_pic
    
    @staticmethod
    def get_hand_from_image(image_url: str) -> str:
        with httpx.Client() as client:
            resp = client.get(image_url)
            resp.raise_for_status()
            image = resp.content
        imgsz = config.input_img_size

        with open(data_collection_file, "a", encoding="utf-8") as f:
            f.write(image_url + "\n")

        model_path = os.path.join(model_dir, f"best_{imgsz}.onnx")
        names_path = os.path.join(model_dir, "names.json")
        rt = MahjongONNXRuntime(model_path, names_path, imgsz=imgsz, ort_intra_threads=1, ort_inter_threads=1)

        out = rt.predict_bytes(image)

        return out["tenhou"]
    
        
