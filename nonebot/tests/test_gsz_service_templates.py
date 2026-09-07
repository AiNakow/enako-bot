from __future__ import annotations

import asyncio
import inspect
import json
import os
from io import BytesIO
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from PIL import Image, ImageStat

from gsz_assist_testpkg import service
from gsz_assist_testpkg.formula_api_client import FormulaApiError


@pytest.fixture
def formula_fixture() -> dict[str, Any]:
    path = Path(__file__).parent / "fixtures" / "gsz_formula_responses.json"
    return json.loads(path.read_text(encoding="utf-8"))


class FakeFormulaClient:
    instance: "FakeFormulaClient | None" = None
    responses: dict[str, Any] = {}

    def __init__(self, *_: Any, **__: Any) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._http = Mock()
        type(self).instance = self

    async def __aenter__(self) -> "FakeFormulaClient":
        return self

    async def __aexit__(self, *_: Any) -> None:
        return None

    async def get(self, endpoint: str, *, params: dict[str, Any] | None = None) -> Any:
        params = params or {}
        self.calls.append((endpoint, params))
        value = self.responses[endpoint]
        if callable(value):
            value = value(params)
        if isinstance(value, BaseException):
            raise value
        return value


def test_personal_render_context_restores_legacy_fields_and_calculations(
    formula_fixture: dict[str, Any],
) -> None:
    history = formula_fixture["history"]["history"]
    records = formula_fixture["records"]["records"]
    original = json.loads(json.dumps(records))

    context = service._personal_render_context(history, records)

    basic = context["basic_data"]
    assert basic["rankRule"] == {
        "name": "二段",
        "state": "promotable",
        "rounds": 20,
        "position_sum": 50,
        "average": 2.5,
    }
    assert basic["maxPoint"] == 51230
    assert basic["avgPoint"] == 27845
    assert context["rateList_data"] == [
        {"createTime": "2026-08-25 20:00:00", "sort": 2},
        {"createTime": "2026-08-24 20:00:00", "sort": 1},
    ]
    assert context["ratePage_data"][0]["point2"] == 30050
    assert context["ratePage_data"][1]["point1"] == 45555
    assert context["tech_data"] == {
        "fire": 42837.5,
        "defense": 0.76,
        "stabilize": 0.51,
        "lucky": 2.48,
        "tech": 1120.0,
        "attack": 0.27,
        "ratio1": 0.25,
        "ratio2": 0.3,
        "ratio3": 0.2,
        "ratio4": 0.25,
    }
    assert records == original


@pytest.mark.parametrize(
    "grade, rank, rounds, total, average",
    [
        (0, "无段位", None, None, None),
        (1, "新人", 7, 20, 2.9),
        (2, "5级", 7, 19, 2.8),
        (3, "4级", 10, 27, 2.7),
        (4, "3级", 10, 27, 2.7),
        (5, "2级", 12, 31, 2.6),
        (6, "1级", 16, 41, 2.6),
        (7, "初段", 16, 40, 2.5),
        (8, "二段", 20, 50, 2.5),
        (9, "三段", 25, 60, 2.4),
        (10, "四段", 25, 60, 2.4),
        (11, "五段", 30, 69, 2.3),
        (12, "六段", 40, 84, 2.1),
        (13, "七段", 45, 90, 2.0),
        (14, "八段", 50, 95, 1.9),
        (15, "九段", None, None, None),
        (16, "十段", None, None, None),
    ],
)
def test_current_grade_dictionary_and_promotion_rules(
    grade: int, rank: str, rounds: int | None, total: int | None, average: float | None,
) -> None:
    state = "unranked" if grade == 0 else "completed" if grade in (15, 16) else "promotable"
    assert service._rank_rule({"grade": grade}) == service.GradeRule(
        rank, state, rounds, total, average,
    )


@pytest.mark.parametrize("grade", [-1, 17, None, "invalid", "8", 8.5, 8.0, True, False, [], {}])
def test_invalid_grade_is_rejected(grade: Any) -> None:
    with pytest.raises(FormulaApiError, match="段位编号"):
        service._rank_rule({"grade": grade})


