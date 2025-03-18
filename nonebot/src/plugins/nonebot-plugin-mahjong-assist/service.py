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
    
    @staticmethod
    def gsz_userinfo_get(username) -> BytesIO:
        API_ENDPOINTS = {
                "basic": 'https://gsz.rmlinking.com/gszapi/customer/getCustomerByName',
                "tech": 'https://gsz.rmlinking.com/gszapi/score/tech',
                "rateList": 'https://gsz.rmlinking.com/gszapi/customer/getCustomerRateList'
            }
        try:
            basic_data = httpx.get(API_ENDPOINTS["basic"] + f'?name={username}').json()
            if basic_data['code'] != 200:
                raise Exception("获取basic_data失败")
            custom_id= basic_data['data']['id']
            qq = basic_data['data']['qq']
            tech_data = httpx.get(API_ENDPOINTS["tech"] + f'?customerId={custom_id}').json()
            if tech_data['code'] != 200:
                raise Exception("获取tech_data失败")
            rateList_data = httpx.get(API_ENDPOINTS["rateList"] + f'?customerId={custom_id}').json()
            if rateList_data['code'] != 200:
                raise Exception("获取rateList_data失败")
        except Exception as e:
            print(e)
            raise e

        raw_pic = httpx.get(f'https://q.qlogo.cn/headimg_dl?dst_uin={qq}&spec=640&img_type=jpg').content

        template = jinja_env.get_template('gsz_info.html')
        content = template.render(username=username, userpic=base64.b64encode(raw_pic).decode("utf-8"), basic_data=json.dumps(basic_data["data"]), tech_data=json.dumps(tech_data["data"]), rateList_data=json.dumps(rateList_data["data"]))
        pic = asyncio.run(convert_html_to_pic(content=content))
        
        return pic
        
