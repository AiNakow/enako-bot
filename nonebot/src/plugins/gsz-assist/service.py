from __future__ import annotations

import asyncio
import base64
import math
import os
import sqlite3
import threading
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from io import BytesIO
from typing import Any, Literal, TypeVar

import httpx
from nonebot.log import logger
from nonebot_plugin_htmlrender import html_to_pic

from .common import template_dir
from .formula_api_client import FormulaApiClient, FormulaApiError
from .ratedata_manage import Ratedata_manager
from .template_env import jinja_env
from .userdata_manage import Userdata_manager

HISTORY_ENDPOINT = "/index/formula/customer/history"
PARTNER_STATS_ENDPOINT = "/index/formula/customer/partner-stats"
RECORDS_ENDPOINT = "/index/formula/customer/records"
MAHJONG_LIST_ENDPOINT = "/index/formula/mahjong/list"
GRADE_RANK_ENDPOINT = "/index/formula/rank/grade/grid"


@dataclass(frozen=True)
class GradeRule:
    name: str
    state: Literal["unranked", "promotable", "completed"]
    rounds: int | None = None
    position_sum: int | None = None
    average: float | None = None


# Keyed by the website's grade ID, not by array position.
GRADE_RULES = {
    0: GradeRule("无段位", "unranked"),
    1: GradeRule("新人", "promotable", 7, 20, 2.9),
    2: GradeRule("5级", "promotable", 7, 19, 2.8),
    3: GradeRule("4级", "promotable", 10, 27, 2.7),
    4: GradeRule("3级", "promotable", 10, 27, 2.7),
    5: GradeRule("2级", "promotable", 12, 31, 2.6),
    6: GradeRule("1级", "promotable", 16, 41, 2.6),
    7: GradeRule("初段", "promotable", 16, 40, 2.5),
    8: GradeRule("二段", "promotable", 20, 50, 2.5),
    9: GradeRule("三段", "promotable", 25, 60, 2.4),
    10: GradeRule("四段", "promotable", 25, 60, 2.4),
    11: GradeRule("五段", "promotable", 30, 69, 2.3),
    12: GradeRule("六段", "promotable", 40, 84, 2.1),
    13: GradeRule("七段", "promotable", 45, 90, 2.0),
    14: GradeRule("八段", "promotable", 50, 95, 1.9),
    15: GradeRule("九段", "completed"),
    16: GradeRule("十段", "completed"),
}

_static_cache: dict[str, str] = {}
T = TypeVar("T")


def _read_static(filename: str) -> str:
    if filename not in _static_cache:
        with open(os.path.join(template_dir, filename), encoding="utf-8") as file:
            _static_cache[filename] = file.read()
    return _static_cache[filename]


def _render_style_context() -> dict[str, str]:
    return {
        "tailwind_css_content": _read_static("tailwind.css"),
        "daisyui_css_content": _read_static("daisyui.css"),
    }


