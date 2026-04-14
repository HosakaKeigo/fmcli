"""HTTP クライアント."""

from __future__ import annotations

import contextlib
import logging
import time
from typing import Any

import httpx

from fmcli.core.errors import ApiError, AuthError, TransportError
from fmcli.core.masking import mask_url
from fmcli.domain.envelopes import ApiInfo
from fmcli.domain.error_codes import AuthErrorType, FmApiCode, HttpStatus

logger = logging.getLogger(__name__)


class HttpClient:
    """FileMaker Data API 用 HTTP クライアント."""

    def __init__(self, base_url: str, *, verify_ssl: bool = True, timeout: int = 60) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(verify=verify_ssl, timeout=timeout)

    def __enter__(self) -> HttpClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
        files: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], ApiInfo]:
        """HTTP リクエストを実行し、レスポンス JSON と API 情報を返す.

        json_body と files は排他的。files を指定した場合は multipart/form-data で送信する。
        """
        if json_body is not None and files is not None:
            raise ValueError("json_body and files are mutually exclusive")
        url = f"{self._base_url}{path}"
        logger.debug("-> %s %s", method, mask_url(url))
        start = time.monotonic()
        try:
            response = self._client.request(
                method,
                url,
                headers=headers,
                json=json_body,
                params=params,
                files=files,
            )
        except httpx.TransportError as e:
            logger.debug("!! %s transport error: %s", method, e)
            raise TransportError(str(e)) from e

        duration_ms = (time.monotonic() - start) * 1000
        api_info = ApiInfo(method=method, url=url, duration_ms=round(duration_ms, 1))
        logger.debug("<- %s %d %.0fms", method, response.status_code, duration_ms)

        if response.status_code >= 400:
            content_type = response.headers.get("content-type", "")
            body: dict[str, Any] = {}
            if content_type.startswith("application/json"):
                try:
                    body = response.json()
                except ValueError:
                    logger.debug("!! Failed to parse error response JSON")
            messages = body.get("messages", [{}])
            api_code = int(messages[0].get("code", 0)) if messages else 0
            msg = (
                messages[0].get("message", response.reason_phrase)
                if messages
                else response.reason_phrase
            )
            status = response.status_code

            # 401: 認証エラー（セッション無効 or 認証情報不正）
            if status == HttpStatus.UNAUTHORIZED:
                is_expired = api_code == FmApiCode.SESSION_EXPIRED
                raise AuthError(
                    msg or "認証エラー",
                    error_type=(AuthErrorType.EXPIRED if is_expired else AuthErrorType.INVALID),
                    retryable=is_expired,
                )
            # 403: アクセス権限なし
            if status == HttpStatus.FORBIDDEN:
                raise AuthError(
                    msg or "アクセスが禁止されています",
                    error_type=AuthErrorType.FORBIDDEN,
                    retryable=False,
                )

            # retryable 判定: HTTP レベル or FM API コードレベル
            try:
                is_retryable = HttpStatus(status).retryable
            except ValueError:
                is_retryable = False
            with contextlib.suppress(ValueError):
                is_retryable = is_retryable or FmApiCode(api_code).retryable

            raise ApiError(
                msg or "API error",
                http_status=status,
                api_code=api_code,
                retryable=is_retryable,
            )

        try:
            return response.json(), api_info
        except ValueError as e:
            raise ApiError(
                f"レスポンスの JSON パースに失敗しました: {e}",
                http_status=response.status_code,
                api_code=0,
                retryable=False,
            ) from e

    def close(self) -> None:
        """クライアントを閉じる."""
        self._client.close()
