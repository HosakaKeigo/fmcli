"""HttpClient のユニットテスト."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from fmcli.core.errors import ApiError, AuthError, TransportError
from fmcli.core.masking import mask_url
from fmcli.domain.envelopes import ApiInfo
from fmcli.infra.http_client import HttpClient

BASE_URL = "https://fm.example.com"


@pytest.fixture()
def mock_httpx_client() -> MagicMock:
    """httpx.Client のモックを返す."""
    return MagicMock(spec=httpx.Client)


@pytest.fixture()
def client(mock_httpx_client: MagicMock) -> HttpClient:
    """モック済み httpx.Client を注入した HttpClient を返す."""
    with patch("fmcli.infra.http_client.httpx.Client", return_value=mock_httpx_client):
        return HttpClient(BASE_URL)


def _make_response(
    *,
    status_code: int = 200,
    json_data: dict | None = None,
    content_type: str = "application/json",
    reason_phrase: str = "OK",
) -> MagicMock:
    """httpx.Response のモックを生成する."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.reason_phrase = reason_phrase
    resp.headers = {"content-type": content_type}
    if json_data is not None:
        resp.json.return_value = json_data
    else:
        resp.json.return_value = {"response": {}, "messages": [{"code": "0"}]}
    return resp


class TestHttpClientRequest:
    """request() メソッドの正常系テスト."""

    def test_get_returns_dict_and_api_info(
        self, client: HttpClient, mock_httpx_client: MagicMock
    ) -> None:
        """GET リクエスト成功時に (dict, ApiInfo) が返る."""
        body = {"response": {"data": [{"id": 1}]}, "messages": [{"code": "0"}]}
        mock_httpx_client.request.return_value = _make_response(json_data=body)

        result, api_info = client.request("GET", "/fmi/data/v1/databases/DB/layouts")

        assert result == body
        assert isinstance(api_info, ApiInfo)
        mock_httpx_client.request.assert_called_once_with(
            "GET",
            f"{BASE_URL}/fmi/data/v1/databases/DB/layouts",
            headers=None,
            json=None,
            params=None,
            files=None,
        )

    def test_post_sends_json_body(self, client: HttpClient, mock_httpx_client: MagicMock) -> None:
        """POST リクエスト成功時に json_body が送信される."""
        body = {"response": {"token": "abc"}, "messages": [{"code": "0"}]}
        mock_httpx_client.request.return_value = _make_response(json_data=body)
        payload = {"query": [{"name": "test"}]}

        client.request("POST", "/fmi/data/v1/sessions", json_body=payload)

        call_kwargs = mock_httpx_client.request.call_args
        assert call_kwargs.kwargs["json"] == payload

    def test_api_info_contains_method_url_duration(
        self, client: HttpClient, mock_httpx_client: MagicMock
    ) -> None:
        """ApiInfo に method, url, duration_ms が含まれる."""
        mock_httpx_client.request.return_value = _make_response()

        _, api_info = client.request("GET", "/test")

        assert api_info.method == "GET"
        assert api_info.url == f"{BASE_URL}/test"
        assert api_info.duration_ms is not None
        assert api_info.duration_ms >= 0

    def test_params_passed_as_query_parameters(
        self, client: HttpClient, mock_httpx_client: MagicMock
    ) -> None:
        """params が正しくクエリパラメータとして付与される."""
        mock_httpx_client.request.return_value = _make_response()
        params = {"_limit": "10", "_offset": "0"}

        client.request("GET", "/records", params=params)

        call_kwargs = mock_httpx_client.request.call_args
        assert call_kwargs.kwargs["params"] == params

    def test_headers_passed_to_request(
        self, client: HttpClient, mock_httpx_client: MagicMock
    ) -> None:
        """headers が正しくリクエストに渡される."""
        mock_httpx_client.request.return_value = _make_response()
        headers = {"Authorization": "Bearer token123"}

        client.request("GET", "/records", headers=headers)

        call_kwargs = mock_httpx_client.request.call_args
        assert call_kwargs.kwargs["headers"] == headers

    def test_base_url_trailing_slash_stripped(self, mock_httpx_client: MagicMock) -> None:
        """base_url 末尾のスラッシュが除去される."""
        with patch("fmcli.infra.http_client.httpx.Client", return_value=mock_httpx_client):
            c = HttpClient("https://fm.example.com/")
        mock_httpx_client.request.return_value = _make_response()

        _, api_info = c.request("GET", "/test")

        assert api_info.url == "https://fm.example.com/test"


