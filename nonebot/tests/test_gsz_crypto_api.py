from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
from typing import Any

import httpx
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from gsz_assist_testpkg.crypto_session_client import (
    CryptoSession,
    CryptoSessionError,
    DecryptError,
    EncryptedSessionClient,
    current_time_ms,
    decode_base64url,
    encode_base64url,
    js_string,
)
from gsz_assist_testpkg.formula_api_client import (
    CRYPTO_SESSION_PATH,
    FormulaApiClient,
    FormulaApiError,
    HKDF_INFO,
)


def _encrypted_payload(
    session: CryptoSession,
    value: Any,
    *,
    rid: str = "rid-1",
    sid: str | None = None,
    timestamp: int = 1_700_000_000_000,
) -> dict[str, Any]:
    request_sid = sid or session.sid
    iv = os.urandom(12)
    iv_text = encode_base64url(iv)
    aad = f"{request_sid}.{rid}.{iv_text}.{timestamp}".encode()
    key = hmac.new(session.hmac_key, rid.encode(), hashlib.sha256).digest()
    data = AESGCM(key).encrypt(iv, json.dumps(value).encode(), aad)
    return {
        "sid": request_sid,
        "rid": rid,
        "iv": iv_text,
        "ts": timestamp,
        "data": encode_base64url(data),
    }


def test_base64url_round_trip_and_invalid_input() -> None:
    assert decode_base64url(encode_base64url(b"\x00\xfb\xffpayload")) == b"\x00\xfb\xffpayload"
    with pytest.raises(ValueError):
        decode_base64url("not+base64url!")
    with pytest.raises(TypeError):
        decode_base64url(123)  # type: ignore[arg-type]


def test_js_string_and_constructor_validation() -> None:
    assert [js_string(value) for value in (None, True, False, 2.0)] == [
        "null", "true", "false", "2"
    ]
    assert js_string(float("nan")) == "NaN"
    assert js_string(float("inf")) == "Infinity"
    assert js_string(float("-inf")) == "-Infinity"
    with pytest.raises(TypeError):
        EncryptedSessionClient(1)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        EncryptedSessionClient(HKDF_INFO, max_used_rids=0)


def test_decrypt_checks_aad_key_and_duplicate_rid() -> None:
    async def scenario() -> None:
        client = EncryptedSessionClient(HKDF_INFO, http_client=httpx.AsyncClient())
        session = CryptoSession("sid", b"k" * 32, "", current_time_ms() + 120_000)
        client.sessions[session.sid] = session
        request = _encrypted_payload(session, {"ok": True})
        assert await client.decrypt_request(request) == {"ok": True}
        with pytest.raises(DecryptError, match="2"):
            await client.decrypt_request(request)

        tampered = _encrypted_payload(session, {"ok": True}, rid="rid-2")
        tampered["ts"] += 1
        with pytest.raises(DecryptError, match="认证失败"):
            await client.decrypt_request(tampered)

        wrong_key = CryptoSession("wrong", b"w" * 32, "", current_time_ms() + 120_000)
        client.sessions[wrong_key.sid] = wrong_key
        wrong_request = _encrypted_payload(session, {"ok": True}, rid="wrong-key", sid="wrong")
        with pytest.raises(DecryptError, match="认证失败"):
            await client.decrypt_request(wrong_request)
        await client._http.aclose()

    asyncio.run(scenario())


def test_concurrent_duplicate_rid_allows_only_one_decrypt() -> None:
    async def scenario() -> None:
        async with httpx.AsyncClient() as http:
            client = EncryptedSessionClient(HKDF_INFO, http_client=http)
            session = CryptoSession("sid", b"x" * 32, "", current_time_ms() + 120_000)
            client.sessions[session.sid] = session
            request = _encrypted_payload(session, {"ok": True})
            results = await asyncio.gather(
                client.decrypt_request(request),
                client.decrypt_request(request),
                return_exceptions=True,
            )
            assert sum(result == {"ok": True} for result in results) == 1
            assert sum(isinstance(result, DecryptError) for result in results) == 1

    asyncio.run(scenario())


