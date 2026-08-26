from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import hmac
import json
import math
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

import httpx
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/151.0.0.0 Safari/537.36 Edg/151.0.0.0"
)


class CryptoSessionError(Exception):
    """Raised when an encrypted session cannot be created."""


class DecryptError(Exception):
    """Raised when an encrypted payload cannot be decrypted."""


def current_time_ms() -> int:
    """Equivalent to JavaScript's Date.now()."""
    return int(time.time() * 1000)


def js_string(value: Any) -> str:
    """Convert common JSON values like JavaScript's String(value)."""
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Infinity" if value > 0 else "-Infinity"
        if value.is_integer():
            return str(int(value))
    return str(value)


def encode_base64url(data: bytes) -> str:
    """
    Equivalent to the JavaScript a(...) helper.

    Encode bytes as URL-safe Base64 and remove trailing '=' padding.
    """
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def decode_base64url(value: str) -> bytes:
    """
    Equivalent to the JavaScript i(...) helper.

    Decode URL-safe Base64 after restoring trailing '=' padding.
    """
    if not isinstance(value, str):
        raise TypeError("Base64URL value must be a string")

    normalized = value.replace("-", "+").replace("_", "/")
    normalized += "=" * ((4 - len(normalized) % 4) % 4)

    try:
        return base64.b64decode(normalized, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Invalid Base64URL value") from exc


@dataclass(slots=True)
class CryptoSession:
    sid: str
    hmac_key: bytes
    token: str
    expires_at: int
    used_rids: set[str] = field(default_factory=set)
    rid_order: deque[str] = field(default_factory=deque)
    pending_rids: set[str] = field(default_factory=set)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class EncryptedSessionClient:
    """
    Python implementation of the JavaScript ECDH/HKDF session and decrypt flow.

    The supplied hkdf_info must exactly match the JavaScript value passed to:

        info: new TextEncoder().encode(r)

    An injected httpx.AsyncClient can carry cookies and other shared HTTP state.
    """

    def __init__(
        self,
        hkdf_info: str,
        *,
        http_client: httpx.AsyncClient | None = None,
        timeout: float = 30.0,
        max_used_rids: int = 2000,
    ) -> None:
        if not isinstance(hkdf_info, str):
            raise TypeError("hkdf_info must be a string")
        if max_used_rids < 1:
            raise ValueError("max_used_rids must be at least 1")

        self.hkdf_info = hkdf_info
        self.max_used_rids = max_used_rids
        self.sessions: dict[str, CryptoSession] = {}
        self.current_session: CryptoSession | None = None

        self._http = http_client or httpx.AsyncClient(timeout=timeout)
        self._owns_http_client = http_client is None
        self._ensure_lock = asyncio.Lock()

    async def __aenter__(self) -> EncryptedSessionClient:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    async def close(self) -> None:
        if self._owns_http_client:
            await self._http.aclose()

    async def ensure_session(
        self,
        endpoint: str,
        token: str | None = None,
    ) -> str:
        """
        Reuse a valid session or negotiate a new one with the server.

        This corresponds to the JavaScript "ensure" branch and returns sid.
        """
        token = token or ""

        # Serializing the entire negotiation prevents concurrent calls from
        # creating multiple sessions and overwriting current_session.
        async with self._ensure_lock:
            now = current_time_ms()
            cached = self.current_session

            if (
                cached is not None
                and cached.token == token
                and cached.expires_at - now > 60_000
            ):
                return cached.sid

            # P-256 is namedCurve "P-256" in Web Crypto.
            client_private_key = ec.generate_private_key(ec.SECP256R1())
            client_public_spki = client_private_key.public_key().public_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )

            headers = {
                "Content-Type": "application/json",
                "Referer": "https://rmj.club/assets/responseCrypto.worker-AwEmsErt.js",
                "User-Agent": BROWSER_USER_AGENT,
            }
            if token:
                headers["X-Access-Token"] = token
                headers["Authorization"] = f"Bearer {token}"

            response = await self._http.post(
                endpoint,
                headers=headers,
                json={
                    "clientPublicKey": encode_base64url(client_public_spki),
                },
            )

            if not response.is_success:
                raise CryptoSessionError(
                    f"加密会话创建失败：{response.status_code}"
                )

            try:
                response_data = response.json()
            except ValueError as exc:
                raise CryptoSessionError("加密会话响应不是有效 JSON") from exc

            if isinstance(response_data, dict) and response_data.get("result") is not None:
                result = response_data["result"]
            else:
                result = response_data

            if not isinstance(result, dict):
                raise CryptoSessionError("加密会话响应格式无效")

            sid_value = result.get("sid")
            server_public_key_value = result.get("serverPublicKey")
            salt_value = result.get("salt")

            if not sid_value or not server_public_key_value or not salt_value:
                raise CryptoSessionError("加密会话响应格式无效")
            if not isinstance(server_public_key_value, str):
                raise CryptoSessionError("serverPublicKey 必须是字符串")
            if not isinstance(salt_value, str):
                raise CryptoSessionError("salt 必须是字符串")

            try:
                server_public_spki = decode_base64url(server_public_key_value)
                loaded_public_key = serialization.load_der_public_key(
                    server_public_spki
                )
            except (TypeError, ValueError) as exc:
                raise CryptoSessionError("服务器 ECDH 公钥格式无效") from exc

            if not isinstance(loaded_public_key, ec.EllipticCurvePublicKey):
                raise CryptoSessionError("服务器返回的不是椭圆曲线公钥")
            if not isinstance(loaded_public_key.curve, ec.SECP256R1):
                raise CryptoSessionError("服务器公钥不是 P-256 曲线")

            # ECDH(client private key, server public key), 32 bytes on P-256.
            shared_secret = client_private_key.exchange(
                ec.ECDH(),
                loaded_public_key,
            )

            try:
                salt = decode_base64url(salt_value)
            except (TypeError, ValueError) as exc:
                raise CryptoSessionError("服务器 salt 格式无效") from exc

            # Equivalent to Web Crypto HKDF deriveKey producing a 256-bit
            # HMAC-SHA-256 key.
            session_hmac_key = HKDF(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                info=self.hkdf_info.encode("utf-8"),
            ).derive(shared_secret)

            expires_at_value = result.get("expiresAt")
            if expires_at_value:
                try:
                    expires_at = int(expires_at_value)
                except (TypeError, ValueError) as exc:
                    raise CryptoSessionError(
                        "expiresAt 必须是毫秒时间戳"
                    ) from exc
            else:
                # JavaScript fallback: Date.now() + 18e5 (30 minutes).
                expires_at = current_time_ms() + 1_800_000

            session = CryptoSession(
                sid=js_string(sid_value),
                hmac_key=session_hmac_key,
                token=token,
                expires_at=expires_at,
            )

            self.current_session = session
            self.sessions[session.sid] = session
            return session.sid

    async def decrypt_request(
        self,
        request: dict[str, Any] | None,
    ) -> Any:
        """
        Decrypt an AES-GCM payload returned for a negotiated session.

        Expected request shape:

            {
                "sid": "...",
                "rid": "...",
                "iv": "Base64URL without padding",
                "ts": 1234567890000,
                "data": "ciphertext + 16-byte GCM tag, Base64URL encoded"
            }
        """
        if request is None:
            raise DecryptError("1")

        sid_value = request.get("sid")
        sid = js_string(sid_value)
        session = self.sessions.get(sid)
        if session is None:
            raise DecryptError("1")

        try:
            rid_value = request["rid"]
            iv_value = request["iv"]
            timestamp_value = request["ts"]
            data_value = request["data"]
        except KeyError as exc:
            raise DecryptError(f"请求缺少字段：{exc.args[0]}") from exc

        rid = js_string(rid_value)
        iv_text = js_string(iv_value)
        data_text = js_string(data_value)

        async with session.lock:
            if rid in session.used_rids or rid in session.pending_rids:
                raise DecryptError("2")
            session.pending_rids.add(rid)

        authenticated = False

        try:
            # HMAC-SHA-256(session HMAC key, UTF-8 rid) produces the
            # per-request 32-byte AES-256-GCM key.
            aes_key = hmac.new(
                key=session.hmac_key,
                msg=rid.encode("utf-8"),
                digestmod=hashlib.sha256,
            ).digest()

            try:
                iv = decode_base64url(iv_text)
                encrypted_data = decode_base64url(data_text)
            except (TypeError, ValueError) as exc:
                raise DecryptError("IV 或 data 不是有效的 Base64URL") from exc

            # Exact equivalent of `${r.sid}.${r.rid}.${r.iv}.${r.ts}`.
            aad = (
                f"{js_string(sid_value)}."
                f"{rid}."
                f"{iv_text}."
                f"{js_string(timestamp_value)}"
            ).encode("utf-8")

            try:
                plaintext = AESGCM(aes_key).decrypt(
                    nonce=iv,
                    data=encrypted_data,
                    associated_data=aad,
                )
            except InvalidTag as exc:
                raise DecryptError("AES-GCM 认证失败") from exc

            # The original JavaScript records rid after authenticated decrypt
            # and before JSON.parse, so invalid authenticated JSON also consumes
            # the rid.
            authenticated = True

            try:
                return json.loads(plaintext.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise DecryptError("解密后的内容不是有效 UTF-8 JSON") from exc

        finally:
            async with session.lock:
                session.pending_rids.discard(rid)

                if authenticated:
                    session.used_rids.add(rid)
                    session.rid_order.append(rid)

                    if len(session.rid_order) > self.max_used_rids:
                        oldest_rid = session.rid_order.popleft()
                        session.used_rids.discard(oldest_rid)
