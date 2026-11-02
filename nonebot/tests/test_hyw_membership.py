"""Real urllib login, cookies, GB18030 pages and exact-card lookup on localhost."""

from contextlib import contextmanager
from dataclasses import FrozenInstanceError, replace
from datetime import date
from decimal import Decimal, localcontext
from html import escape
from http.client import HTTPException
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
from pathlib import Path
import sys
import threading
from types import MappingProxyType
from urllib.error import URLError
from urllib.parse import parse_qs, urlencode, urlsplit

from pydantic import SecretStr
import pytest


MODULE_PATH = Path(__file__).parents[1] / "src/plugins/hyw_assist/hyw_membership.py"
SPEC = importlib.util.spec_from_file_location("hyw_membership_testmodule", MODULE_PATH)
membership = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = membership
SPEC.loader.exec_module(membership)

CARD = "004637"
USERNAME = "测试店员"
PASSWORD = "test-password-中文"


def store_config(**overrides):
    backend = dict(base_url="https://billing.example.invalid/shop", username=USERNAME,
                   password=PASSWORD, timeout_seconds=15, allow_http=False)
    backend.update(overrides)
    return {"ledger_id": "initial", "billing": {}, "backend": backend}


def login_page(action="login.php", method="post"):
    return (f'<form method="{method}" action="{action}"><input name="username">'
            '<input name="password" type="password"><input type="hidden" '
            'name="csrf" value="test-token"><input type="hidden"></form>')


def listing(cards, *, total=None, size=2, next_page=None, detail_prefix=""):
    total = len(cards) if total is None else total
    rows = []
    for card in cards:
        href = detail_prefix + "member_post.php?" + urlencode({"pri_mumber": card})
        rows.append(f'<tr><td><a href="member_edit.php">编辑</a><a href="{escape(href)}">学生卡：{card}</a></td>'
                    '<td>测试会员</td><td>其他</td><td>其他</td>'
                    '<td><img alt="已停用"></td></tr>')
    next_link = ""
    if next_page is not None:
        href = "member_all.php?" + urlencode({"page_info": next_page, "ss_mumber": CARD})
        next_link = f'<a href="{escape(href)}">下一页</a>'
    return (f'<input name="ss_mumber"><p>当前共有会员:{total}人 / 每页显示{size}人</p>'
            f'<table><tr><th>会员列表</th></tr>{"".join(rows)}</table>{next_link}')


def details(**overrides):
    values = {"会员号": CARD, "会员类别": "学生卡", "会员姓名": "测试会员", "到期日期": "2000-01-01"}
    values.update(overrides)
    return "<table><tr><td>备注</td><td>测试资料</td></tr>" + "".join(f"<tr><td>{key}：</td><td>{value}</td></tr>"
                              for key, value in values.items()) + "</table>"


def discounts(text="台费：8折 自动计费：7.5折", category="学生卡"):
    return f"<table><tr><td>{category}</td><td>其他</td><td>{text}</td></tr></table>"