@pytest.mark.parametrize("grade", [17, 8.5])
def test_unknown_or_invalid_grade_stops_before_records_and_rendering(
    formula_fixture: dict[str, Any], grade: Any,
) -> None:
    FakeFormulaClient.responses = {
        service.HISTORY_ENDPOINT: {
            "history": {**formula_fixture["history"]["history"], "grade": grade}, "qq": None,
        },
    }

    async def scenario() -> None:
        with (
            patch.object(service, "FormulaApiClient", FakeFormulaClient),
            patch.object(service, "convert_html_to_pic_with_chart_wait", AsyncMock()) as render,
        ):
            with pytest.raises(FormulaApiError, match="段位编号"):
                await service.GszService.get_userinfo_by_name("玩家")
            render.assert_not_awaited()
        assert FakeFormulaClient.instance is not None
        assert [call[0] for call in FakeFormulaClient.instance.calls] == [service.HISTORY_ENDPOINT]

    asyncio.run(scenario())


def test_legacy_tech_data_handles_empty_totals_and_records() -> None:
    assert service._legacy_tech_data({"totalPosition": 0}, []) == {
        "fire": 40000,
        "defense": 0,
        "stabilize": 0,
        "lucky": 4,
        "tech": 1000,
        "attack": 0,
        "ratio1": 0,
        "ratio2": 0,
        "ratio3": 0,
        "ratio4": 0,
    }


def test_templates_escape_html_secure_json_and_handle_zero_totals(formula_fixture: dict[str, Any]) -> None:
    context = service._personal_render_context(
        formula_fixture["history"]["history"],
        formula_fixture["records"]["records"],
    )
    context["ratePage_data"][0]["mahjongName"] = "测试</script><script>alert(1)</script>"
    user_html = service.jinja_env.get_template("gsz_info.html").render(
        **service._render_style_context(),
        chart_js_content=service._read_static("chart.js"),
        userpic=None,
        **context,
    )
    assert "测试玩家\\u003c安全\\u003e" in user_html
    assert "\\u003c/script\\u003e\\u003cscript\\u003ealert(1)" in user_html
    assert "</script><script>alert(1)</script>" not in user_html
    assert "健康麻将联合 - 数据预览" in user_html
    assert "window.__chartsReady = true" in user_html
    assert all(label in user_html for label in ("最高点数", "最近顺位数据（旧 → 新）", "近10场顺位走势"))

    rank_data = [service._rank_render_record(formula_fixture["rank"]["records"][0])]
    rank_html = service.jinja_env.get_template("rank_list.html").render(
        **service._render_style_context(), rank_data=rank_data
    )
    assert "0.0%" in rank_html
    assert "雀庄段位排行榜" in rank_html


def test_history_missing_and_required_structure_errors() -> None:
    assert service._history_from_result({"history": None, "qq": None}) == (None, None)
    with pytest.raises(FormulaApiError, match="history 格式无效"):
        service._history_from_result({"history": []})
    with pytest.raises(FormulaApiError, match="records 格式无效"):
        service._records({"records": None}, "/endpoint")
    with pytest.raises(FormulaApiError, match="格式无效"):
        service._require_dict([], "/endpoint", "结果")
    assert service._number("bad", 7) == 7
    assert service._number(float("nan"), 8) == 8
    with pytest.raises(FormulaApiError, match="用户标识"):
        service._personal_render_context({"grade": 0}, [])


def test_sync_bridge_works_inside_an_existing_event_loop() -> None:
    async def check() -> None:
        with patch.object(service.GszService, "_exist_gsz_user", AsyncMock(return_value=True)):
            assert service.GszService.exist_gsz_user("玩家") is True

    asyncio.run(check())


def test_sync_bridge_propagates_thread_exception() -> None:
    async def fail() -> bool:
        raise RuntimeError("thread failure")

    async def check() -> None:
        with pytest.raises(RuntimeError, match="thread failure"):
            service._run_sync(fail)

    asyncio.run(check())


