# 标准库
import asyncio
import base64
import httpx
import os
import sqlite3
import json
from io import BytesIO

# 第三方库
from nonebot_plugin_htmlrender import html_to_pic
from nonebot.log import logger
from PIL import Image

# 本地模块
from .common import *
from .ratedata_manage import Ratedata_manager
from .template_env import *
from .userdata_manage import Userdata_manager

API_BASE = 'https://gsz.rmlinking.com/gszapi'

API_ENDPOINTS = {
        "basic": API_BASE + '/customer/getCustomerByName',
        "tech": API_BASE + '/score/tech',
        "customerRateList": API_BASE + '/customer/getCustomerRateList',
        "hate": API_BASE + '/score/hate',
        "rateList": API_BASE + '/customer/rate/list',
        "findRanking": API_BASE + '/customer/findRanking',
        "customerRatePage": API_BASE + '/customer/rate/page'
    }

# 缓存静态资源内容，避免每次渲染都读文件
_static_cache: dict[str, str] = {}

def _read_static(filename: str) -> str:
    """读取模板目录下的静态资源文件内容，带缓存。"""
    if filename not in _static_cache:
        with open(os.path.join(template_dir, filename), "r", encoding="utf-8") as f:
            _static_cache[filename] = f.read()
    return _static_cache[filename]

async def convert_html_to_pic(content: str) -> BytesIO:
    try:
        result = await html_to_pic(html=content, type="jpeg", quality=70, device_scale_factor=2, wait=1000) 
    except Exception as e:
        logger.debug(e)
        raise e
    return result

async def convert_html_to_pic2(content: str) -> BytesIO:
    return await html_to_pic(
        html=content,
        type="jpeg",
        quality=70,
        device_scale_factor=2,
        wait=1000,
    )