@contextmanager
def backend_server(overrides=None):
    overrides = overrides or {}
    calls = []
    pages = {
        ("GET", ""): login_page(),
        ("GET", "main.php"): '<a href="logout.php">退出</a>',
        ("POST", "member_all.php"): listing(["0046370", "00463"], total=5, next_page=2),
        ("GET", "member_all.php", "2"): listing(["4637", "00001"], total=5, next_page=3),
        ("GET", "member_all.php", "3"): listing([CARD], total=5),
        ("GET", "member_post.php"): details(),
        ("GET", "hylb.php"): discounts(),
    }
    pages.update(overrides)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            self.respond("GET")

        def do_POST(self):
            self.respond("POST")

        def respond(self, method):
            parts = urlsplit(self.path)
            path = parts.path.removeprefix("/shop/")
            query = parse_qs(parts.query)
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            fields = parse_qs(body.decode("ascii"), encoding="gb18030") if body else {}
            calls.append((method, path, fields, query, self.headers.get("Cookie")))
            if method == "POST" and path == "login.php":
                expected = {"username": [USERNAME], "password": [PASSWORD],
                            "csrf": ["test-token"], "imageField.x": ["0"], "imageField.y": ["0"]}
                if fields != expected:
                    self.send_error(401)
                    return
                self.send_response(302)
                self.send_header("Set-Cookie", "session=local-test; Path=/shop/")
                self.send_header("Location", "main.php")
                self.end_headers()
                return
            if path and self.headers.get("Cookie") != "session=local-test":
                response = login_page()
            else:
                key = (method, path, query["page_info"][0]) if "page_info" in query else (method, path)
                response = pages.get(key, "missing")
            if isinstance(response, tuple):
                status, response = response
            else:
                status = 200
            data = response.encode("gb18030") if isinstance(response, str) else response
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=gb2312")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=.01), daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/shop/"
        config = membership.BackendConfig.from_store("store-a", store_config(base_url=url, allow_http=True))
        yield config, calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_store_snapshot_to_real_http_lookup():
    with backend_server() as (config, calls):
        result = membership.fetch_member_discounts(config, CARD)
    assert result.store_id == "store-a"
    assert result.card_number == CARD
    assert result.member_name == "测试会员"
    assert result.member_category == "学生卡"
    assert result.status == "已停用"
    assert result.expires_on == date(2000, 1, 1)
    assert result.cap_multiplier == Decimal("0.8")
    assert result.billing_multiplier == Decimal("0.75")
    query_call = next(call for call in calls if call[0:2] == ("POST", "member_all.php"))
    assert query_call[2] == {"ss_mumber": [CARD], "Submit": ["查询"]}
    assert [call[3].get("page_info") for call in calls if call[1] == "member_all.php"] == [None, ["2"], ["3"]]
    assert all(call[4] == "session=local-test" for call in calls if call[1] not in ("", "login.php"))


def test_two_stores_keep_results_and_sessions_separate():
    with backend_server() as (first, _), backend_server() as (second, calls):
        second = replace(second, store_id="store-b")
        assert membership.fetch_member_discounts(first, CARD).store_id == "store-a"
        assert membership.fetch_member_discounts(second, CARD).store_id == "store-b"
        assert sum(path == "login.php" for _, path, *_ in calls) == 1


def test_store_mapping_and_secrets(monkeypatch):
    monkeypatch.setenv("HYW_BACKEND_PASSWORD", "ignored-environment-password")
    store = store_config(password=SecretStr(PASSWORD))
    store["backend"] = MappingProxyType(store["backend"])
    config = membership.BackendConfig.from_store("store-a", MappingProxyType(store))
    assert config.base_url == "https://billing.example.invalid/shop/"
    assert config.password.get_secret_value() == PASSWORD
    assert PASSWORD not in repr(config) and USERNAME not in repr(config)
    with pytest.raises(FrozenInstanceError):
        config.store_id = "other"


def test_explicit_unconfigured_backend_has_no_session(monkeypatch):
    monkeypatch.setattr(membership, "_Session", lambda *_: pytest.fail("must not access backend"))
    assert membership.BackendConfig.from_store("store-a", store_config(base_url=None, username=None, password=None)) is None


@pytest.mark.parametrize("store", [None, {}, {"backend": None}, {"backend": []},
    {"backend": {"base_url": None, "username": None, "password": None}},
    {"backend": {**store_config()["backend"], "credential_ref": "SECRET-MARKER"}}])
def test_reject_incomplete_or_unknown_configuration(store):
    with pytest.raises(ValueError) as error:
        membership.BackendConfig.from_store("store-a", store)
    assert "SECRET-MARKER" not in str(error.value)