def test_user_binding_existence_and_database_paths(formula_fixture: dict[str, Any]) -> None:
    FakeFormulaClient.responses = {
        service.HISTORY_ENDPOINT: formula_fixture["history"]
    }

    async def run_inline(function: Any, *args: Any) -> Any:
        return function(*args)

    async def scenario() -> None:
        manager = Mock()
        with (
            patch.object(service, "FormulaApiClient", FakeFormulaClient),
            patch.object(service.GszService, "userdata_manager", manager),
            patch.object(service.asyncio, "to_thread", side_effect=run_inline),
        ):
            assert await service.GszService._exist_gsz_user("玩家") is True
            assert await service.GszService.bind_userinfo("uid", "玩家") is True
            manager.update_userdata.assert_called_once_with(
                [{"uid": "uid", "username": "玩家"}]
            )
            manager.get_userdata.return_value = [{"username": "玩家"}]
            assert await service.GszService.get_userinfo_by_uid("uid") == "玩家"
            manager.get_userdata.return_value = []
            assert await service.GszService.get_userinfo_by_uid("missing") is None

        FakeFormulaClient.responses = {
            service.HISTORY_ENDPOINT: {"history": None, "qq": None}
        }
        with patch.object(service, "FormulaApiClient", FakeFormulaClient):
            assert await service.GszService.bind_userinfo("uid", "missing") is False

    asyncio.run(scenario())


@pytest.mark.parametrize("method", ["update_userdata", "get_userdata"])
def test_user_database_errors_return_false_or_none(
    method: str,
    formula_fixture: dict[str, Any],
) -> None:
    FakeFormulaClient.responses = {
        service.HISTORY_ENDPOINT: formula_fixture["history"]
    }
    manager = Mock()
    getattr(manager, method).side_effect = service.sqlite3.Error("db")

    async def run_inline(function: Any, *args: Any) -> Any:
        return function(*args)

    async def scenario() -> None:
        with (
            patch.object(service, "FormulaApiClient", FakeFormulaClient),
            patch.object(service.GszService, "userdata_manager", manager),
            patch.object(service.asyncio, "to_thread", side_effect=run_inline),
        ):
            if method == "update_userdata":
                assert await service.GszService.bind_userinfo("uid", "玩家") is False
            else:
                assert await service.GszService.get_userinfo_by_uid("uid") is None

    asyncio.run(scenario())


def test_user_image_avatar_failure_uses_placeholder(formula_fixture: dict[str, Any]) -> None:
    class AvatarFailureClient(FakeFormulaClient):
        def __init__(self, *_: Any, **__: Any) -> None:
            super().__init__()
            self._http.get = AsyncMock(
                side_effect=httpx.ConnectError(
                    "avatar offline", request=httpx.Request("GET", "https://avatar")
                )
            )

    AvatarFailureClient.responses = {
        service.HISTORY_ENDPOINT: formula_fixture["history"],
        service.RECORDS_ENDPOINT: formula_fixture["records"],
    }

    async def scenario() -> None:
        with (
            patch.object(service, "FormulaApiClient", AvatarFailureClient),
            patch.object(
                service,
                "convert_html_to_pic_with_chart_wait",
                AsyncMock(return_value=BytesIO(b"jpeg")),
            ) as render,
        ):
            output = await service.GszService.get_userinfo_by_name("玩家")
        assert output.getvalue() == b"jpeg"
        html = render.await_args.args[0]
        assert 'src="data:image/png;base64,"' in html
        assert "测试玩家\\u003c安全\\u003e" in html
        assert AvatarFailureClient.instance is not None
        assert AvatarFailureClient.instance.calls[1][1]["pageSize"] == 20

    asyncio.run(scenario())


def test_user_image_embeds_successful_avatar(formula_fixture: dict[str, Any]) -> None:
    class AvatarResponse:
        content = b"avatar-bytes"

        def raise_for_status(self) -> None:
            return None

    class AvatarClient(FakeFormulaClient):
        def __init__(self, *_: Any, **__: Any) -> None:
            super().__init__()
            self._http.get = AsyncMock(return_value=AvatarResponse())

    AvatarClient.responses = {
        service.HISTORY_ENDPOINT: formula_fixture["history"],
        service.RECORDS_ENDPOINT: formula_fixture["records"],
    }

    async def scenario() -> None:
        with (
            patch.object(service, "FormulaApiClient", AvatarClient),
            patch.object(
                service,
                "convert_html_to_pic_with_chart_wait",
                AsyncMock(return_value=BytesIO(b"jpeg")),
            ) as render,
        ):
            await service.GszService.get_userinfo_by_name("玩家")
        assert "data:image/png;base64,YXZhdGFyLWJ5dGVz" in render.await_args.args[0]

    asyncio.run(scenario())