class TestHttpClientErrors:
    """request() メソッドのエラー系テスト."""

    def test_400_raises_api_error(self, client: HttpClient, mock_httpx_client: MagicMock) -> None:
        """400 エラー時に ApiError が発生する."""
        mock_httpx_client.request.return_value = _make_response(
            status_code=400,
            json_data={
                "messages": [{"code": "500", "message": "Date value is invalid"}],
            },
            reason_phrase="Bad Request",
        )

        with pytest.raises(ApiError) as exc_info:
            client.request("POST", "/records")

        err = exc_info.value
        assert err.http_status == 400
        assert err.api_code == 500
        assert "Date value is invalid" in str(err)
        assert err.retryable is False

    def test_401_raises_auth_error(self, client: HttpClient, mock_httpx_client: MagicMock) -> None:
        """401 エラー時に AuthError が発生する."""
        mock_httpx_client.request.return_value = _make_response(
            status_code=401,
            json_data={
                "messages": [{"code": "952", "message": "Invalid FileMaker Data API token"}],
            },
            reason_phrase="Unauthorized",
        )

        with pytest.raises(AuthError) as exc_info:
            client.request("GET", "/records")

        err = exc_info.value
        assert err.error_type == "auth_expired"
        assert err.retryable is True

    def test_401_non_952_raises_auth_invalid(
        self, client: HttpClient, mock_httpx_client: MagicMock
    ) -> None:
        """401 エラーで api_code が 952 以外の場合 auth_invalid になる."""
        mock_httpx_client.request.return_value = _make_response(
            status_code=401,
            json_data={
                "messages": [{"code": "0", "message": "Unauthorized"}],
            },
            reason_phrase="Unauthorized",
        )

        with pytest.raises(AuthError) as exc_info:
            client.request("GET", "/records")

        err = exc_info.value
        assert err.error_type == "auth_invalid"
        assert err.retryable is False

    def test_403_raises_auth_forbidden(
        self, client: HttpClient, mock_httpx_client: MagicMock
    ) -> None:
        """403 エラー時に AuthError(auth_forbidden) が発生する."""
        mock_httpx_client.request.return_value = _make_response(
            status_code=403,
            json_data={
                "messages": [{"code": "0", "message": "Forbidden"}],
            },
            reason_phrase="Forbidden",
        )

        with pytest.raises(AuthError) as exc_info:
            client.request("GET", "/records")

        err = exc_info.value
        assert err.error_type == "auth_forbidden"
        assert err.retryable is False

    def test_404_non_json_raises_api_error_with_code_0(
        self, client: HttpClient, mock_httpx_client: MagicMock
    ) -> None:
        """404 エラーで JSON でない場合 api_code=0 になる."""
        mock_httpx_client.request.return_value = _make_response(
            status_code=404,
            content_type="text/html",
            reason_phrase="Not Found",
        )

        with pytest.raises(ApiError) as exc_info:
            client.request("GET", "/records/999")

        err = exc_info.value
        assert err.http_status == 404
        assert err.api_code == 0
        assert err.retryable is False

    def test_404_json_raises_api_error_with_api_code(
        self, client: HttpClient, mock_httpx_client: MagicMock
    ) -> None:
        """404 エラーで JSON の場合 api_code がレスポンスから取得される."""
        mock_httpx_client.request.return_value = _make_response(
            status_code=404,
            json_data={
                "messages": [{"code": "401", "message": "No records match the request"}],
            },
            reason_phrase="Not Found",
        )

        with pytest.raises(ApiError) as exc_info:
            client.request("GET", "/records")

        err = exc_info.value
        assert err.http_status == 404
        assert err.api_code == 401

    def test_500_raises_api_error_not_retryable(
        self, client: HttpClient, mock_httpx_client: MagicMock
    ) -> None:
        """500 エラー時に ApiError が発生し retryable=False."""
        mock_httpx_client.request.return_value = _make_response(
            status_code=500,
            json_data={"messages": [{"code": "0", "message": "Internal Server Error"}]},
            reason_phrase="Internal Server Error",
        )

        with pytest.raises(ApiError) as exc_info:
            client.request("GET", "/records")

        err = exc_info.value
        assert err.http_status == 500
        assert err.retryable is False

    def test_503_raises_api_error_retryable(
        self, client: HttpClient, mock_httpx_client: MagicMock
    ) -> None:
        """503 エラー時に ApiError が発生し retryable=True."""
        mock_httpx_client.request.return_value = _make_response(
            status_code=503,
            json_data={"messages": [{"code": "0", "message": "Service Unavailable"}]},
            reason_phrase="Service Unavailable",
        )

        with pytest.raises(ApiError) as exc_info:
            client.request("GET", "/records")

        err = exc_info.value
        assert err.http_status == 503
        assert err.retryable is True

    def test_429_raises_api_error_retryable(
        self, client: HttpClient, mock_httpx_client: MagicMock
    ) -> None:
        """429 エラー時に ApiError が発生し retryable=True."""
        mock_httpx_client.request.return_value = _make_response(
            status_code=429,
            json_data={"messages": [{"code": "0", "message": "Too Many Requests"}]},
            reason_phrase="Too Many Requests",
        )

        with pytest.raises(ApiError) as exc_info:
            client.request("GET", "/records")

        err = exc_info.value
        assert err.http_status == 429
        assert err.retryable is True

    def test_transport_error_raises_transport_error(
        self, client: HttpClient, mock_httpx_client: MagicMock
    ) -> None:
        """httpx.TransportError 時に TransportError が発生する."""
        mock_httpx_client.request.side_effect = httpx.ConnectError("Connection refused")

        with pytest.raises(TransportError, match="Connection refused"):
            client.request("GET", "/records")

    def test_error_with_empty_messages_uses_reason_phrase(
        self, client: HttpClient, mock_httpx_client: MagicMock
    ) -> None:
        """messages が空配列の場合 reason_phrase がメッセージになる."""
        mock_httpx_client.request.return_value = _make_response(
            status_code=400,
            json_data={"messages": []},
            reason_phrase="Bad Request",
        )

        with pytest.raises(ApiError) as exc_info:
            client.request("GET", "/records")

        err = exc_info.value
        assert err.api_code == 0
        assert "Bad Request" in str(err)

    def test_error_with_no_messages_key(
        self, client: HttpClient, mock_httpx_client: MagicMock
    ) -> None:
        """messages キーがない JSON の場合 api_code=0."""
        mock_httpx_client.request.return_value = _make_response(
            status_code=400,
            json_data={"error": "something"},
            reason_phrase="Bad Request",
        )

        with pytest.raises(ApiError) as exc_info:
            client.request("GET", "/records")

        err = exc_info.value
        assert err.api_code == 0