@pytest.mark.parametrize("overrides", [
    {"base_url": None}, {"username": None}, {"password": None},
    {"username": ""}, {"username": " "}, {"username": 1},
    {"password": ""}, {"password": 123},
    {"timeout_seconds": True}, {"timeout_seconds": "15"}, {"timeout_seconds": 0},
    {"timeout_seconds": -1}, {"timeout_seconds": float("nan")}, {"timeout_seconds": float("inf")},
    {"allow_http": 1}, {"allow_http": "false"},
    {"base_url": 1}, {"base_url": "ftp://example.invalid"}, {"base_url": "/relative"},
    {"base_url": "https://user:SECRET-MARKER@example.invalid/"},
    {"base_url": "https://example.invalid/?token=SECRET-MARKER"},
    {"base_url": "https://example.invalid/#SECRET-MARKER"},
    {"base_url": "https://example.invalid:SECRET-MARKER/"},
    {"base_url": "https://[invalid/"}, {"base_url": " https://example.invalid/"},
    {"base_url": "https://example.invalid/\n"}, {"base_url": "https://example.invalid/a b"},
    {"base_url": "http://example.invalid/"},
])
def test_reject_bad_backend_values_without_exposing_input(overrides):
    with pytest.raises(ValueError) as error:
        membership.BackendConfig.from_store("store-a", store_config(**overrides))
    assert "SECRET-MARKER" not in str(error.value)


@pytest.mark.parametrize("store_id", [None, 1, "", " store", "store "])
@pytest.mark.parametrize("disabled", [False, True])
def test_store_id_is_required_even_when_backend_disabled(store_id, disabled):
    store = store_config(**dict(base_url=None, username=None, password=None)) if disabled else store_config()
    with pytest.raises(ValueError):
        membership.BackendConfig.from_store(store_id, store)


@pytest.mark.parametrize("overrides", [{"timeout_seconds": False}, {"allow_http": 1}])
def test_disabled_backend_still_validates_options(overrides):
    with pytest.raises(ValueError):
        membership.BackendConfig.from_store("store-a", store_config(base_url=None, username=None, password=None, **overrides))


@pytest.mark.parametrize("card", [None, 4637, "", " 4637", "4637 ", "４６３７", "4637\n", "abc"])
def test_card_validation_precedes_requests(monkeypatch, card):
    config = membership.BackendConfig.from_store("store-a", store_config())
    monkeypatch.setattr(membership, "_Session", lambda *_: pytest.fail("invalid input made a request"))
    with pytest.raises(ValueError):
        membership.fetch_member_discounts(config, card)


def test_invalid_config_is_not_an_unconfigured_backend():
    with pytest.raises(ValueError):
        membership.fetch_member_discounts(None, CARD)


@pytest.mark.parametrize("overrides, error", [
    ({("GET", ""): "<html></html>"}, membership.BackendDataError),
    ({("GET", ""): login_page(method="get")}, membership.BackendDataError),
    ({("GET", ""): login_page() + login_page()}, membership.BackendDataError),
    ({("GET", ""): login_page(action="https://other.invalid/login.php")}, membership.BackendRequestError),
    ({("GET", "main.php"): login_page()}, membership.AuthenticationError),
    ({("GET", "main.php"): "<p>denied</p>"}, membership.AuthenticationError),
    ({("POST", "member_all.php"): login_page()}, membership.AuthenticationError),
    ({("POST", "member_all.php"): (503, "SECRET-MARKER")}, membership.BackendRequestError),
    ({("POST", "member_all.php"): b"\x81"}, membership.BackendDataError),
    ({("POST", "member_all.php"): listing([], total=0)}, membership.MemberNotFoundError),
    ({("POST", "member_all.php"): listing([CARD], detail_prefix="https://other.invalid/")}, membership.BackendRequestError),
    ({("GET", "member_post.php"): details(会员号="4637")}, membership.BackendDataError),
    ({("GET", "member_post.php"): details(到期日期="invalid")}, membership.BackendDataError),
    ({("GET", "member_post.php"): details() + details()}, membership.BackendDataError),
    ({("GET", "hylb.php"): discounts(category="其他卡")}, membership.BackendDataError),
    ({("GET", "hylb.php"): discounts() + discounts()}, membership.BackendDataError),
])
def test_full_lookup_failures(overrides, error):
    with backend_server(overrides) as (config, _):
        with pytest.raises(error) as caught:
            membership.fetch_member_discounts(config, CARD)
    assert "SECRET-MARKER" not in str(caught.value)
    assert PASSWORD not in str(caught.value)