def test_user_image_rejects_missing_user_and_customer_id(
    formula_fixture: dict[str, Any],
) -> None:
    async def scenario() -> None:
        with patch.object(service.GszService, "_get_history", AsyncMock(return_value=(None, None))):
            with pytest.raises(FormulaApiError, match="用户不存在"):
                await service.GszService.get_userinfo_by_name("missing")
        bad_history = {**formula_fixture["history"]["history"]}
        bad_history.pop("customerId")
        with patch.object(service.GszService, "_get_history", AsyncMock(return_value=(bad_history, None))):
            with pytest.raises(FormulaApiError, match="customerId"):
                await service.GszService.get_userinfo_by_name("bad")

    asyncio.run(scenario())


def test_hate_top_renders_first_ten_and_missing_user(formula_fixture: dict[str, Any]) -> None:
    records = [
        {**formula_fixture["partners"]["records"][0], "opponentName": f"对手{i}"}
        for i in range(12)
    ]
    FakeFormulaClient.responses = {
        service.PARTNER_STATS_ENDPOINT: {"records": records, "total": 12}
    }

    async def scenario() -> None:
        with (
            patch.object(service, "FormulaApiClient", FakeFormulaClient),
            patch.object(service.GszService, "_get_history", AsyncMock(return_value=({"customerId": "c"}, None))),
            patch.object(service, "convert_html_to_pic", AsyncMock(return_value=BytesIO(b"jpeg"))) as render,
        ):
            await service.GszService.get_rank_top("玩家")
        html = render.await_args.args[0]
        assert "对手9" in html and "对手10" not in html
        assert "37.5%" in html
        assert ">12<" in "".join(html.split())
        assert ">12.5<" not in "".join(html.split())
        assert "3" in html
        with patch.object(service.GszService, "_get_history", AsyncMock(return_value=(None, None))):
            with pytest.raises(FormulaApiError, match="用户不存在"):
                await service.GszService.get_rank_top("missing")
            with pytest.raises(FormulaApiError, match="用户不存在"):
                await service.GszService.get_rank_last("missing")

    asyncio.run(scenario())


def test_rate_search_prefers_exact_then_first_fuzzy(formula_fixture: dict[str, Any]) -> None:
    FakeFormulaClient.responses = {
        service.MAHJONG_LIST_ENDPOINT: formula_fixture["mahjong"]
    }
    with patch.object(service, "FormulaApiClient", FakeFormulaClient):
        assert service.GszService.get_rate_id("测试雀庄") == "mahjong-redacted"
        assert service.GszService.get_rate_id("不存在的精确名") == "mahjong-redacted"
    assert FakeFormulaClient.instance is not None
    assert FakeFormulaClient.instance.calls[0][1]["keyword"] == "不存在的精确名"


def test_rate_search_returns_none_for_empty_or_api_failure() -> None:
    with patch.object(service, "FormulaApiClient", FakeFormulaClient):
        FakeFormulaClient.responses = {
            service.MAHJONG_LIST_ENDPOINT: {"records": [], "total": 0}
        }
        assert service.GszService.get_rate_id("空雀庄") is None
        FakeFormulaClient.responses = {
            service.MAHJONG_LIST_ENDPOINT: FormulaApiError("/endpoint", "失败")
        }
        assert service.GszService.get_rate_id("失败雀庄") is None
        FakeFormulaClient.responses = {
            service.MAHJONG_LIST_ENDPOINT: {"records": [{"name": "无ID雀庄"}]}
        }
        assert service.GszService.get_rate_id("无ID雀庄") is None


def test_exist_rate_and_group_database_paths() -> None:
    with patch.object(service.GszService, "get_rate_id", return_value=None):
        assert service.GszService.exist_rate("雀庄") is False
    with patch.object(service.GszService, "get_rate_id", return_value="id"):
        assert service.GszService.exist_rate("雀庄") is True

    async def run_inline(function: Any, *args: Any) -> Any:
        return function(*args)

    async def scenario() -> None:
        manager = Mock()
        manager.get_ratedata.return_value = [{"groupId": "group", "rateId": "id"}]
        with (
            patch.object(service.GszService, "ratedata_manager", manager),
            patch.object(service.asyncio, "to_thread", side_effect=run_inline),
        ):
            assert await service.GszService.get_rateinfo_by_group_id("group") == {
                "groupId": "group", "rateId": "id"
            }
            manager.get_ratedata.return_value = []
            assert await service.GszService.get_rateinfo_by_group_id("empty") is None
            manager.get_ratedata.side_effect = service.sqlite3.Error("db")
            assert await service.GszService.get_rateinfo_by_group_id("bad") is None

        with patch.object(service.GszService, "_get_rate_id", AsyncMock(return_value=None)):
            assert await service.GszService.bind_rateinfo("group", "missing") is False

        manager = Mock()
        manager.update_ratedata.side_effect = service.sqlite3.Error("db")
        with (
            patch.object(service.GszService, "_get_rate_id", AsyncMock(return_value="id")),
            patch.object(service.GszService, "ratedata_manager", manager),
            patch.object(service.asyncio, "to_thread", side_effect=run_inline),
        ):
            assert await service.GszService.bind_rateinfo("group", "bad") is False

    asyncio.run(scenario())


