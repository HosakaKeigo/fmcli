"""FileMaker Data API クライアント."""

from __future__ import annotations

import logging
from types import TracebackType
from typing import Any

from fmcli.core.encoding import encode_fm_value
from fmcli.core.errors import ApiError, AuthError, TransportError
from fmcli.core.masking import mask_token_in_url
from fmcli.domain.envelopes import ApiInfo
from fmcli.infra.http_client import HttpClient

logger = logging.getLogger(__name__)

FMDATA_API_BASE = "/fmi/data/vLatest"


class FileMakerAPI:
    """FileMaker Data API ラッパー."""

    @staticmethod
    def build_records_path(database: str, layout: str) -> str:
        """GET /records 用のパスを構築する."""
        db = encode_fm_value(database)
        lay = encode_fm_value(layout)
        return f"{FMDATA_API_BASE}/databases/{db}/layouts/{lay}/records"

    @staticmethod
    def build_find_path(database: str, layout: str) -> str:
        """POST /_find 用のパスを構築する."""
        db = encode_fm_value(database)
        lay = encode_fm_value(layout)
        return f"{FMDATA_API_BASE}/databases/{db}/layouts/{lay}/_find"

    def __init__(self, client: HttpClient, database: str) -> None:
        self._client = client
        self._database = database
        self._db = encode_fm_value(database)
        self._token: str | None = None

    @property
    def _auth_headers(self) -> dict[str, str]:
        if not self._token:
            raise AuthError("Not authenticated. Call login() first.")
        return {"Authorization": f"Bearer {self._token}"}

    def set_token(self, token: str) -> None:
        """外部から取得済みトークンをセットする."""
        self._token = token

    # --- Auth ---

    @staticmethod
    def _basic_auth_header(username: str, password: str) -> dict[str, str]:
        """Basic 認証ヘッダを生成する."""
        import base64

        credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
        return {"Authorization": f"Basic {credentials}"}

    def login(self, username: str, password: str) -> tuple[str, ApiInfo]:
        """ログインしてセッショントークンを取得する."""
        logger.debug("login db=%s", self._database)
        path = f"{FMDATA_API_BASE}/databases/{self._db}/sessions"
        body, api_info = self._client.request(
            "POST",
            path,
            headers={
                **self._basic_auth_header(username, password),
                "Content-Type": "application/json",
            },
            json_body={},
        )
        token = body.get("response", {}).get("token", "")
        self._token = token
        logger.debug("login ok db=%s", self._database)
        return token, api_info

    def logout(self) -> ApiInfo:
        """セッションを破棄する."""
        logger.debug("logout db=%s", self._database)
        token = self._token or ""
        path = f"{FMDATA_API_BASE}/databases/{self._db}/sessions/{token}"
        _, api_info = self._client.request("DELETE", path, headers=self._auth_headers)
        if token:
            api_info.url = mask_token_in_url(api_info.url, token)
        self._token = None
        return api_info

    def validate_session(self) -> tuple[bool, ApiInfo]:
        """セッションが有効か確認する."""
        path = f"{FMDATA_API_BASE}/validateSession"
        try:
            _, api_info = self._client.request("GET", path, headers=self._auth_headers)
            logger.debug("validate_session valid=True")
            return True, api_info
        except (ApiError, TransportError, AuthError):
            logger.debug("validate_session valid=False")
            return False, ApiInfo(method="GET", url=path)

    # --- Metadata ---

    def get_product_info(self) -> tuple[dict[str, Any], ApiInfo]:
        """ホスト製品情報を取得する (認証不要)."""
        path = f"{FMDATA_API_BASE}/productInfo"
        return self._client.request("GET", path)

    def get_databases(self, username: str, password: str) -> tuple[dict[str, Any], ApiInfo]:
        """データベース一覧を取得する (Basic 認証)."""
        path = f"{FMDATA_API_BASE}/databases"
        return self._client.request(
            "GET",
            path,
            headers=self._basic_auth_header(username, password),
        )

    def get_layouts(self) -> tuple[dict[str, Any], ApiInfo]:
        """レイアウト一覧を取得する."""
        path = f"{FMDATA_API_BASE}/databases/{self._db}/layouts"
        return self._client.request("GET", path, headers=self._auth_headers)

    def get_layout_metadata(self, layout: str) -> tuple[dict[str, Any], ApiInfo]:
        """レイアウトメタデータを取得する."""
        path = f"{FMDATA_API_BASE}/databases/{self._db}/layouts/{encode_fm_value(layout)}"
        return self._client.request("GET", path, headers=self._auth_headers)

    def get_scripts(self) -> tuple[dict[str, Any], ApiInfo]:
        """スクリプト一覧を取得する."""
        path = f"{FMDATA_API_BASE}/databases/{self._db}/scripts"
        return self._client.request("GET", path, headers=self._auth_headers)

    # --- Records ---

    def get_record(
        self,
        layout: str,
        record_id: int,
        *,
        portal_params: dict[str, str] | None = None,
        script_params: dict[str, str] | None = None,
    ) -> tuple[dict[str, Any], ApiInfo]:
        """単一レコードを取得する."""
        path = (
            f"{FMDATA_API_BASE}/databases/{self._db}"
            f"/layouts/{encode_fm_value(layout)}/records/{record_id}"
        )
        params: dict[str, str] = {}
        if portal_params:
            params.update(portal_params)
        if script_params:
            params.update(script_params)
        return self._client.request("GET", path, headers=self._auth_headers, params=params or None)

    def get_records(
        self,
        layout: str,
        *,
        offset: int = 1,
        limit: int = 100,
        sort: list[dict[str, str]] | None = None,
        portal_params: dict[str, str] | None = None,
        script_params: dict[str, str] | None = None,
    ) -> tuple[dict[str, Any], ApiInfo]:
        """レコード一覧を取得する."""
        import json

        path = self.build_records_path(self._database, layout)
        params: dict[str, str] = {
            "_offset": str(offset),
            "_limit": str(limit),
        }
        if sort:
            params["_sort"] = json.dumps(sort)
        if portal_params:
            params.update(portal_params)
        if script_params:
            params.update(script_params)
        return self._client.request("GET", path, headers=self._auth_headers, params=params)

    def find_records(
        self,
        layout: str,
        query: list[dict[str, Any]],
        *,
        sort: list[dict[str, str]] | None = None,
        offset: int = 1,
        limit: int = 100,
        portal_params: dict[str, Any] | None = None,
        script_params: dict[str, str] | None = None,
    ) -> tuple[dict[str, Any], ApiInfo]:
        """レコードを検索する."""
        path = self.build_find_path(self._database, layout)
        body: dict[str, Any] = {"query": query}
        if sort:
            body["sort"] = sort
        body["offset"] = str(offset)
        body["limit"] = str(limit)
        if portal_params:
            body.update(portal_params)
        if script_params:
            body.update(script_params)
        return self._client.request(
            "POST",
            path,
            headers=self._auth_headers,
            json_body=body,
        )

    def create_record(
        self,
        layout: str,
        field_data: dict[str, Any],
        *,
        script_params: dict[str, str] | None = None,
    ) -> tuple[dict[str, Any], ApiInfo]:
        """レコードを作成する."""
        path = self.build_records_path(self._database, layout)
        body: dict[str, Any] = {"fieldData": field_data}
        if script_params:
            body.update(script_params)
        return self._client.request(
            "POST",
            path,
            headers=self._auth_headers,
            json_body=body,
        )

    def update_record(
        self,
        layout: str,
        record_id: int,
        field_data: dict[str, Any],
        *,
        mod_id: str,
        script_params: dict[str, str] | None = None,
    ) -> tuple[dict[str, Any], ApiInfo]:
        """レコードを更新する (PATCH)."""
        path = (
            f"{FMDATA_API_BASE}/databases/{self._db}"
            f"/layouts/{encode_fm_value(layout)}/records/{record_id}"
        )
        body: dict[str, Any] = {"fieldData": field_data, "modId": mod_id}
        if script_params:
            body.update(script_params)
        return self._client.request(
            "PATCH",
            path,
            headers=self._auth_headers,
            json_body=body,
        )

    def upload_container(
        self,
        layout: str,
        record_id: int,
        field_name: str,
        *,
        file_path: str,
        file_name: str,
        mime_type: str,
        repetition: int = 1,
    ) -> tuple[dict[str, Any], ApiInfo]:
        """コンテナフィールドにファイルをアップロードする (POST multipart/form-data)."""
        path = (
            f"{FMDATA_API_BASE}/databases/{self._db}"
            f"/layouts/{encode_fm_value(layout)}"
            f"/records/{record_id}"
            f"/containers/{encode_fm_value(field_name)}/{repetition}"
        )
        try:
            with open(file_path, "rb") as f:
                files = {"upload": (file_name, f, mime_type)}
                return self._client.request(
                    "POST",
                    path,
                    headers=self._auth_headers,
                    files=files,
                )
        except OSError as e:
            raise ApiError(
                f"ファイルの読み込みに失敗しました: {e}",
                http_status=0,
                api_code=0,
                retryable=False,
            ) from e

    # --- Context Manager ---

    def __enter__(self) -> FileMakerAPI:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        """クライアントを閉じる."""
        self._client.close()
