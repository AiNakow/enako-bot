from nonebot_plugin_htmlrender import html_to_pic, template_to_pic, md_to_pic
from PIL import Image
import httpx
import json
import base64
import asyncio
import nest_asyncio
from io import BytesIO

from .userdata_manage import Userdata_manager
from .ratedata_manage import Ratedata_manager
from .common import *
from .template_env import *

API_ENDPOINTS = {
        "basic": 'https://gsz.rmlinking.com/gszapi/customer/getCustomerByName',
        "tech": 'https://gsz.rmlinking.com/gszapi/score/tech',
        "customerRateList": 'https://gsz.rmlinking.com/gszapi/customer/getCustomerRateList',
        "hate": 'https://gsz.rmlinking.com/gszapi/score/hate',
        "rateList": 'https://gsz.rmlinking.com/gszapi/customer/rate/list',
        "findRanking": 'https://gsz.rmlinking.com/gszapi/customer/findRanking'
    }

nest_asyncio.apply()

async def convert_html_to_pic(content): 
    try:
        result = await html_to_pic(html=content, type="jpeg", quality=70, device_scale_factor=2, wait=1000) 
    except Exception as e:
        print(e)
        raise e
    return result

class GszService:
    userdata_manager = Userdata_manager()
    ratedata_manager = Ratedata_manager()

    @staticmethod
    def exist_gsz_user(username: str) -> bool:
        try:
            basic_data = httpx.post(API_ENDPOINTS["basic"] + f'?name={username}&mobile=').json()
            if basic_data['code'] != 200:
                raise Exception("获取basic_data失败")
        except Exception as e:
            print(e)
            return False
        
        if basic_data['data'] == "":
            return False
        return True
    
    @staticmethod
    def bind_userinfo(uid: str, username: str) -> bool:
        if not GszService.exist_gsz_user(username):
            return False
        userdata_manager = GszService.userdata_manager
        userdata_manager.update_userdata(userdata_list=[{"uid": uid, "username": username}])
        return True

    @staticmethod
    def get_userinfo_by_uid(uid: str) -> str | None:
        userdata_manager = GszService.userdata_manager
        userdata_list = userdata_manager.get_userdata(uid_list=[uid])
        if len(userdata_list) == 0:
            return None
        return userdata_list[0]["username"]

    @staticmethod
    def get_userinfo_by_name(username: str) -> BytesIO:
        try:
            basic_data = httpx.post(API_ENDPOINTS["basic"] + f'?name={username}&mobile=').json()
            if basic_data['code'] != 200:
                raise Exception("获取basic_data失败")
            custom_id= basic_data['data']['id']
            qq = basic_data['data']['qq']
            tech_data = httpx.post(API_ENDPOINTS["tech"] + f'?customerId={custom_id}').json()
            if tech_data['code'] != 200:
                raise Exception("获取tech_data失败")
            rateList_data = httpx.post(API_ENDPOINTS["customerRateList"] + f'?customerId={custom_id}').json()
            if rateList_data['code'] != 200:
                raise Exception("获取rateList_data失败")
        except Exception as e:
            print(e)
            raise e

        raw_pic = httpx.get(f'https://q.qlogo.cn/headimg_dl?dst_uin={qq}&spec=640&img_type=jpg').content

        template = jinja_env.get_template('gsz_info.html')
        content = template.render(
            tailwind_js=os.path.join(template_dir, 'tailwind.js'),
            daisyui_css=os.path.join(template_dir, 'daisyui.css'),
            chart_js=os.path.join(template_dir, 'chart.js'),
            username=username, 
            userpic=base64.b64encode(raw_pic).decode("utf-8"), 
            basic_data=json.dumps(basic_data["data"]), 
            tech_data=json.dumps(tech_data["data"]), 
            rateList_data=json.dumps(rateList_data["data"])
            )
        pic = asyncio.run(convert_html_to_pic(content=content))
        
        return pic

    @staticmethod
    def get_rank_top(username: str) -> BytesIO:
        try:
            basic_data = httpx.post(API_ENDPOINTS["basic"] + f'?name={username}').json()
            if basic_data['code'] != 200:
                raise Exception("获取basic_data失败")
            custom_id= basic_data['data']['id']
            hate_data_top = httpx.post(API_ENDPOINTS["hate"] + f'?customerId={custom_id}&pageNo=1&pageSize=10').json()
            if hate_data_top['code'] != 200:
                raise Exception("获取hate_data_top失败")
        except Exception as e:
            print(e)
            raise e
        
        template = jinja_env.get_template('hate.html')
        content = template.render(
            tailwind_js=os.path.join(template_dir, 'tailwind.js'),
            daisyui_css=os.path.join(template_dir, 'daisyui.css'),
            flag=0,
            username=username,
            hate_data=hate_data_top["data"]["records"]
            )
        pic = asyncio.run(convert_html_to_pic(content=content))

        return pic

    @staticmethod
    def get_rank_last(username: str) -> BytesIO:
        try:
            basic_data = httpx.post(API_ENDPOINTS["basic"] + f'?name={username}').json()
            if basic_data['code'] != 200:
                raise Exception("获取basic_data失败")
            custom_id= basic_data['data']['id']
            hate_data= httpx.post(API_ENDPOINTS["hate"] + f'?customerId={custom_id}&pageNo=1&pageSize=10').json()
            if hate_data['code'] != 200:
                raise Exception("获取hate_data失败")
            pageNo = hate_data["data"]["pages"]
            hate_data = httpx.post(API_ENDPOINTS["hate"] + f'?customerId={custom_id}&pageNo={pageNo}&pageSize=10').json()
            if hate_data['code'] != 200:
                raise Exception("获取hate_data_last_page失败")
            hate_data_last = hate_data["data"]["records"]
            hate_data = httpx.post(API_ENDPOINTS["hate"] + f'?customerId={custom_id}&pageNo={pageNo-1}&pageSize=10').json()
            if hate_data['code'] != 200:
                raise Exception("获取hate_data_last_page-1失败")
            hate_data_last = hate_data["data"]["records"] + hate_data_last
            if len(hate_data_last) > 10:
                hate_data_last = hate_data_last[-10:]
            for i in range(len(hate_data_last)):
                hate_data_last[i]["hatred"] = -hate_data_last[i]["hatred"]
            hate_data_last = sorted(hate_data_last, key=lambda x: x["hatred"], reverse=True)

        except Exception as e:
            print(e)
            raise e
        
        template = jinja_env.get_template('hate.html')
        content = template.render(
            tailwind_js=os.path.join(template_dir, 'tailwind.js'),
            daisyui_css=os.path.join(template_dir, 'daisyui.css'),
            flag=1,
            username=username,
            hate_data=hate_data_last
            )
        pic = asyncio.run(convert_html_to_pic(content=content))

        return pic
    
    @staticmethod
    def get_rate_id(rate_name: str) -> str | None:
        try:
            rate_data = httpx.post(API_ENDPOINTS["rateList"] + f'?&pageNo=1&pageSize=9&name={rate_name}&areaName=&province=&city=').json()
            if rate_data['code'] != 200:
                raise Exception("获取rate_data失败")
        except Exception as e:
            print(e)
            return None
        
        if len(rate_data["data"]["records"]) == 0:
            return None
        return rate_data["data"]["records"][0]["id"]
    
    @staticmethod
    def exist_rate(rate_name: str) -> bool:
        return GszService.get_rate_id(rate_name) is not None
        
    @staticmethod
    def get_rateinfo_by_group_id(group_id: str) -> object | None:
        ratedata_manager = GszService.ratedata_manager
        ratedata_list = ratedata_manager.get_ratedata(groupId_list=[group_id])
        if len(ratedata_list) == 0:
            return None
        return ratedata_list[0]

    @staticmethod
    def bind_rateinfo(group_id: str, rate_name: str) -> bool:
        if not GszService.exist_rate(rate_name):
            return False
        ratedata_manager = GszService.ratedata_manager
        rate_id = GszService.get_rate_id(rate_name)
        ratedata_manager.update_ratedata(ratedata_list=[{"groupId": group_id, "rateId": rate_id, "rateName": rate_name}])
        return True
    
    @staticmethod
    def get_rank_list(rate_id: str) -> BytesIO:
        try:
            rank_data = httpx.post(API_ENDPOINTS["findRanking"] + f'?pageNo=1&pageSize=10000&pid={rate_id}&sortField=rank&sortType=desc').json()
            if rank_data['code'] != 200:
                raise Exception("获取rank_data失败")
        except Exception as e:
            print(e)
            raise e
        
        rank_data = rank_data["data"]["records"]
        print(rank_data[0])

        template = jinja_env.get_template('rank_list.md')
        content = template.render(
            rank_data=rank_data
        )

        pic = asyncio.run(md_to_pic(md=content, type="jpeg", quality=70, device_scale_factor=2))
        

        # pic = asyncio.run(template_to_pic(
        #     template_path=template_dir, 
        #     template_name='rank_list.html',
        #     templates={
        #     "tailwind_js": os.path.join(template_dir, 'tailwind.js'), 
        #     "daisyui_css": os.path.join(template_dir, 'daisyui.css'), 
        #     "rank_data": rank_data
        #     },
        #     wait=1000,
        #     ))

        return pic