async def convert_html_to_pic_with_chart_wait(
    content: str,
    canvas_ids: list[str],
    max_wait: int = 5000,
) -> BytesIO:
    """渲染 HTML 到图片，等待所有指定 canvas 绘制完成后再截图。

    所有 JS/CSS 资源已内联在 HTML 中，Tailwind 已预编译为静态 CSS，
    无需 JIT 运行时，截图时布局确定性有保障。
    """
    from nonebot_plugin_htmlrender.browser import get_new_page

    async def log_chart_debug(page, stage: str) -> None:
        """Log browser-side canvas status before screenshot for diagnosis."""
        try:
            debug_info = await page.evaluate(
                """(canvasIds) => {
                    const sampleCanvas = (canvas) => {
                        const ctx = canvas.getContext('2d');
                        if (!ctx || canvas.width === 0 || canvas.height === 0) {
                            return {
                                sampled: false,
                                nonTransparent: 0,
                                nonWhite: 0,
                                sampleCount: 0,
                            };
                        }

                        const width = canvas.width;
                        const height = canvas.height;
                        const points = [];
                        for (let y = 0; y < 5; y++) {
                            for (let x = 0; x < 5; x++) {
                                points.push([
                                    Math.floor((x + 0.5) * width / 5),
                                    Math.floor((y + 0.5) * height / 5),
                                ]);
                            }
                        }

                        let nonTransparent = 0;
                        let nonWhite = 0;
                        for (const [x, y] of points) {
                            const pixel = ctx.getImageData(x, y, 1, 1).data;
                            const [r, g, b, a] = pixel;
                            if (a !== 0) nonTransparent++;
                            if (!(r > 245 && g > 245 && b > 245 && a > 0)) nonWhite++;
                        }

                        return {
                            sampled: true,
                            nonTransparent,
                            nonWhite,
                            sampleCount: points.length,
                        };
                    };

                    return {
                        chartsReady: window.__chartsReady,
                        chartsError: window.__chartsError ? String(window.__chartsError) : null,
                        chartDefined: typeof window.Chart !== 'undefined',
                        devicePixelRatio: window.devicePixelRatio,
                        viewport: {
                            innerWidth: window.innerWidth,
                            innerHeight: window.innerHeight,
                            scrollWidth: document.documentElement.scrollWidth,
                            scrollHeight: document.documentElement.scrollHeight,
                            bodyScrollHeight: document.body ? document.body.scrollHeight : null,
                        },
                        canvases: canvasIds.map((id) => {
                            const canvas = document.getElementById(id);
                            if (!canvas) {
                                return { id, exists: false };
                            }
                            const rect = canvas.getBoundingClientRect();
                            const chart = window.Chart && window.Chart.getChart
                                ? window.Chart.getChart(canvas)
                                : null;
                            return {
                                id,
                                exists: true,
                                attrWidth: canvas.width,
                                attrHeight: canvas.height,
                                clientWidth: canvas.clientWidth,
                                clientHeight: canvas.clientHeight,
                                rect: {
                                    x: rect.x,
                                    y: rect.y,
                                    width: rect.width,
                                    height: rect.height,
                                },
                                display: getComputedStyle(canvas).display,
                                visibility: getComputedStyle(canvas).visibility,
                                chartExists: Boolean(chart),
                                chartSize: chart ? {
                                    width: chart.width,
                                    height: chart.height,
                                    attached: chart.attached,
                                } : null,
                                sample: sampleCanvas(canvas),
                            };
                        }),
                    };
                }""",
                canvas_ids,
            )
            logger.warning(f"图表诊断[{stage}]: {json.dumps(debug_info, ensure_ascii=False)}")
        except Exception:
            logger.warning(f"图表诊断[{stage}]失败", exc_info=True)

    async with get_new_page(2, viewport={"width": 1280, "height": 10}) as page:
        page.on("console", lambda msg: logger.debug(f"浏览器控制台: {msg.text}"))
        page.on("pageerror", lambda err: logger.warning(f"浏览器JS错误: {err}"))
        await page.goto("file:///")  # 使用 file:// origin，与 htmlrender 标准做法一致
        await page.set_content(content, wait_until="load")
        await page.wait_for_timeout(500)  # CSS 已预编译为静态文件，只需等待解析完成

        try:
            await page.wait_for_function(
                "() => window.__chartsReady === true",
                timeout=max_wait,
            )
            await page.wait_for_timeout(200)  # 确保 rAF 回调中的 resize() 完全执行
        except Exception:
            logger.warning(f"图表等待超时 ({max_wait}ms)，继续截图")
            await page.wait_for_timeout(1000)

        await log_chart_debug(page, "before_screenshot")

        return await page.screenshot(
            full_page=True,
            type="jpeg",
            quality=70,
        )


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
        except Exception as e:
            logger.debug(f"API请求失败：{e}")
            raise

        if basic_data['data'] == "":
            return False
        return True
    
    @staticmethod
    async def bind_userinfo(uid: str, username: str) -> bool:
        if not GszService.exist_gsz_user(username):
            return False
        userdata_manager = GszService.userdata_manager
        try:
            await asyncio.to_thread(
                userdata_manager.update_userdata,
                [{"uid": uid, "username": username}],
            )
        except sqlite3.Error:
            logger.warning("bind_userinfo: DB update failed", exc_info=True)
            return False
        return True

    @staticmethod
    async def get_userinfo_by_uid(uid: str) -> str | None:
        userdata_manager = GszService.userdata_manager
        try:
            userdata_list = await asyncio.to_thread(userdata_manager.get_userdata, [uid])
        except sqlite3.Error:
            logger.warning("get_userinfo_by_uid: DB read failed", exc_info=True)
            return None
        logger.warning(f"[diag] get_userinfo_by_uid uid={uid!r} -> {len(userdata_list)} rows, _initialized={userdata_manager._initialized}")
        if len(userdata_list) == 0:
            return None
        return userdata_list[0]["username"]

    @staticmethod
    async def get_userinfo_by_name(username: str) -> BytesIO:
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
            ratePage_data = httpx.post(API_ENDPOINTS["customerRatePage"] + f'?customerId={custom_id}&pageNo=1&pageSize=10', timeout=timeout_config).json()
            if ratePage_data['code'] != 200:
                raise Exception("获取ratePage_data失败")
        except Exception as e:
            logger.debug(f"API请求失败：{e}")
            raise

        logger.debug(f"获取用户信息: {username}({qq})")
        raw_pic = httpx.get(f'https://q.qlogo.cn/headimg_dl?dst_uin={qq}&spec=640&img_type=jpg').content

        template = jinja_env.get_template('gsz_info.html')
        content = template.render(
            tailwind_css_content=_read_static('tailwind.css'),
            daisyui_css_content=_read_static('daisyui.css'),
            chart_js_content=_read_static('chart.js'),
            username=username,
            userpic=base64.b64encode(raw_pic).decode("utf-8"),
            basic_data=basic_data["data"],
            tech_data=tech_data["data"],
            rateList_data=rateList_data["data"],
            ratePage_data=ratePage_data["data"]["records"]
            )
        logger.debug(f"渲染模板内容: {content[:100]}...")  # 仅打印前100个字符以避免过长输出
        pic = await convert_html_to_pic_with_chart_wait(
            content=content,
            canvas_ids=["radarChart", "doughnutChart", "rankTrendChart"],
            max_wait=5000,
        )
        logger.debug(f"获取用户信息图片: {username}({qq})")
        
        return pic

    @staticmethod
    async def get_rank_top(username: str) -> BytesIO:
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
        pic = await convert_html_to_pic(content=content)

        return pic

    @staticmethod
    async def get_rank_last(username: str) -> BytesIO:
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
        pic = await convert_html_to_pic(content=content)

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
    async def get_rateinfo_by_group_id(group_id: str) -> object | None:
        ratedata_manager = GszService.ratedata_manager
        try:
            ratedata_list = await asyncio.to_thread(ratedata_manager.get_ratedata, [group_id])
        except sqlite3.Error:
            logger.warning("get_rateinfo_by_group_id: DB read failed", exc_info=True)
            return None
        if len(ratedata_list) == 0:
            return None
        return ratedata_list[0]

    @staticmethod
    async def bind_rateinfo(group_id: str, rate_name: str) -> bool:
        if not GszService.exist_rate(rate_name):
            return False
        ratedata_manager = GszService.ratedata_manager
        rate_id = GszService.get_rate_id(rate_name)
        if rate_id is None:
            return False
        try:
            await asyncio.to_thread(
                ratedata_manager.update_ratedata,
                [{"groupId": group_id, "rateId": rate_id, "rateName": rate_name}],
            )
        except sqlite3.Error:
            logger.warning("bind_rateinfo: DB update failed", exc_info=True)
            return False
        return True
    
    @staticmethod
    async def get_rank_list(rate_id: str) -> BytesIO:
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

        pic = await convert_html_to_pic(content=content)

        return pic