class TestHttpClientContextManager:
    """context manager のテスト."""

    def test_close_called_on_exit(self, mock_httpx_client: MagicMock) -> None:
        """with 文で使用後に close() が呼ばれる."""
        with (
            patch("fmcli.infra.http_client.httpx.Client", return_value=mock_httpx_client),
            HttpClient(BASE_URL) as c,
        ):
            assert c is not None

        mock_httpx_client.close.assert_called_once()

    def test_close_called_explicitly(
        self, client: HttpClient, mock_httpx_client: MagicMock
    ) -> None:
        """close() を明示的に呼ぶと httpx.Client.close() が呼ばれる."""
        client.close()

        mock_httpx_client.close.assert_called_once()


class TestHttpClientInit:
    """__init__ のテスト."""

    def test_default_parameters(self) -> None:
        """デフォルトパラメータで httpx.Client が初期化される."""
        with patch("fmcli.infra.http_client.httpx.Client") as mock_cls:
            HttpClient("https://fm.example.com")

        mock_cls.assert_called_once_with(verify=True, timeout=60)

    def test_custom_parameters(self) -> None:
        """カスタムパラメータで httpx.Client が初期化される."""
        with patch("fmcli.infra.http_client.httpx.Client") as mock_cls:
            HttpClient("https://fm.example.com", verify_ssl=False, timeout=30)

        mock_cls.assert_called_once_with(verify=False, timeout=30)


class TestMaskUrl:
    """URL マスキングのテスト."""

    def test_masks_session_token(self) -> None:
        url = "https://fm.example.com/fmi/data/vLatest/databases/DB/sessions/abc123"
        assert (
            mask_url(url)
            == "https://fm.example.com/fmi/data/vLatest/databases/DB/sessions/********...c123"
        )

    def test_no_token_unchanged(self) -> None:
        url = "https://fm.example.com/fmi/data/vLatest/databases/DB/layouts"
        assert mask_url(url) == url


class TestHttpClientLogging:
    """HTTP クライアントのログ出力テスト."""

    def test_logs_request_and_response(
        self, client: HttpClient, mock_httpx_client: MagicMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """正常リクエスト時にリクエスト/レスポンスがログされる."""
        mock_httpx_client.request.return_value = _make_response(
            status_code=200,
            json_data={"response": {}},
        )

        with caplog.at_level("DEBUG", logger="fmcli.infra.http_client"):
            client.request("GET", "/test")

        messages = [r.message for r in caplog.records]
        assert any("-> GET" in m for m in messages)
        assert any("<- GET 200" in m for m in messages)

    def test_logs_transport_error(
        self, client: HttpClient, mock_httpx_client: MagicMock, caplog: pytest.LogCaptureFixture
    ) -> None:
        """トランスポートエラー時にログされる."""
        import httpx as _httpx

        mock_httpx_client.request.side_effect = _httpx.ConnectError("Connection refused")

        with (
            caplog.at_level("DEBUG", logger="fmcli.infra.http_client"),
            pytest.raises(TransportError),
        ):
            client.request("GET", "/test")