def test_bind_rate_queries_once_and_preserves_database_shape() -> None:
    manager = Mock()
    manager.update_ratedata.return_value = True

    async def scenario() -> None:
        async def run_inline(function: Any, *args: Any) -> Any:
            return function(*args)

        with (
            patch.object(service.GszService, "_get_rate_id", AsyncMock(return_value="same-id")) as get_id,
            patch.object(service.GszService, "ratedata_manager", manager),
            patch.object(service.asyncio, "to_thread", side_effect=run_inline),
        ):
            assert await service.GszService.bind_rateinfo("group", "雀庄") is True
        get_id.assert_awaited_once_with("雀庄")
        manager.update_ratedata.assert_called_once_with(
            [{"groupId": "group", "rateId": "same-id", "rateName": "雀庄"}]
        )

    asyncio.run(scenario())


@pytest.mark.parametrize("goodwill, hate_value, expected", [(False, 12.5, 12), (True, -12.5, 12)])
def test_partner_values_render_as_integers(goodwill: bool, hate_value: float, expected: int) -> None:
    record = service._hate_render_record({"hateValue": hate_value}, goodwill=goodwill)
    assert type(record["hatred"]) is int
    assert record["hatred"] == expected
    html = service.jinja_env.get_template("hate.html").render(
        **service._render_style_context(), flag=int(goodwill), username="玩家", hate_data=[record],
    )
    assert f">{expected}<" in "".join(html.split())


def test_goodwill_uses_last_two_pages_and_lowest_hate_values() -> None:
    pages = {
        1: {"records": [{"opponentName": "top", "hateValue": 100}], "total": 25, "pages": 3, "size": 10},
        2: {"records": [{"opponentName": f"mid-{i}", "hateValue": i} for i in range(10)], "total": 25, "pages": 3, "size": 10},
        3: {"records": [{"opponentName": f"last-{i}", "hateValue": -10 + i} for i in range(5)], "total": 25, "pages": 3, "size": 10},
    }
    FakeFormulaClient.responses = {
        service.PARTNER_STATS_ENDPOINT: lambda params: pages[params["pageNo"]]
    }
    captured: dict[str, str] = {}

    async def fake_pic(content: str) -> BytesIO:
        captured["html"] = content
        return BytesIO(b"jpeg")

    async def scenario() -> None:
        with (
            patch.object(service, "FormulaApiClient", FakeFormulaClient),
            patch.object(service.GszService, "_get_history", AsyncMock(return_value=({"customerId": "c"}, None))),
            patch.object(service, "convert_html_to_pic", fake_pic),
        ):
            result = await service.GszService.get_rank_last("玩家")
            assert result.getvalue() == b"jpeg"

    asyncio.run(scenario())
    assert "last-0" in captured["html"]
    assert "mid-9" not in captured["html"]
    assert "10" in captured["html"]
    assert FakeFormulaClient.instance is not None
    assert [call[1]["pageNo"] for call in FakeFormulaClient.instance.calls] == [1, 2, 3]


def test_empty_partner_page_renders_without_extra_page_request() -> None:
    FakeFormulaClient.responses = {
        service.PARTNER_STATS_ENDPOINT: {"records": [], "total": 0, "pages": 0, "size": 10}
    }

    async def scenario() -> None:
        with (
            patch.object(service, "FormulaApiClient", FakeFormulaClient),
            patch.object(service.GszService, "_get_history", AsyncMock(return_value=({"customerId": "c"}, None))),
            patch.object(service, "convert_html_to_pic", AsyncMock(return_value=BytesIO(b"jpeg"))) as render,
        ):
            await service.GszService.get_rank_last("玩家")
        assert "玩家的好人榜" in render.await_args.args[0]

    asyncio.run(scenario())
    assert FakeFormulaClient.instance is not None
    assert len(FakeFormulaClient.instance.calls) == 1


