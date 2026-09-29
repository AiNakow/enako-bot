"""仅抓拍所需的萤石 API；不依赖父目录测试脚本。"""
import time
from urllib.parse import urlsplit

import requests


class CounterError(RuntimeError):
    """配置、抓拍或推理失败；失败绝不表示人数为 0。"""


class ApiError(CounterError):
    def __init__(self, code):
        self.code = str(code)
        safe_code = self.code if self.code.isdecimal() else "unknown"
        super().__init__(f"萤石 API 业务码 {safe_code}；请核对设备在线状态、权限及抓拍能力。")


class CaptureClient:
    def __init__(self, settings):
        self.settings = settings
        self.session = requests.Session()
        self.token = settings.access_token
        self.expires_at = 0
        self.last_capture = {}

    def close(self):
        self.session.close()

    def post(self, endpoint, data):
        try:
            with self.session.post("https://open.ys7.com/api/lapp/" + endpoint,
                                   data=data, timeout=(10, self.settings.timeout),
                                   allow_redirects=False) as response:
                if response.status_code != 200:
                    raise CounterError(f"萤石 API HTTP {response.status_code}。")
                body = response.json()
        except requests.RequestException:
            raise CounterError("萤石 API 网络请求失败。") from None
        except ValueError:
            raise CounterError("萤石 API 响应不是 JSON。") from None
        if not isinstance(body, dict):
            raise CounterError("萤石 API 响应结构异常。")
        if str(body.get("code")) != "200":
            raise ApiError(body.get("code"))
        return body.get("data")

    def get_token(self, refresh=False):
        if self.settings.access_token:
            return self.settings.access_token
        if not refresh and self.token and time.time() + 60 < self.expires_at:
            return self.token
        data = self.post("token/get", {"appKey": self.settings.app_key,
                                       "appSecret": self.settings.app_secret})
        try:
            token, expires_at = data["accessToken"], int(data["expireTime"]) / 1000
            if not isinstance(token, str) or not token or expires_at <= time.time():
                raise ValueError
        except (TypeError, KeyError, ValueError):
            raise CounterError("Token 响应缺少有效令牌或过期时间。") from None
        self.token, self.expires_at = token, expires_at
        return token

    def capture(self, camera):
        for attempt in range(2):
            token = self.get_token(refresh=attempt == 1)
            key = (camera.device_serial, camera.channel_no)
            delay = self.settings.capture_interval - (time.monotonic() - self.last_capture.get(key, float('-inf')))
            if delay > 0:
                time.sleep(delay)
            self.last_capture[key] = time.monotonic()
            try:
                data = self.post("device/capture", {"accessToken": token,
                    "deviceSerial": camera.device_serial, "channelNo": camera.channel_no})
                break
            except ApiError as exc:
                if exc.code != "10002" or self.settings.access_token or attempt:
                    raise
        url = data.get("picUrl") if isinstance(data, dict) else None
        if not isinstance(url, str) or urlsplit(url).scheme != "https":
            raise CounterError("抓拍接口没有返回 HTTPS 图片地址。")
        # 图片只保存在内存；存储服务器不会收到应用密钥/Token。
        try:
            with requests.get(url, stream=True, timeout=(10, self.settings.timeout),
                              allow_redirects=False) as response:
                if response.status_code != 200:
                    raise CounterError(f"图片下载 HTTP {response.status_code}。")
                image = bytearray()
                for chunk in response.iter_content(65536):
                    image.extend(chunk)
                    if len(image) > 25 * 1024 * 1024:
                        raise CounterError("抓拍图片超过 25 MiB。")
        except requests.RequestException:
            raise CounterError("抓拍图片下载失败。") from None
        return bytes(image)
