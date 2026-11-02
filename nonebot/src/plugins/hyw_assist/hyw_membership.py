"""Read membership using one store's injected group-config snapshot.

cap_multiplier applies to all caps; billing_multiplier applies to the hourly rate.
Status and expiry are returned as facts and do not restrict either discount.
This module reads no configuration files or environment variables and changes no bill.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from http.client import HTTPException
from http.cookiejar import CookieJar
import math
import re
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit
from urllib.request import HTTPCookieProcessor, HTTPRedirectHandler, Request, build_opener

from pydantic import SecretStr


class MembershipError(Exception):
    """Base error with a message safe to display without credentials."""


class AuthenticationError(MembershipError):
    """Login failed, permission denied, or the session expired."""


class MemberNotFoundError(MembershipError):
    """No exact card number was found."""


class BackendDataError(MembershipError):
    """The returned page or discount configuration cannot be interpreted."""


class BackendRequestError(MembershipError):
    """A request failed or would leave the configured origin."""


def _origin(url):
    parts = urlsplit(url)
    port = parts.port if parts.port is not None else (443 if parts.scheme == "https" else 80)
    return parts.scheme, parts.hostname, port


def _validate_options(timeout_seconds, allow_http):
    if type(allow_http) is not bool:
        raise ValueError("backend.allow_http 必须是布尔值。")
    if (type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds)
            or timeout_seconds <= 0):
        raise ValueError("backend.timeout_seconds 必须是有限的正数秒。")


def _validate_store_id(store_id):
    if not isinstance(store_id, str) or not store_id or store_id != store_id.strip():
        raise ValueError("门店 ID 必须是无首尾空白的非空字符串。")


@dataclass(frozen=True, kw_only=True)
class BackendConfig:
    store_id: str
    base_url: str
    username: str = field(repr=False)
    password: SecretStr = field(repr=False)
    timeout_seconds: float = 15
    allow_http: bool = False

    def __post_init__(self):
        _validate_store_id(self.store_id)
        _validate_options(self.timeout_seconds, self.allow_http)
        if not isinstance(self.base_url, str):
            raise ValueError("后台地址必须是 HTTP(S) 目录地址。")
        try:
            parts = urlsplit(self.base_url)
            _origin(self.base_url)
        except ValueError:
            raise ValueError("后台地址或端口格式不正确。") from None
        if (parts.scheme not in ("http", "https") or not parts.hostname
                or parts.username is not None or parts.password is not None
                or parts.query or parts.fragment or self.base_url != self.base_url.strip()
                or any(ord(char) < 33 for char in self.base_url)):
            raise ValueError("后台地址必须是无凭据、查询参数和片段的 HTTP(S) 目录地址。")
        if parts.scheme == "http" and not self.allow_http:
            raise ValueError("HTTP 后台须在该门店配置中显式设置 backend.allow_http=true。")
        if not isinstance(self.username, str) or not self.username.strip():
            raise ValueError("后台用户名不能为空。")
        if not isinstance(self.password, SecretStr) or not self.password.get_secret_value():
            raise ValueError("后台密码不能为空。")
        object.__setattr__(self, "base_url", self.base_url.rstrip("/") + "/")

    @classmethod
    def from_store(cls, store_id: str, store: Mapping) -> "BackendConfig | None":
        """Convert stores[store_id]; an explicit all-null credential triple disables lookup."""
        if not isinstance(store, Mapping) or not isinstance(store.get("backend"), Mapping):
            raise ValueError("门店 backend 必须是完整配置对象。")
        backend = store["backend"]
        if set(backend) != {"base_url", "username", "password", "timeout_seconds", "allow_http"}:
            raise ValueError("门店 backend 配置字段缺失或包含未知字段。")
        credentials = [backend[name] for name in ("base_url", "username", "password")]
        if all(value is None for value in credentials):
            _validate_store_id(store_id)
            _validate_options(backend["timeout_seconds"], backend["allow_http"])
            return None
        if any(value is None for value in credentials):
            raise ValueError("后台地址、用户名和密码须全部填写或全部为 null。")
        password = backend["password"]
        if isinstance(password, str):
            password = SecretStr(password)
        return cls(store_id=store_id, base_url=backend["base_url"], username=backend["username"],
                   password=password, timeout_seconds=backend["timeout_seconds"],
                   allow_http=backend["allow_http"])


@dataclass(frozen=True)
class MemberDiscounts:
    store_id: str
    card_number: str
    member_name: str
    member_category: str
    status: str
    expires_on: date
    cap_multiplier: Decimal
    billing_multiplier: Decimal


@dataclass
class _Element:
    tag: str
    attrs: dict = field(default_factory=dict)
    children: list = field(default_factory=list)

    @property
    def text(self):
        return " ".join((child.text if isinstance(child, _Element) else child)
                        for child in self.children).strip()

    def find(self, tag):
        for child in self.children:
            if isinstance(child, _Element):
                if child.tag == tag:
                    yield child
                yield from child.find(tag)


class _Page(HTMLParser):
    """A small DOM for the observed login forms and HTML tables."""

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = _Element("document")
        self.stack = [self.root]
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        element = _Element(tag, dict(attrs))
        self.stack[-1].children.append(element)
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input",
                       "link", "meta", "param", "source", "track", "wbr"}:
            self.stack.append(element)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def _cells(row):
    return [child for child in row.children
            if isinstance(child, _Element) and child.tag in ("td", "th")]


def _login_forms(page):
    return [form for form in page.root.find("form")
            if {"username", "password"} <= {node.attrs.get("name") for node in form.find("input")}]


class _OriginRedirect(HTTPRedirectHandler):
    def __init__(self, origin):
        self.origin = origin

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if _origin(newurl) != self.origin or urlsplit(newurl).username is not None:
            raise BackendRequestError("已拒绝向其他来源重定向，未转发登录凭据。")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class _Session:
    def __init__(self, config):
        self.config = config
        self.opener = build_opener(HTTPCookieProcessor(CookieJar()),
                                  _OriginRedirect(_origin(config.base_url)))

    def request(self, path, fields=None):
        url = urljoin(self.config.base_url, path)
        if _origin(url) != _origin(self.config.base_url) or urlsplit(url).username is not None:
            raise BackendRequestError("已拒绝请求配置地址之外的来源。")
        try:
            data = None if fields is None else urlencode(fields, encoding="gb18030").encode("ascii")
            request = Request(url, data=data, headers={"User-Agent": "hyw-membership/1.0"})
            with self.opener.open(request, timeout=self.config.timeout_seconds) as response:
                html = response.read().decode("gb18030")
        except HTTPError as error:
            raise BackendRequestError(f"后台返回 HTTP {error.code}。") from None
        except (URLError, OSError, HTTPException):
            raise BackendRequestError("后台请求失败，请检查地址、网络和访问权限。") from None
        except UnicodeError:
            raise BackendDataError("后台页面不是预期的 GB2312/GB18030 编码。") from None
        return _Page(html)

    def authenticated(self, path, fields=None):
        page = self.request(path, fields)
        if _login_forms(page):
            raise AuthenticationError("后台登录已失效或没有访问权限。")
        return page

    def login(self):
        forms = _login_forms(self.request(""))
        if len(forms) != 1 or forms[0].attrs.get("method", "").lower() != "post":
            raise BackendDataError("未找到预期的后台登录表单。")
        form = forms[0]
        fields = {node.attrs["name"]: node.attrs.get("value", "")
                  for node in form.find("input")
                  if node.attrs.get("type", "").lower() == "hidden" and node.attrs.get("name")}
        fields.update(username=self.config.username, password=self.config.password.get_secret_value())
        fields.update({"imageField.x": "0", "imageField.y": "0"})
        self.request(form.attrs.get("action", ""), fields)
        main = self.authenticated("main.php")
        if not any(urlsplit(link.attrs.get("href", "")).path.endswith("/logout.php")
                   or link.attrs.get("href") == "logout.php" for link in main.root.find("a")):
            raise AuthenticationError("后台登录未成功或账号无访问权限。")


def _member_matches(page, card_number):
    if not any(node.attrs.get("name") == "ss_mumber" for node in page.root.find("input")):
        raise BackendDataError("会员查询页面结构不符或账号无访问权限。")
    matches = []
    cards = []
    for row in page.root.find("tr"):
        cells = _cells(row)
        if len(cells) < 5:
            continue
        for link in cells[0].find("a"):
            href = link.attrs.get("href", "")
            if urlsplit(href).path.rsplit("/", 1)[-1] != "member_post.php":
                continue
            visible = re.fullmatch(r"(.+?)\s*[:：]\s*(\S+)", link.text)
            linked = parse_qs(urlsplit(href).query).get("pri_mumber")
            if not visible or linked != [visible[2]]:
                raise BackendDataError("会员详情链接与显示卡号不一致。")
            cards.append(visible[2])
            if visible[2] == card_number:
                status = " ".join(image.attrs.get("alt", "") for image in cells[4].find("img")).strip()
                if not cells[1].text:
                    raise BackendDataError("会员姓名缺失。")
                matches.append((href, visible[1].strip(), cells[1].text, status))
    return matches, cards


def _pagination(page):
    matches = re.findall(r"当前共有会员\s*[:：]\s*(\d+)\s*人\s*/\s*每页显示\s*(\d+)\s*人",
                         page.root.text)
    if len(matches) != 1 or int(matches[0][1]) == 0:
        raise BackendDataError("会员查询分页信息缺失或不正确。")
    return tuple(map(int, matches[0]))


def _find_member(session, card_number):
    page = session.authenticated("member_all.php", {"ss_mumber": card_number, "Submit": "查询"})
    total, page_size = expected = _pagination(page)
    page_count = max(1, (total + page_size - 1) // page_size)
    matches = []
    seen_cards = set()
    for page_number in range(1, page_count + 1):
        if _pagination(page) != expected:
            raise BackendDataError("查询期间会员分页信息发生变化，请重新查询。")
        page_matches, cards = _member_matches(page, card_number)
        expected_rows = min(page_size, total - (page_number - 1) * page_size)
        if (len(cards) != expected_rows or len(set(cards)) != len(cards)
                or seen_cards.intersection(cards)):
            raise BackendDataError("会员分页记录数量不符或重复，查询结果不完整。")
        seen_cards.update(cards)
        matches.extend(page_matches)
        if page_number < page_count:
            next_links = set()
            for link in page.root.find("a"):
                href = link.attrs.get("href", "")
                parts = urlsplit(href)
                query = parse_qs(parts.query)
                if (parts.path.rsplit("/", 1)[-1] == "member_all.php"
                        and query.get("page_info") == [str(page_number + 1)]
                        and query.get("ss_mumber") == [card_number]):
                    next_links.add(href)
            if len(next_links) != 1:
                raise BackendDataError("未找到唯一的下一页查询链接，查询结果不完整。")
            page = session.authenticated(next_links.pop())
    if not matches:
        raise MemberNotFoundError("未找到精确匹配该卡号的会员。")
    return matches[0]


def _member_details(page, card_number, category, member_name):
    wanted = {"会员号", "会员类别", "会员姓名", "到期日期"}
    values = {}
    for row in page.root.find("tr"):
        cells = _cells(row)
        for left, right in zip(cells, cells[1:]):
            label = re.sub(r"\s+", "", left.text).rstrip(":：")
            if label in wanted:
                if label in values:
                    raise BackendDataError("会员详情字段重复。")
                values[label] = right.text.strip()
    if (values.keys() != wanted or values["会员号"] != card_number
            or values["会员类别"] != category or values["会员姓名"] != member_name):
        raise BackendDataError("会员详情字段缺失或与查询结果不一致。")
    try:
        return date.fromisoformat(values["到期日期"])
    except ValueError:
        raise BackendDataError("会员到期日期格式不正确。") from None


def _multiplier(text, label):
    matches = re.findall(r"(?<!\S)" + re.escape(label) + r"\s*[:：]\s*([^折]*)折", text)
    if len(matches) != 1:
        raise BackendDataError(f"{label}折扣字段缺失或不唯一。")
    if not matches[0].strip():
        return Decimal("1")
    try:
        value = Decimal(matches[0].strip())
    except InvalidOperation:
        raise BackendDataError(f"{label}折扣不是有效数字。") from None
    if not value.is_finite() or not 0 <= value <= 10:
        raise BackendDataError(f"{label}折扣必须在 0 到 10 折之间。")
    sign, digits, exponent = value.as_tuple()
    return Decimal((sign, digits, exponent - 1))


def _discounts(page, category):
    rows = [_cells(row) for row in page.root.find("tr")]
    matches = [cells for cells in rows if len(cells) >= 3 and cells[0].text == category]
    if len(matches) != 1:
        raise BackendDataError("未找到唯一的会员类别折扣配置。")
    text = matches[0][2].text
    return _multiplier(text, "台费"), _multiplier(text, "自动计费")


def fetch_member_discounts(config: BackendConfig, card_number: str) -> MemberDiscounts:
    """Log in and read one exact card; retain neither credentials nor cookies on disk."""
    if not isinstance(config, BackendConfig):
        raise ValueError("会员查询必须使用门店 BackendConfig。")
    if not isinstance(card_number, str) or re.fullmatch(r"[0-9]+", card_number) is None:
        raise ValueError("会员卡号必须是 ASCII 数字字符串，请保留前导零。")
    session = _Session(config)
    session.login()
    href, category, name, status = _find_member(session, card_number)
    expires = _member_details(session.authenticated(href), card_number, category, name)
    cap, billing = _discounts(session.authenticated("hylb.php"), category)
    return MemberDiscounts(config.store_id, card_number, name, category, status, expires, cap, billing)
