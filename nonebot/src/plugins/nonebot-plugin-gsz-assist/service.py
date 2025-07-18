# 标准库
import asyncio
import base64
import httpx
import json
import nest_asyncio
import os
from io import BytesIO

# 第三方库
from nonebot_plugin_htmlrender import get_new_page, html_to_pic
from nonebot.log import logger
from PIL import Image

# 本地模块
from .common import *
from .ratedata_manage import Ratedata_manager
from .template_env import *
from .userdata_manage import Userdata_manager

API_ENDPOINTS = {
        "basic": 'https://gsz.rmlinking.com/gszapi/customer/getCustomerByName',
        "tech": 'https://gsz.rmlinking.com/gszapi/score/tech',
        "customerRateList": 'https://gsz.rmlinking.com/gszapi/customer/getCustomerRateList',
        "hate": 'https://gsz.rmlinking.com/gszapi/score/hate',
        "rateList": 'https://gsz.rmlinking.com/gszapi/customer/rate/list',
        "findRanking": 'https://gsz.rmlinking.com/gszapi/customer/findRanking'
    }

nest_asyncio.apply()

async def convert_html_to_pic(content: str) -> BytesIO: 
    try:
        result = await html_to_pic(html=content, type="jpeg", quality=70, device_scale_factor=2, wait=1000) 
    except Exception as e:
        logger.debug(e)
        raise e
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

class GszService:
    userdata_manager = Userdata_manager()
    ratedata_manager = Ratedata_manager()

    @staticmethod
    def exist_gsz_user(username: str) -> bool:
        timeout_config = httpx.Timeout(30.0, connect=15.0, read=15.0)
        try:
            basic_data = httpx.post(API_ENDPOINTS["basic"] + f'?name={username}&mobile=', timeout=timeout_config).json()
            if basic_data['code'] != 200:
                raise Exception("获取basic_data失败")
        except httpx.ConnectError as e:
            logger.debug(f"连接失败：{e}")
        except httpx.ReadTimeout as e:
            logger.debug(f"读取超时：{e}")
        except httpx.HTTPStatusError as e:
            logger.debug(f"响应状态码错误: {e.response.status_code}")
        except httpx.RequestError as e:
            logger.debug(f"请求失败：{e}")
        except Exception as e:
            logger.debug(f"其他错误：{e}")
        
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
        logger.debug(f"开始获取用户信息: {username}")
        timeout_config = httpx.Timeout(30.0, connect=15.0, read=15.0)
        logger.debug(f"设置请求超时时间: {timeout_config}")
        try:
            basic_data = httpx.post(API_ENDPOINTS["basic"] + f'?name={username}&mobile=', timeout=timeout_config).json()
            if basic_data['code'] != 200:
                raise Exception("获取basic_data失败")
            custom_id= basic_data['data']['id']
            qq = basic_data['data']['qq']
            tech_data = httpx.post(API_ENDPOINTS["tech"] + f'?customerId={custom_id}', timeout=timeout_config).json()
            if tech_data['code'] != 200:
                raise Exception("获取tech_data失败")
            rateList_data = httpx.post(API_ENDPOINTS["customerRateList"] + f'?customerId={custom_id}', timeout=timeout_config).json()
            if rateList_data['code'] != 200:
                raise Exception("获取rateList_data失败")
        except httpx.ConnectError as e:
            logger.debug(f"连接失败：{e}")
        except httpx.ReadTimeout as e:
            logger.debug(f"读取超时：{e}")
        except httpx.HTTPStatusError as e:
            logger.debug(f"响应状态码错误: {e.response.status_code}")
        except httpx.RequestError as e:
            logger.debug(f"请求失败：{e}")
        except Exception as e:
            logger.debug(f"其他错误：{e}")

        logger.debug(f"获取用户信息: {username}({qq})")
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
        logger.debug(f"渲染模板内容: {content[:100]}...")  # 仅打印前100个字符以避免过长输出
        pic = asyncio.run(convert_html_to_pic2(content=content))
        logger.debug(f"获取用户信息图片: {username}({qq})")
        
        return pic

    @staticmethod
    def get_rank_top(username: str) -> BytesIO:
        timeout_config = httpx.Timeout(30.0, connect=15.0, read=15.0)
        try:
            basic_data = httpx.post(API_ENDPOINTS["basic"] + f'?name={username}', timeout=timeout_config).json()
            if basic_data['code'] != 200:
                raise Exception("获取basic_data失败")
            custom_id= basic_data['data']['id']
            hate_data_top = httpx.post(API_ENDPOINTS["hate"] + f'?customerId={custom_id}&pageNo=1&pageSize=10', timeout=timeout_config).json()
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
        timeout_config = httpx.Timeout(30.0, connect=15.0, read=15.0)
        try:
            basic_data = httpx.post(API_ENDPOINTS["basic"] + f'?name={username}', timeout=timeout_config).json()
            if basic_data['code'] != 200:
                raise Exception("获取basic_data失败")
            custom_id= basic_data['data']['id']
            hate_data= httpx.post(API_ENDPOINTS["hate"] + f'?customerId={custom_id}&pageNo=1&pageSize=10', timeout=timeout_config).json()
            if hate_data['code'] != 200:
                raise Exception("获取hate_data失败")
            pageNo = hate_data["data"]["pages"]
            hate_data = httpx.post(API_ENDPOINTS["hate"] + f'?customerId={custom_id}&pageNo={pageNo}&pageSize=10', timeout=timeout_config).json()
            if hate_data['code'] != 200:
                raise Exception("获取hate_data_last_page失败")
            hate_data_last = hate_data["data"]["records"]
            hate_data = httpx.post(API_ENDPOINTS["hate"] + f'?customerId={custom_id}&pageNo={pageNo-1}&pageSize=10', timeout=timeout_config).json()
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
        timeout_config = httpx.Timeout(30.0, connect=15.0, read=15.0)
        try:
            rate_data = httpx.post(API_ENDPOINTS["rateList"] + f'?&pageNo=1&pageSize=9&name={rate_name}&areaName=&province=&city=', timeout=timeout_config).json()
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
        timeout_config = httpx.Timeout(30.0, connect=15.0, read=15.0)
        try:
            rank_data = httpx.post(API_ENDPOINTS["findRanking"] + f'?pageNo=1&pageSize=50&pid={rate_id}&sortField=rank&sortType=desc', timeout=timeout_config).json()
            if rank_data['code'] != 200:
                raise Exception("获取rank_data失败")
        except Exception as e:
            print(e)
            raise e
        
        rank_data = rank_data["data"]["records"]

        template = jinja_env.get_template('rank_list.html')
        content = template.render(
            daisyui_css=os.path.join(template_dir, 'daisyui.css'),
            tailwind_js=os.path.join(template_dir, 'tailwind.js'),
            rank_data=rank_data
        )
        
        pic = asyncio.run(convert_html_to_pic(content=content))

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