def test_decrypt_rejects_missing_invalid_and_authenticated_non_json() -> None:
    async def scenario() -> None:
        async with httpx.AsyncClient() as http:
            client = EncryptedSessionClient(HKDF_INFO, http_client=http, max_used_rids=1)
            session = CryptoSession("sid", b"z" * 32, "", current_time_ms() + 120_000)
            client.sessions[session.sid] = session
            with pytest.raises(DecryptError, match="1"):
                await client.decrypt_request(None)
            with pytest.raises(DecryptError, match="缺少字段"):
                await client.decrypt_request({"sid": "sid"})
            with pytest.raises(DecryptError, match="Base64URL"):
                await client.decrypt_request({"sid": "sid", "rid": "bad", "iv": "!", "ts": 1, "data": "!"})

            def encrypted_raw(raw: bytes, rid: str) -> dict[str, Any]:
                iv = os.urandom(12)
                iv_text = encode_base64url(iv)
                timestamp = 10
                aad = f"sid.{rid}.{iv_text}.{timestamp}".encode()
                key = hmac.new(session.hmac_key, rid.encode(), hashlib.sha256).digest()
                return {"sid": "sid", "rid": rid, "iv": iv_text, "ts": timestamp, "data": encode_base64url(AESGCM(key).encrypt(iv, raw, aad))}

            with pytest.raises(DecryptError, match="UTF-8 JSON"):
                await client.decrypt_request(encrypted_raw(b"not json", "json"))
            assert "json" in session.used_rids
            assert await client.decrypt_request(_encrypted_payload(session, 1, rid="next")) == 1
            assert "json" not in session.used_rids

    asyncio.run(scenario())