def test_rank_list_uses_first_fifty_and_converts_points(formula_fixture: dict[str, Any]) -> None:
    records = formula_fixture["rank"]["records"] * 51
    FakeFormulaClient.responses = {
        service.GRADE_RANK_ENDPOINT: {"records": records, "total": 51}
    }

    async def scenario() -> None:
        with (
            patch.object(service, "FormulaApiClient", FakeFormulaClient),
            patch.object(service, "convert_html_to_pic", AsyncMock(return_value=BytesIO(b"jpeg"))) as render,
        ):
            await service.GszService.get_rank_list("mahjong-redacted")
        html = render.await_args.args[0]
        assert html.count("榜首玩家") == 50
        assert "30125" in html
        assert "0.0%" in html

    asyncio.run(scenario())
    assert FakeFormulaClient.instance is not None
    params = FakeFormulaClient.instance.calls[0][1]
    assert params["mahjongId"] == "mahjong-redacted"
    assert params["pageNo"] == 1 and params["pageSize"] == 50


def test_public_interface_signatures_and_async_forms() -> None:
    expected = {
        "exist_gsz_user": ("username", False),
        "bind_userinfo": ("uid, username", True),
        "get_userinfo_by_uid": ("uid", True),
        "get_userinfo_by_name": ("username", True),
        "get_rank_top": ("username", True),
        "get_rank_last": ("username", True),
        "get_rate_id": ("rate_name", False),
        "exist_rate": ("rate_name", False),
        "get_rateinfo_by_group_id": ("group_id", True),
        "bind_rateinfo": ("group_id, rate_name", True),
        "get_rank_list": ("rate_id", True),
    }
    for name, (parameters, is_async) in expected.items():
        method = getattr(service.GszService, name)
        assert ", ".join(inspect.signature(method).parameters) == parameters
        assert inspect.iscoroutinefunction(method) is is_async


@pytest.mark.render
@pytest.mark.parametrize("grade, rank", [(0, "无段位"), (8, "二段"), (14, "八段"), (15, "九段"), (16, "十段")])
@pytest.mark.parametrize("empty_records", [False, True])
def test_personal_grade_service_to_browser(
    formula_fixture: dict[str, Any], grade: int, rank: str, empty_records: bool,
) -> None:
    from playwright.async_api import async_playwright

    history = {**formula_fixture["history"]["history"], "grade": grade}
    FakeFormulaClient.responses = {
        service.HISTORY_ENDPOINT: {"history": history, "qq": None},
        service.RECORDS_ENDPOINT: {
            **formula_fixture["records"],
            "records": [] if empty_records else formula_fixture["records"]["records"],
        },
    }

    async def render_and_check(content: str, canvas_ids: list[str]) -> BytesIO:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch()
            page = await browser.new_page(viewport={"width": 1280, "height": 1080})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            await page.set_content(content, wait_until="load")
            await page.wait_for_function("window.__chartsReady === true")
            text = await page.locator("body").inner_text()
            assert rank in text
            assert "NaN" not in text and "undefined" not in text
            assert not errors
            if grade == 0:
                assert "升段条件" not in text and "成功通关" not in text
                assert "当前均顺" not in text and "顺位之和" not in text
            elif grade in (15, 16):
                assert "成功通关" in text
            else:
                assert "成功通关" not in text
                average, total = (2.5, 50) if grade == 8 else (1.9, 95)
                assert f"（≤{average}）可升段" in text
                assert f"（≤{total}）可升段" in text
            output = BytesIO(await page.screenshot(type="jpeg", full_page=True))
            await browser.close()
            return output

    async def scenario() -> BytesIO:
        with (
            patch.object(service, "FormulaApiClient", FakeFormulaClient),
            patch.object(service, "convert_html_to_pic_with_chart_wait", render_and_check),
        ):
            return await service.GszService.get_userinfo_by_name(history["name"])

    image = Image.open(asyncio.run(scenario()))
    image.verify()
    assert image.format == "JPEG"
    assert FakeFormulaClient.instance is not None
    assert FakeFormulaClient.instance.calls[1][1]["pageSize"] == (20 if grade == 8 else 50)