def _number(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _integer(value: Any, default: int = 0) -> int:
    return int(_number(value, default))


def _require_dict(value: Any, endpoint: str, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise FormulaApiError(endpoint, f"{label}格式无效")
    return value


def _records(result: Any, endpoint: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    page = _require_dict(result, endpoint, "分页结果")
    raw_records = page.get("records")
    if not isinstance(raw_records, list) or not all(isinstance(item, dict) for item in raw_records):
        raise FormulaApiError(endpoint, "分页 records 格式无效")
    return [dict(item) for item in raw_records], page


def _history_from_result(result: Any) -> tuple[dict[str, Any] | None, str | None]:
    body = _require_dict(result, HISTORY_ENDPOINT, "用户结果")
    history = body.get("history")
    if history is not None and not isinstance(history, dict):
        raise FormulaApiError(HISTORY_ENDPOINT, "history 格式无效")
    qq = body.get("qq")
    return (dict(history) if history is not None else None, str(qq) if qq else None)


def _customer_id(history: dict[str, Any]) -> Any:
    customer_id = history.get("customerId")
    if not customer_id:
        raise FormulaApiError(HISTORY_ENDPOINT, "history 缺少 customerId")
    return customer_id


def _rank_rule(history: dict[str, Any]) -> GradeRule:
    grade = history.get("grade")
    if type(grade) is not int:
        raise FormulaApiError(HISTORY_ENDPOINT, "段位编号必须为整数")
    if grade not in GRADE_RULES:
        raise FormulaApiError(HISTORY_ENDPOINT, f"未知段位编号：{grade}")
    return GRADE_RULES[grade]


def _record_position(record: dict[str, Any], username: str) -> int | None:
    normalized_name = username.strip()
    for index in range(1, 5):
        if str(record.get(f"name{index}") or "").strip() == normalized_name:
            return index
    return None


def _legacy_point_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    converted: list[dict[str, Any]] = []
    for record in records[:10]:
        item = dict(record)
        for index in range(1, 5):
            item[f"point{index}"] = round(_number(record.get(f"point{index}")) * 100)
        converted.append(item)
    return converted


def _legacy_tech_data(
    history: dict[str, Any],
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    total = _integer(history.get("totalPosition"))
    winner_points = [
        _number(record.get("point1")) * 100
        for record in records
        if record.get("point1") is not None
    ]
    average_winner_point = (
        sum(winner_points) / len(winner_points) if winner_points else 40000
    )

    return {
        # 旧雷达图的火力是最近对局中一位终局点数的平均值。
        "fire": average_winner_point,
        "defense": _number(history.get("defense")),
        "stabilize": _number(history.get("stability")),
        "lucky": _number(history.get("fire"), 4),
        # 新接口的平均得点以百点为单位，旧接口以 1000 为零点。
        "tech": 1000 + _number(history.get("technique")) * 100,
        "attack": _number(history.get("luck")),
        "ratio1": _integer(history.get("position1")) / total if total else 0,
        "ratio2": _integer(history.get("position2")) / total if total else 0,
        "ratio3": _integer(history.get("position3")) / total if total else 0,
        "ratio4": _integer(history.get("position4")) / total if total else 0,
    }


def _personal_render_context(
    history: dict[str, Any],
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    customer_id = history.get("customerId")
    name = history.get("name")
    if not customer_id or not name:
        raise FormulaApiError(HISTORY_ENDPOINT, "history 缺少用户标识")

    rank_rule = _rank_rule(history)
    promotion_count = _integer(history.get("upPosition"))
    rate_list_data = []
    for record in records[:promotion_count]:
        position = _record_position(record, str(name))
        if position is not None:
            rate_list_data.append(
                {"createTime": record.get("logtime") or "", "sort": position}
            )

    return {
        "username": str(name),
        "basic_data": {
            "id": customer_id,
            "name": str(name),
            "rateName": (records[0].get("mahjongName") if records else None) or history.get("rateName") or "-",
            "allRankNum": history.get("nationaSort", "-"),
            "rateRankNum": history.get("mahjongSort", "-"),
            "totalRate": _integer(history.get("totalPosition")),
            "rankRule": asdict(rank_rule),
            "rate": history.get("rate", "-"),
            "maxPoint": round(_number(history.get("maxPoint")) * 100),
            "avgPoint": round(_number(history.get("avgPoint")) * 100),
            "upAvgPosition": _number(history.get("upAvgPosition")),
            "sumPosition": _integer(history.get("sumPosition")),
        },
        "tech_data": _legacy_tech_data(history, records),
        "rateList_data": rate_list_data,
        "ratePage_data": _legacy_point_records(records),
    }


def _hate_render_record(record: dict[str, Any], *, goodwill: bool) -> dict[str, Any]:
    hate_value = _number(record.get("hateValue"))
    return {
        "name": record.get("opponentName") or "-",
        "total": _integer(record.get("meetCount")),
        "hatred": _integer(-hate_value if goodwill else hate_value),
        "wincount": _integer(record.get("myWinCount")),
        "winRate": _number(record.get("myWinRate")) / 100,
        "opSort1": _integer(record.get("opponentPosition1")),
        "opSort2": _integer(record.get("opponentPosition2")),
        "opSort3": _integer(record.get("opponentPosition3")),
        "opSort4": _integer(record.get("opponentPosition4")),
        "opAvg": _number(record.get("opponentAvgPosition")),
        "mySort1": _integer(record.get("myPosition1")),
        "mySort2": _integer(record.get("myPosition2")),
        "mySort3": _integer(record.get("myPosition3")),
        "mySort4": _integer(record.get("myPosition4")),
        "myAvg": _number(record.get("myAvgPosition")),
    }


def _rank_render_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": record.get("name") or "-",
        "rankName": record.get("gradeText") or "-",
        "rate": record.get("rate", "-"),
        "rateName": record.get("mahjongName") or "-",
        "avgPoint": round(_number(record.get("avgPoint")) * 100),
        "upAvgPosition": _number(record.get("upAvgPosition")),
        "upRate": _integer(record.get("upPosition")),
        "totalRate": _integer(record.get("totalPosition")),
        "position1": _integer(record.get("position1")),
        "position2": _integer(record.get("position2")),
        "position3": _integer(record.get("position3")),
        "position4": _integer(record.get("position4")),
    }


def _run_sync(factory: Callable[[], Awaitable[T]]) -> T:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(factory())

    result: list[T] = []
    error: list[BaseException] = []

    def run() -> None:
        try:
            result.append(asyncio.run(factory()))
        except BaseException as exc:
            error.append(exc)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    thread.join()
    if error:
        raise error[0]
    return result[0]


async def convert_html_to_pic(content: str) -> BytesIO:
    result = await html_to_pic(
        html=content,
        type="jpeg",
        quality=70,
        device_scale_factor=2,
        wait=1000,
    )
    return result if isinstance(result, BytesIO) else BytesIO(result)


async def convert_html_to_pic_with_chart_wait(
    content: str,
    canvas_ids: list[str],
    max_wait: int = 5000,
) -> BytesIO:
    from nonebot_plugin_htmlrender.browser import get_new_page

    async with get_new_page(2, viewport={"width": 1280, "height": 10}) as page:
        page.on("console", lambda message: logger.debug(f"浏览器控制台: {message.text}"))
        page.on("pageerror", _handle_browser_page_error)
        await page.goto("file:///")
        await page.set_content(content, wait_until="load")
        await page.wait_for_timeout(500)
        try:
            await page.wait_for_function(
                "() => window.__chartsReady === true",
                timeout=max_wait,
            )
            await page.wait_for_timeout(200)
        except Exception:
            logger.warning(f"图表等待超时 ({max_wait}ms)，继续截图")
            await page.wait_for_timeout(1000)

        page_size = await page.evaluate(
            """() => ({
                width: Math.ceil(Math.max(
                    document.documentElement.scrollWidth,
                    document.body ? document.body.scrollWidth : 0,
                    window.innerWidth
                )),
                height: Math.ceil(Math.max(
                    document.documentElement.scrollHeight,
                    document.body ? document.body.scrollHeight : 0,
                    window.innerHeight
                )),
            })"""
        )
        await page.set_viewport_size(
            {
                "width": max(1280, int(page_size["width"])),
                "height": max(720, int(page_size["height"])),
            }
        )
        await page.evaluate(
            """(canvasIds) => new Promise((resolve) => {
                for (const id of canvasIds) {
                    const canvas = document.getElementById(id);
                    const chart = canvas && window.Chart && window.Chart.getChart
                        ? window.Chart.getChart(canvas)
                        : null;
                    if (chart) {
                        chart.resize();
                        chart.update('none');
                        chart.draw();
                    }
                }
                requestAnimationFrame(() => requestAnimationFrame(resolve));
            })""",
            canvas_ids,
        )
        return BytesIO(
            await page.screenshot(full_page=True, type="jpeg", quality=70)
        )


def _handle_browser_page_error(error: object) -> None:
    text = str(error)
    if "start is not defined" in text or "addRow is not defined" in text:
        logger.debug(f"忽略浏览器JS噪声: {text}")
        return
    logger.warning(f"浏览器JS错误: {text}")


class GszService:
    userdata_manager = Userdata_manager()
    ratedata_manager = Ratedata_manager()

    @staticmethod
    async def _get_history(username: str, client: FormulaApiClient) -> tuple[dict[str, Any] | None, str | None]:
        result = await client.get(HISTORY_ENDPOINT, params={"name": username})
        return _history_from_result(result)

    @staticmethod
    async def _exist_gsz_user(username: str) -> bool:
        async with FormulaApiClient() as client:
            history, _ = await GszService._get_history(username, client)
            return history is not None

    @staticmethod
    def exist_gsz_user(username: str) -> bool:
        return _run_sync(lambda: GszService._exist_gsz_user(username))

    @staticmethod
    async def bind_userinfo(uid: str, username: str) -> bool:
        async with FormulaApiClient() as client:
            history, _ = await GszService._get_history(username, client)
        if history is None:
            return False
        try:
            await asyncio.to_thread(
                GszService.userdata_manager.update_userdata,
                [{"uid": uid, "username": username}],
            )
        except sqlite3.Error:
            logger.warning("bind_userinfo: DB update failed", exc_info=True)
            return False
        return True

    @staticmethod
    async def get_userinfo_by_uid(uid: str) -> str | None:
        try:
            users = await asyncio.to_thread(GszService.userdata_manager.get_userdata, [uid])
        except sqlite3.Error:
            logger.warning("get_userinfo_by_uid: DB read failed", exc_info=True)
            return None
        return users[0]["username"] if users else None

    @staticmethod
    async def get_userinfo_by_name(username: str) -> BytesIO:
        async with FormulaApiClient() as client:
            history, qq = await GszService._get_history(username, client)
            if history is None:
                raise FormulaApiError(HISTORY_ENDPOINT, "用户不存在")
            customer_id = _customer_id(history)
            rank_rule = _rank_rule(history)
            page_size = max(10, rank_rule.rounds) if rank_rule.state == "promotable" else 50
            records_result = await client.get(
                RECORDS_ENDPOINT,
                params={"customerId": customer_id, "pageNo": 1, "pageSize": page_size},
            )
            records, _ = _records(records_result, RECORDS_ENDPOINT)

            avatar = None
            if qq:
                try:
                    response = await client._http.get(
                        "https://q.qlogo.cn/headimg_dl",
                        params={"dst_uin": qq, "spec": 640, "img_type": "jpg"},
                    )
                    response.raise_for_status()
                    if response.content:
                        avatar = base64.b64encode(response.content).decode("ascii")
                except httpx.HTTPError:
                    logger.debug("公式战头像获取失败")

        render_context = _personal_render_context(history, records)
        content = jinja_env.get_template("gsz_info.html").render(
            **_render_style_context(),
            chart_js_content=_read_static("chart.js"),
            userpic=avatar or "",
            **render_context,
        )
        return await convert_html_to_pic_with_chart_wait(
            content,
            ["radarChart", "doughnutChart", "rankTrendChart"],
        )

    @staticmethod
    async def _partner_page(
        client: FormulaApiClient,
        customer_id: Any,
        page_no: int,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        result = await client.get(
            PARTNER_STATS_ENDPOINT,
            params={"customerId": customer_id, "pageNo": page_no, "pageSize": 10},
        )
        return _records(result, PARTNER_STATS_ENDPOINT)

    @staticmethod
    async def get_rank_top(username: str) -> BytesIO:
        async with FormulaApiClient() as client:
            history, _ = await GszService._get_history(username, client)
            if history is None:
                raise FormulaApiError(HISTORY_ENDPOINT, "用户不存在")
            records, _ = await GszService._partner_page(client, _customer_id(history), 1)
        content = jinja_env.get_template("hate.html").render(
            **_render_style_context(),
            flag=0,
            username=username,
            hate_data=[
                _hate_render_record(record, goodwill=False)
                for record in records[:10]
            ],
        )
        return await convert_html_to_pic(content)

    @staticmethod
    async def get_rank_last(username: str) -> BytesIO:
        async with FormulaApiClient() as client:
            history, _ = await GszService._get_history(username, client)
            if history is None:
                raise FormulaApiError(HISTORY_ENDPOINT, "用户不存在")
            first_records, first_page = await GszService._partner_page(
                client, _customer_id(history), 1
            )
            total = _integer(first_page.get("total"), len(first_records))
            page_size = max(1, _integer(first_page.get("size") or first_page.get("pageSize"), 10))
            pages = _integer(first_page.get("pages"), math.ceil(total / page_size) if total else 0)
            if pages <= 1:
                records = first_records
            else:
                records = []
                for page_no in sorted({pages - 1, pages}):
                    page_records, _ = await GszService._partner_page(
                        client, _customer_id(history), page_no
                    )
                    records.extend(page_records)

        selected = sorted(records, key=lambda item: _number(item.get("hateValue")))[:10]
        content = jinja_env.get_template("hate.html").render(
            **_render_style_context(),
            flag=1,
            username=username,
            hate_data=[
                _hate_render_record(record, goodwill=True)
                for record in selected
            ],
        )
        return await convert_html_to_pic(content)

    @staticmethod
    async def _get_rate_id(rate_name: str) -> str | None:
        try:
            async with FormulaApiClient() as client:
                result = await client.get(
                    MAHJONG_LIST_ENDPOINT,
                    params={
                        "pageNo": 1,
                        "pageSize": 9,
                        "keyword": rate_name,
                        "provinceName": "全国",
                    },
                )
            records, _ = _records(result, MAHJONG_LIST_ENDPOINT)
        except FormulaApiError:
            logger.debug("公式战雀庄搜索失败")
            return None
        if not records:
            return None
        match = next((item for item in records if item.get("name") == rate_name), records[0])
        rate_id = match.get("id")
        return str(rate_id) if rate_id is not None else None

    @staticmethod
    def get_rate_id(rate_name: str) -> str | None:
        return _run_sync(lambda: GszService._get_rate_id(rate_name))

    @staticmethod
    def exist_rate(rate_name: str) -> bool:
        return GszService.get_rate_id(rate_name) is not None

    @staticmethod
    async def get_rateinfo_by_group_id(group_id: str) -> object | None:
        try:
            rates = await asyncio.to_thread(GszService.ratedata_manager.get_ratedata, [group_id])
        except sqlite3.Error:
            logger.warning("get_rateinfo_by_group_id: DB read failed", exc_info=True)
            return None
        return rates[0] if rates else None

    @staticmethod
    async def bind_rateinfo(group_id: str, rate_name: str) -> bool:
        rate_id = await GszService._get_rate_id(rate_name)
        if rate_id is None:
            return False
        try:
            await asyncio.to_thread(
                GszService.ratedata_manager.update_ratedata,
                [{"groupId": group_id, "rateId": rate_id, "rateName": rate_name}],
            )
        except sqlite3.Error:
            logger.warning("bind_rateinfo: DB update failed", exc_info=True)
            return False
        return True

    @staticmethod
    async def get_rank_list(rate_id: str) -> BytesIO:
        async with FormulaApiClient() as client:
            result = await client.get(
                GRADE_RANK_ENDPOINT,
                params={
                    "mahjongId": rate_id,
                    "scope": "mahjong",
                    "pageNo": 1,
                    "pageSize": 50,
                    "orderColumns": "",
                    "orderTypes": "",
                },
            )
        records, _ = _records(result, GRADE_RANK_ENDPOINT)
        rank_data = [_rank_render_record(record) for record in records[:50]]
        content = jinja_env.get_template("rank_list.html").render(
            **_render_style_context(),
            rank_data=rank_data,
        )
        return await convert_html_to_pic(content)