@pytest.mark.parametrize("page", [
    "<p>no pagination</p>", listing([CARD], size=0),
    listing([CARD], total=2),
    listing([CARD, CARD], total=2),
    listing([CARD], total=3),
    listing([CARD], total=1).replace('name="ss_mumber"', 'name="other"'),
    listing([CARD]).replace("pri_mumber=004637", "pri_mumber=4637"),
    listing([CARD]).replace("学生卡：004637", "malformed-card"),
    listing([CARD]).replace("测试会员", ""),
])
def test_incomplete_or_conflicting_member_pages(page):
    with backend_server({("POST", "member_all.php"): page}) as (config, _):
        with pytest.raises(membership.BackendDataError):
            membership.fetch_member_discounts(config, CARD)


@pytest.mark.parametrize("page", [
    listing(["0046370", "00463"], total=4, next_page=3),
    listing(["0046370", "00463"], total=4, next_page=2).replace("ss_mumber=004637", "ss_mumber=other"),
])
def test_pagination_must_preserve_exact_query(page):
    with backend_server({("POST", "member_all.php"): page}) as (config, _):
        with pytest.raises(membership.BackendDataError):
            membership.fetch_member_discounts(config, CARD)


@pytest.mark.parametrize("second", [listing(["4637", "00001"], total=6, next_page=3),
                                    listing(["0046370", "00001"], total=5, next_page=3)])
def test_changed_or_duplicate_pages_are_not_used(second):
    with backend_server({("GET", "member_all.php", "2"): second}) as (config, _):
        with pytest.raises(membership.BackendDataError):
            membership.fetch_member_discounts(config, CARD)


def test_duplicate_non_target_rows_are_incomplete_history():
    page = listing(["00001", "00001"], total=2)
    with backend_server({("POST", "member_all.php"): page}) as (config, _):
        with pytest.raises(membership.BackendDataError):
            membership.fetch_member_discounts(config, CARD)


def test_empty_status_does_not_prevent_using_discounts():
    page = listing([CARD]).replace('alt="已停用"', 'alt=""')
    with backend_server({("POST", "member_all.php"): page}) as (config, _):
        result = membership.fetch_member_discounts(config, CARD)
    assert result.status == ""
    assert result.cap_multiplier == Decimal(".8")


@pytest.mark.parametrize("text, cap, billing", [("台费：折 自动计费：10折", "1", "1"),
    ("台费：0折 自动计费：0折", "0", "0"), ("台费：9.25折 自动计费：0.5折", ".925", ".05")])
def test_discount_coefficients_are_exact_and_allow_zero(text, cap, billing):
    with backend_server({("GET", "hylb.php"): discounts(text)}) as (config, _):
        with localcontext() as context:
            context.prec = 1
            result = membership.fetch_member_discounts(config, CARD)
    assert result.cap_multiplier == Decimal(cap)
    assert result.billing_multiplier == Decimal(billing)


@pytest.mark.parametrize("text", ["自动计费：8折", "台费：8折 台费：9折 自动计费：8折",
    "台费：NaN折 自动计费：8折", "台费：Infinity折 自动计费：8折",
    "台费：11折 自动计费：8折", "台费：-1折 自动计费：8折", "台费：错误折 自动计费：8折"])
def test_invalid_discounts_do_not_become_full_price(text):
    with backend_server({("GET", "hylb.php"): discounts(text)}) as (config, _):
        with pytest.raises(membership.BackendDataError):
            membership.fetch_member_discounts(config, CARD)


@pytest.mark.parametrize("error", [URLError("SECRET-MARKER"), OSError("SECRET-MARKER"), HTTPException("SECRET-MARKER")])
def test_transport_errors_are_redacted(monkeypatch, error):
    config = membership.BackendConfig.from_store("store-a", store_config())
    session = membership._Session(config)

    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(session.opener, "open", fail)
    with pytest.raises(membership.BackendRequestError) as caught:
        session.request("")
    assert "SECRET-MARKER" not in str(caught.value)


@pytest.mark.parametrize("target", ["https://other.invalid/login.php", "https://user@billing.example.invalid/login.php"])
def test_credential_redirect_is_rejected(target):
    config = membership.BackendConfig.from_store("store-a", store_config())
    handler = membership._OriginRedirect(membership._origin(config.base_url))
    with pytest.raises(membership.BackendRequestError):
        handler.redirect_request(None, None, 302, "", {}, target)