class EncryptedApiTransport:
    def __init__(self, payloads: list[Any]) -> None:
        self.payloads = list(payloads)
        self.sessions: dict[str, bytes] = {}
        self.session_calls = 0
        self.get_calls = 0
        self.last_request: httpx.Request | None = None

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith(CRYPTO_SESSION_PATH):
            self.session_calls += 1
            body = json.loads(request.content)
            client_public = serialization.load_der_public_key(
                decode_base64url(body["clientPublicKey"])
            )
            assert isinstance(client_public, ec.EllipticCurvePublicKey)
            server_private = ec.generate_private_key(ec.SECP256R1())
            salt = os.urandom(16)
            shared = server_private.exchange(ec.ECDH(), client_public)
            key = HKDF(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                info=HKDF_INFO.encode(),
            ).derive(shared)
            sid = f"sid-{self.session_calls}"
            self.sessions[sid] = key
            public = server_private.public_key().public_bytes(
                serialization.Encoding.DER,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            return httpx.Response(
                200,
                json={
                    "result": {
                        "sid": sid,
                        "serverPublicKey": encode_base64url(public),
                        "salt": encode_base64url(salt),
                        "expiresAt": current_time_ms() + 120_000,
                    }
                },
            )

        self.get_calls += 1
        self.last_request = request
        sid = request.headers["X-Crypto-Session"]
        session = CryptoSession(sid, self.sessions[sid], "", current_time_ms() + 120_000)
        value = self.payloads[min(self.get_calls - 1, len(self.payloads) - 1)]
        return httpx.Response(200, json=_encrypted_payload(session, value, rid=f"rid-{self.get_calls}"))


def test_session_negotiation_reuse_and_expiry() -> None:
    async def scenario() -> None:
        transport = EncryptedApiTransport([])
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as http:
            client = EncryptedSessionClient(HKDF_INFO, http_client=http)
            first = await client.ensure_session("https://test/security/crypto/session")
            assert await client.ensure_session("https://test/security/crypto/session") == first
            assert transport.session_calls == 1
            assert client.current_session is not None
            client.current_session.expires_at = current_time_ms() + 1
            assert await client.ensure_session("https://test/security/crypto/session") != first
            assert transport.session_calls == 2

    asyncio.run(scenario())


def test_session_rejects_invalid_json_and_server_key() -> None:
    async def invalid_json(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not json")

    async def scenario() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(invalid_json)) as http:
            client = EncryptedSessionClient(HKDF_INFO, http_client=http)
            with pytest.raises(CryptoSessionError, match="有效 JSON"):
                await client.ensure_session("https://test/security/crypto/session")

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "kind, message",
    [
        ("http", "创建失败"),
        ("list", "格式无效"),
        ("missing", "格式无效"),
        ("key-type", "serverPublicKey"),
        ("salt-type", "salt"),
        ("bad-key", "公钥格式"),
        ("rsa-key", "不是椭圆曲线公钥"),
        ("curve", "不是 P-256"),
        ("bad-salt", "salt 格式"),
        ("expires", "expiresAt"),
    ],
)
def test_session_response_validation(kind: str, message: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if kind == "http":
            return httpx.Response(503)
        if kind == "list":
            return httpx.Response(200, json=[])
        if kind == "missing":
            return httpx.Response(200, json={})
        body = json.loads(request.content)
        client_public = serialization.load_der_public_key(decode_base64url(body["clientPublicKey"]))
        server_private = ec.generate_private_key(ec.SECP256R1())
        server_public = server_private.public_key().public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        result: dict[str, Any] = {
            "sid": "sid",
            "serverPublicKey": encode_base64url(server_public),
            "salt": encode_base64url(os.urandom(16)),
            "expiresAt": current_time_ms() + 120_000,
        }
        if kind == "key-type":
            result["serverPublicKey"] = 1
        elif kind == "salt-type":
            result["salt"] = 1
        elif kind == "bad-key":
            result["serverPublicKey"] = encode_base64url(b"bad")
        elif kind == "rsa-key":
            public = rsa.generate_private_key(public_exponent=65537, key_size=2048).public_key()
            result["serverPublicKey"] = encode_base64url(
                public.public_bytes(
                    serialization.Encoding.DER,
                    serialization.PublicFormat.SubjectPublicKeyInfo,
                )
            )
        elif kind == "curve":
            public = ec.generate_private_key(ec.SECP384R1()).public_key()
            result["serverPublicKey"] = encode_base64url(
                public.public_bytes(
                    serialization.Encoding.DER,
                    serialization.PublicFormat.SubjectPublicKeyInfo,
                )
            )
        elif kind == "bad-salt":
            result["salt"] = "!"
        elif kind == "expires":
            result["expiresAt"] = "never"
        assert isinstance(client_public, ec.EllipticCurvePublicKey)
        return httpx.Response(200, json=result)

    async def scenario() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            client = EncryptedSessionClient(HKDF_INFO, http_client=http)
            with pytest.raises(CryptoSessionError, match=message):
                await client.ensure_session("https://test/session", token="token")

    asyncio.run(scenario())


def test_session_plain_response_default_expiry_and_context_close() -> None:
    transport = EncryptedApiTransport([])

    def handler(request: httpx.Request) -> httpx.Response:
        response = transport(request)
        body = response.json()["result"]
        body.pop("expiresAt")
        return httpx.Response(200, json=body)

    async def scenario() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            async with EncryptedSessionClient(HKDF_INFO, http_client=http) as client:
                await client.ensure_session("https://test/security/crypto/session")
                assert client.current_session is not None
                assert client.current_session.expires_at > current_time_ms()
        owned = EncryptedSessionClient(HKDF_INFO)
        async with owned:
            pass
        assert owned._http.is_closed

    asyncio.run(scenario())


def test_formula_api_encrypted_round_trip_and_query_params() -> None:
    async def scenario() -> None:
        transport = EncryptedApiTransport([
            {"success": True, "code": 200, "result": {"records": []}}
        ])
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as http:
            async with FormulaApiClient(http_client=http, base_url="https://test") as client:
                result = await client.get("/endpoint", params={"name": "测试 名"})
                assert result == {"records": []}
                assert transport.session_calls == 1
                assert transport.last_request is not None
                assert transport.last_request.url.params["name"] == "测试 名"
                assert transport.last_request.headers["X-Crypto-Session"] == "sid-1"

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "payload, message",
    [
        ({"success": False, "code": 500, "result": None}, "业务请求失败"),
        ({"success": True, "code": 500, "result": None}, "业务状态异常"),
        ({"success": True, "code": 200}, "缺少 result"),
        (["invalid"], "业务响应格式无效"),
    ],
)
def test_formula_api_rejects_business_and_format_errors(payload: Any, message: str) -> None:
    async def scenario() -> None:
        transport = EncryptedApiTransport([payload])
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as http:
            client = FormulaApiClient(http_client=http, base_url="https://test")
            with pytest.raises(FormulaApiError, match=message):
                await client.get("/endpoint")

    asyncio.run(scenario())