@pytest.mark.render
def test_four_template_render_chains_produce_nonempty_jpegs(formula_fixture: dict[str, Any]) -> None:
    context = service._personal_render_context(
        formula_fixture["history"]["history"],
        formula_fixture["records"]["records"],
    )
    user_html = service.jinja_env.get_template("gsz_info.html").render(
        **service._render_style_context(),
        chart_js_content=service._read_static("chart.js"),
        userpic=None,
        **context,
    )
    hate_html = [
        service.jinja_env.get_template("hate.html").render(
            **service._render_style_context(),
            flag=flag,
            username="测试玩家",
            hate_data=[
                service._hate_render_record(record, goodwill=bool(flag))
                for record in formula_fixture["partners"]["records"]
            ],
        )
        for flag in (0, 1)
    ]
    rank_html = service.jinja_env.get_template("rank_list.html").render(
        **service._render_style_context(),
        rank_data=[
            service._rank_render_record(formula_fixture["rank"]["records"][0])
        ],
    )

    async def render_all() -> list[BytesIO]:
        return [
            await service.convert_html_to_pic_with_chart_wait(
                user_html, ["radarChart", "doughnutChart", "rankTrendChart"]
            ),
            await service.convert_html_to_pic(hate_html[0]),
            await service.convert_html_to_pic(hate_html[1]),
            await service.convert_html_to_pic(rank_html),
        ]

    with patch.object(service.logger, "warning") as browser_warning:
        outputs = asyncio.run(render_all())
    assert not any(
        "浏览器JS错误" in str(call.args[0])
        for call in browser_warning.call_args_list
    )
    for output in outputs:
        output.seek(0)
        image = Image.open(output)
        image.load()
        assert image.format == "JPEG"
        assert image.width >= 1000 and image.height >= 500
        assert sum(ImageStat.Stat(image.convert("L")).var) > 1


@pytest.mark.live
def test_formula_api_and_four_images_live_smoke() -> None:
    if os.getenv("GSZ_RUN_LIVE_TESTS") != "1":
        pytest.skip("set GSZ_RUN_LIVE_TESTS=1 to run live formula smoke tests")
    username = os.environ["GSZ_SMOKE_USERNAME"]
    rate_name = os.environ["GSZ_SMOKE_RATE_NAME"]

    async def scenario() -> list[BytesIO]:
        async with service.FormulaApiClient() as client:
            history_result = await client.get(service.HISTORY_ENDPOINT, params={"name": username})
            history, _ = service._history_from_result(history_result)
            assert history is not None
            customer_id = history["customerId"]
            await client.get(service.PARTNER_STATS_ENDPOINT, params={"customerId": customer_id, "pageNo": 1, "pageSize": 10})
            await client.get(service.RECORDS_ENDPOINT, params={"customerId": customer_id, "pageNo": 1, "pageSize": 10})
            mahjong = await client.get(service.MAHJONG_LIST_ENDPOINT, params={"pageNo": 1, "pageSize": 9, "keyword": rate_name, "provinceName": "全国"})
            rate_id = mahjong["records"][0]["id"]
            await client.get(service.GRADE_RANK_ENDPOINT, params={"mahjongId": rate_id, "scope": "mahjong", "pageNo": 1, "pageSize": 50, "orderColumns": "", "orderTypes": ""})
        return [
            await service.GszService.get_userinfo_by_name(username),
            await service.GszService.get_rank_top(username),
            await service.GszService.get_rank_last(username),
            await service.GszService.get_rank_list(str(rate_id)),
        ]

    for output in asyncio.run(scenario()):
        output.seek(0)
        image = Image.open(output)
        image.verify()
        assert image.format == "JPEG"


@pytest.mark.live
def test_grade_dictionary_matches_website() -> None:
    if os.getenv("GSZ_RUN_LIVE_TESTS") != "1":
        pytest.skip("set GSZ_RUN_LIVE_TESTS=1 to verify the website grade dictionary")

    async def scenario() -> None:
        async with service.FormulaApiClient() as client:
            result = await client.get("/sys/dictType/getDict/match_grades")
        items = result["items"]
        actual = {int(item["value"]): item["text"] for item in items}
        assert len(actual) == len(items), "网站段位字典包含重复编号"
        expected = {grade: rule.name for grade, rule in service.GRADE_RULES.items()}
        assert actual == expected, "网站段位字典已变化，请同时核对段位名称和前端升段门槛"

    asyncio.run(scenario())
