from nonebot_plugin_htmlrender import html_to_pic
from PIL import Image
import httpx
import json
import base64
import asyncio
import nest_asyncio
from io import BytesIO

from .userdata_manage import Userdata_manager
from .common import *
from .template_env import *

nest_asyncio.apply()

async def convert_html_to_pic(content): 
    result = await html_to_pic(html=content, type="jpeg", quality=80, device_scale_factor=2) 
    return result

class GszService:
    userdata_manager = Userdata_manager()

    @staticmethod
    def bind_userinfo(uid, username) -> bool:
        userdata_manager = GszService.userdata_manager
        userdata_manager.update_userdata(userdata_list=[{"uid": uid, "username": username}])
        return True

    @staticmethod
    def get_userinfo_by_uid(uid) -> str | None:
        userdata_manager = GszService.userdata_manager
        userdata_list = userdata_manager.get_userdata(uid_list=[uid])
        if len(userdata_list) == 0:
            return None
        return userdata_list[0]["username"]

    @staticmethod
    def get_userinfo_by_name(username: str) -> BytesIO:
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