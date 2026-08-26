from __future__ import annotations

from typing import Any, Mapping

import httpx

from .crypto_session_client import (
    BROWSER_USER_AGENT,
    CryptoSessionError,
    DecryptError,
    EncryptedSessionClient,
)

FORMULA_API_BASE = "https://rmj.club/formula"
CRYPTO_SESSION_PATH = "/security/crypto/session"
HKDF_INFO = "formula-response-encrypt-session-v1"


class FormulaApiError(Exception):
    """A safe, endpoint-scoped error raised by the formula API client."""

    def __init__(self, endpoint: str, summary: str) -> None:
        self.endpoint = endpoint
        self.summary = summary
        super().__init__(f"{endpoint}: {summary}")


class FormulaApiClient:
    """Client for the encrypted, read-only formula API."""

    def __init__(
        self,
        *,
        http_client: httpx.AsyncClient | None = None,
        base_url: str = FORMULA_API_BASE,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._http = http_client or httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=min(timeout, 15.0))
        )
        self._owns_http_client = http_client is None
        self._crypto = EncryptedSessionClient(
            HKDF_INFO,
            http_client=self._http,
        )

    async def __aenter__(self) -> FormulaApiClient:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    async def close(self) -> None:
        await self._crypto.close()
        if self._owns_http_client:
            await self._http.aclose()

    def _url(self, endpoint: str) -> str:
        if not endpoint.startswith("/"):
            raise ValueError("formula API endpoint must start with '/'")
        return self.base_url + endpoint

    def _reset_session(self) -> None:
        self._crypto.current_session = None

    @staticmethod
    def _headers(sid: str) -> dict[str, str]:
        return {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": "https://rmj.club/browser/formulaCustomer",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "User-Agent": BROWSER_USER_AGENT,
            "X-Crypto-Session": sid,
            "sec-ch-ua": (
                '"Not=A?Brand";v="99", "Microsoft Edge";v="151", '
                '"Chromium";v="151"'
            ),
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        }

    async def get(
        self,
        endpoint: str,
        *,
        params: Mapping[str, Any] | None = None,
    ) -> Any:
        """Return a validated business result, retrying session failures once."""
        url = self._url(endpoint)

        for attempt in range(2):
            try:
                sid = await self._crypto.ensure_session(
                    self._url(CRYPTO_SESSION_PATH)
                )
                response = await self._http.get(
                    url,
                    params=params,
                    headers=self._headers(sid),
                )
            except (httpx.TransportError, CryptoSessionError) as exc:
                if attempt == 0:
                    self._reset_session()
                    continue
                raise FormulaApiError(endpoint, "连接或加密会话失败") from exc

            if response.status_code in {401, 403, 419} and attempt == 0:
                self._reset_session()
                continue
            if not response.is_success:
                raise FormulaApiError(
                    endpoint,
                    f"HTTP 状态码 {response.status_code}",
                )

            try:
                encrypted_payload = response.json()
            except ValueError as exc:
                raise FormulaApiError(endpoint, "响应不是有效 JSON") from exc
            if not isinstance(encrypted_payload, dict):
                raise FormulaApiError(endpoint, "加密响应格式无效")

            try:
                payload = await self._crypto.decrypt_request(encrypted_payload)
            except DecryptError as exc:
                if attempt == 0:
                    self._reset_session()
                    continue
                raise FormulaApiError(endpoint, "响应解密失败") from exc

            if not isinstance(payload, dict):
                raise FormulaApiError(endpoint, "业务响应格式无效")
            if payload.get("success") is not True:
                code = payload.get("code", "unknown")
                raise FormulaApiError(endpoint, f"业务请求失败（code={code}）")
            if payload.get("code") not in {0, 200, "0", "200"}:
                raise FormulaApiError(
                    endpoint,
                    f"业务状态异常（code={payload.get('code', 'missing')}）",
                )
            if "result" not in payload:
                raise FormulaApiError(endpoint, "业务响应缺少 result")
            return payload["result"]

        raise AssertionError("unreachable")