def test_formula_api_retries_decrypt_failure_once() -> None:
    class RetryTransport(EncryptedApiTransport):
        def __call__(self, request: httpx.Request) -> httpx.Response:
            response = super().__call__(request)
            if not request.url.path.endswith(CRYPTO_SESSION_PATH) and self.get_calls == 1:
                body = response.json()
                body["sid"] = "unknown"
                return httpx.Response(200, json=body)
            return response

    async def scenario() -> None:
        transport = RetryTransport([
            {"success": True, "code": 200, "result": "ignored"},
            {"success": True, "code": 200, "result": "ok"},
        ])
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as http:
            client = FormulaApiClient(http_client=http, base_url="https://test")
            assert await client.get("/endpoint") == "ok"
            assert transport.session_calls == 2
            assert transport.get_calls == 2

    asyncio.run(scenario())


def test_formula_api_http_error_does_not_retry() -> None:
    transport = EncryptedApiTransport([])

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith(CRYPTO_SESSION_PATH):
            return transport(request)
        transport.get_calls += 1
        return httpx.Response(503)

    async def scenario() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            client = FormulaApiClient(http_client=http, base_url="https://test")
            with pytest.raises(FormulaApiError, match="503"):
                await client.get("/endpoint")
        assert transport.get_calls == 1

    asyncio.run(scenario())


def test_formula_api_transport_retry_exhaustion_and_session_http_retry() -> None:
    calls = 0

    def transport_error(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("offline", request=request)

    async def transport_scenario() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport_error)) as http:
            client = FormulaApiClient(http_client=http, base_url="https://test")
            with pytest.raises(FormulaApiError, match="连接或加密会话失败"):
                await client.get("/endpoint")
        assert calls == 2

    asyncio.run(transport_scenario())

    transport = EncryptedApiTransport([
        {"success": True, "code": 200, "result": "ok"}
    ])
    unauthorized = 0

    def session_http(request: httpx.Request) -> httpx.Response:
        nonlocal unauthorized
        if request.url.path.endswith(CRYPTO_SESSION_PATH):
            return transport(request)
        if unauthorized == 0:
            unauthorized += 1
            return httpx.Response(401)
        return transport(request)

    async def http_scenario() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(session_http)) as http:
            client = FormulaApiClient(http_client=http, base_url="https://test")
            assert await client.get("/endpoint") == "ok"
        assert transport.session_calls == 2

    asyncio.run(http_scenario())


@pytest.mark.parametrize(
    "response, message",
    [
        (httpx.Response(200, text="not json"), "有效 JSON"),
        (httpx.Response(200, json=[]), "加密响应格式无效"),
    ],
)
def test_formula_api_rejects_outer_response(response: httpx.Response, message: str) -> None:
    transport = EncryptedApiTransport([])

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith(CRYPTO_SESSION_PATH):
            return transport(request)
        return response

    async def scenario() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            client = FormulaApiClient(http_client=http, base_url="https://test")
            with pytest.raises(FormulaApiError, match=message):
                await client.get("/endpoint")

    asyncio.run(scenario())


def test_formula_api_url_validation_owned_close_and_decrypt_exhaustion() -> None:
    client = FormulaApiClient()
    with pytest.raises(ValueError):
        client._url("endpoint")
    asyncio.run(client.close())
    assert client._http.is_closed

    class AlwaysBad(EncryptedApiTransport):
        def __call__(self, request: httpx.Request) -> httpx.Response:
            response = super().__call__(request)
            if not request.url.path.endswith(CRYPTO_SESSION_PATH):
                body = response.json()
                body["sid"] = "unknown"
                return httpx.Response(200, json=body)
            return response

    async def scenario() -> None:
        transport = AlwaysBad([
            {"success": True, "code": 200, "result": "ignored"}
        ])
        async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as http:
            client = FormulaApiClient(http_client=http, base_url="https://test")
            with pytest.raises(FormulaApiError, match="响应解密失败"):
                await client.get("/endpoint")

    asyncio.run(scenario())
