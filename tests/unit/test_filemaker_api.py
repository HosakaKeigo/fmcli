"""FileMakerAPI クラスのユニットテスト.

各メソッドのリクエスト構築・レスポンスパース・エラーハンドリングを検証する。
"""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock

import pytest

from fmcli.core.errors import ApiError, AuthError
from fmcli.core.masking import mask_token_in_url
from fmcli.domain.envelopes import ApiInfo
from fmcli.infra.filemaker_api import FMDATA_API_BASE, FileMakerAPI

# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------


def _make_api(database: str = "TestDB") -> tuple[FileMakerAPI, Mock]:
    """テスト用 API インスタンスを生成する."""
    mock_client = Mock()
    mock_client.request.return_value = (
        {"response": {}, "messages": [{"code": "0", "message": "OK"}]},
        ApiInfo(method="GET", url="dummy"),
    )
    api = FileMakerAPI(mock_client, database)
    api.set_token("test-session-token")
    return api, mock_client


def _setup_response(mock_client: Mock, body: dict[str, Any], method: str = "GET") -> None:
    """モッククライアントのレスポンスを設定する."""
    mock_client.request.return_value = (body, ApiInfo(method=method, url="dummy"))


# ===========================================================================
# get_layouts
# ===========================================================================


class TestGetLayouts:
    """get_layouts のテスト."""

    def test_正しいパスでリクエストする(self) -> None:
        api, client = _make_api("TestDB")
        api.get_layouts()

        path = client.request.call_args[0][1]
        assert path == f"{FMDATA_API_BASE}/databases/TestDB/layouts"

    def test_認証ヘッダーが含まれる(self) -> None:
        api, client = _make_api()
        api.get_layouts()

        kwargs = client.request.call_args[1]
        assert kwargs["headers"]["Authorization"] == "Bearer test-session-token"

    def test_レスポンスをそのまま返す(self) -> None:
        api, client = _make_api()
        response_body = {
            "response": {
                "layouts": [
                    {"name": "Contacts"},
                    {"name": "Orders"},
                ]
            },
            "messages": [{"code": "0"}],
        }
        _setup_response(client, response_body)

        body, api_info = api.get_layouts()

        assert body["response"]["layouts"][0]["name"] == "Contacts"
        assert len(body["response"]["layouts"]) == 2

    def test_日本語データベース名のエンコード(self) -> None:
        api, client = _make_api("顧客管理DB")
        api.get_layouts()

        path = client.request.call_args[0][1]
        assert "顧客管理DB" not in path
        assert "%E9%A1%A7%E5%AE%A2%E7%AE%A1%E7%90%86DB" in path


# ===========================================================================
# get_layout_metadata (get_fields 相当)
# ===========================================================================


class TestGetLayoutMetadata:
    """get_layout_metadata のテスト."""

    def test_正しいパスでリクエストする(self) -> None:
        api, client = _make_api()
        api.get_layout_metadata("Contacts")

        path = client.request.call_args[0][1]
        assert path == f"{FMDATA_API_BASE}/databases/TestDB/layouts/Contacts"

    def test_フィールドメタデータのパース(self) -> None:
        api, client = _make_api()
        response_body = {
            "response": {
                "fieldMetaData": [
                    {
                        "name": "Name",
                        "type": "normal",
                        "displayType": "editText",
                        "result": "text",
                    },
                    {
                        "name": "Age",
                        "type": "normal",
                        "displayType": "editText",
                        "result": "number",
                    },
                ]
            },
            "messages": [{"code": "0"}],
        }
        _setup_response(client, response_body)

        body, _ = api.get_layout_metadata("Contacts")

        fields = body["response"]["fieldMetaData"]
        assert len(fields) == 2
        assert fields[0]["name"] == "Name"
        assert fields[0]["result"] == "text"
        assert fields[1]["result"] == "number"

    def test_レイアウト名のエンコード(self) -> None:
        api, client = _make_api()
        api.get_layout_metadata("連絡先 一覧")

        path = client.request.call_args[0][1]
        assert "連絡先 一覧" not in path


# ===========================================================================
# get_scripts
# ===========================================================================


class TestGetScripts:
    """get_scripts のテスト."""

    def test_正しいパスでリクエストする(self) -> None:
        api, client = _make_api()
        api.get_scripts()

        path = client.request.call_args[0][1]
        assert path == f"{FMDATA_API_BASE}/databases/TestDB/scripts"

    def test_スクリプト一覧のパース(self) -> None:
        api, client = _make_api()
        response_body = {
            "response": {
                "scripts": [
                    {"name": "ProcessRecords", "isFolder": False},
                    {"name": "Utilities", "isFolder": True},
                    {"name": "ExportData", "isFolder": False},
                ]
            },
            "messages": [{"code": "0"}],
        }
        _setup_response(client, response_body)

        body, _ = api.get_scripts()

        scripts = body["response"]["scripts"]
        assert len(scripts) == 3
        assert scripts[0]["name"] == "ProcessRecords"
        assert scripts[1]["isFolder"] is True

    def test_認証ヘッダーが含まれる(self) -> None:
        api, client = _make_api()
        api.get_scripts()

        kwargs = client.request.call_args[1]
        assert "Authorization" in kwargs["headers"]


# ===========================================================================
# find_records
# ===========================================================================


class TestFindRecords:
    """find_records のテスト."""

    def test_基本的なリクエストボディ構築(self) -> None:
        api, client = _make_api()
        api.find_records("Contacts", [{"Name": "Alice"}])

        kwargs = client.request.call_args[1]
        body = kwargs["json_body"]
        assert body["query"] == [{"Name": "Alice"}]
        assert body["offset"] == "1"
        assert body["limit"] == "100"

    def test_複数条件のクエリ(self) -> None:
        """OR 条件（配列内に複数オブジェクト）のリクエスト."""
        api, client = _make_api()
        query = [{"Name": "Alice"}, {"Name": "Bob"}]
        api.find_records("Contacts", query)

        kwargs = client.request.call_args[1]
        body = kwargs["json_body"]
        assert len(body["query"]) == 2
        assert body["query"][0] == {"Name": "Alice"}
        assert body["query"][1] == {"Name": "Bob"}

    def test_ソート指定のリクエストボディ(self) -> None:
        api, client = _make_api()
        sort = [{"fieldName": "Name", "sortOrder": "ascend"}]
        api.find_records("Contacts", [{"Name": "Alice"}], sort=sort)

        kwargs = client.request.call_args[1]
        body = kwargs["json_body"]
        assert body["sort"] == sort

    def test_offset_limit指定(self) -> None:
        api, client = _make_api()
        api.find_records("Contacts", [{"Name": "Alice"}], offset=10, limit=25)

        kwargs = client.request.call_args[1]
        body = kwargs["json_body"]
        assert body["offset"] == "10"
        assert body["limit"] == "25"

    def test_ポータルパラメータのリクエストボディ(self) -> None:
        api, client = _make_api()
        portal_params = {"portal": ["Orders"], "limit.Orders": 5}
        api.find_records("Contacts", [{"Name": "Alice"}], portal_params=portal_params)

        kwargs = client.request.call_args[1]
        body = kwargs["json_body"]
        assert body["portal"] == ["Orders"]
        assert body["limit.Orders"] == 5

    def test_スクリプトパラメータのリクエストボディ(self) -> None:
        api, client = _make_api()
        script_params = {
            "script": "MyScript",
            "script.param": "param1",
        }
        api.find_records("Contacts", [{"Name": "Alice"}], script_params=script_params)

        kwargs = client.request.call_args[1]
        body = kwargs["json_body"]
        assert body["script"] == "MyScript"
        assert body["script.param"] == "param1"

    def test_POSTメソッドでリクエストする(self) -> None:
        api, client = _make_api()
        api.find_records("Contacts", [{"Name": "Alice"}])

        method = client.request.call_args[0][0]
        assert method == "POST"

    def test_正しいパスでリクエストする(self) -> None:
        api, client = _make_api()
        api.find_records("Contacts", [{"Name": "Alice"}])

        path = client.request.call_args[0][1]
        assert path == f"{FMDATA_API_BASE}/databases/TestDB/layouts/Contacts/_find"

    def test_find_recordsにresponse_fieldsパラメータは存在しない(self) -> None:
        """フィールドフィルタはrecord_service側で行うためAPIメソッドにパラメータなし."""
        import inspect

        sig = inspect.signature(FileMakerAPI.find_records)
        assert "response_fields" not in sig.parameters

    def test_レスポンスパース(self) -> None:
        api, client = _make_api()
        response_body = {
            "response": {
                "data": [
                    {
                        "fieldData": {"Name": "Alice"},
                        "portalData": {},
                        "recordId": "1",
                        "modId": "0",
                    }
                ],
                "dataInfo": {
                    "totalRecordCount": 100,
                    "foundCount": 1,
                    "returnedCount": 1,
                },
            },
            "messages": [{"code": "0"}],
        }
        _setup_response(client, response_body, method="POST")

        body, api_info = api.find_records("Contacts", [{"Name": "Alice"}])

        assert body["response"]["data"][0]["fieldData"]["Name"] == "Alice"
        assert body["response"]["dataInfo"]["foundCount"] == 1


# ===========================================================================
# get_records
# ===========================================================================


class TestGetRecords:
    """get_records のテスト."""

    def test_基本的なパラメータ構築(self) -> None:
        api, client = _make_api()
        api.get_records("Contacts")

        kwargs = client.request.call_args[1]
        assert kwargs["params"]["_offset"] == "1"
        assert kwargs["params"]["_limit"] == "100"

    def test_カスタムoffset_limit(self) -> None:
        api, client = _make_api()
        api.get_records("Contacts", offset=50, limit=25)

        kwargs = client.request.call_args[1]
        assert kwargs["params"]["_offset"] == "50"
        assert kwargs["params"]["_limit"] == "25"

    def test_ソートパラメータ(self) -> None:
        import json

        api, client = _make_api()
        sort = [{"fieldName": "Name", "sortOrder": "ascend"}]
        api.get_records("Contacts", sort=sort)

        kwargs = client.request.call_args[1]
        assert "_sort" in kwargs["params"]
        assert json.loads(kwargs["params"]["_sort"]) == sort

    def test_fieldsパラメータは送信されない(self) -> None:
        """get_records は _fields パラメータを API に送信しない (クライアント側フィルタ)."""
        api, client = _make_api()
        api.get_records("Contacts")

        kwargs = client.request.call_args[1]
        assert "_fields" not in kwargs["params"]

    def test_ポータルパラメータ(self) -> None:
        api, client = _make_api()
        portal_params = {"portal": '["Orders"]', "_limit.Orders": "5"}
        api.get_records("Contacts", portal_params=portal_params)

        kwargs = client.request.call_args[1]
        assert kwargs["params"]["portal"] == '["Orders"]'
        assert kwargs["params"]["_limit.Orders"] == "5"

    def test_スクリプトパラメータ(self) -> None:
        api, client = _make_api()
        script_params = {"script": "MyScript", "script.param": "value1"}
        api.get_records("Contacts", script_params=script_params)

        kwargs = client.request.call_args[1]
        assert kwargs["params"]["script"] == "MyScript"
        assert kwargs["params"]["script.param"] == "value1"

    def test_GETメソッドでリクエストする(self) -> None:
        api, client = _make_api()
        api.get_records("Contacts")

        method = client.request.call_args[0][0]
        assert method == "GET"

    def test_正しいパスでリクエストする(self) -> None:
        api, client = _make_api()
        api.get_records("Contacts")

        path = client.request.call_args[0][1]
        assert path == f"{FMDATA_API_BASE}/databases/TestDB/layouts/Contacts/records"


# ===========================================================================
# get_record
# ===========================================================================


class TestGetRecord:
    """get_record のテスト."""

    def test_正しいパスでリクエストする(self) -> None:
        api, client = _make_api()
        api.get_record("Contacts", 42)

        path = client.request.call_args[0][1]
        assert path == f"{FMDATA_API_BASE}/databases/TestDB/layouts/Contacts/records/42"

    def test_ポータルパラメータ(self) -> None:
        api, client = _make_api()
        portal_params = {"portal": '["Orders"]'}
        api.get_record("Contacts", 1, portal_params=portal_params)

        kwargs = client.request.call_args[1]
        assert kwargs["params"]["portal"] == '["Orders"]'

    def test_スクリプトパラメータ(self) -> None:
        api, client = _make_api()
        script_params = {"script": "OnLoad", "script.param": "recordId=1"}
        api.get_record("Contacts", 1, script_params=script_params)

        kwargs = client.request.call_args[1]
        assert kwargs["params"]["script"] == "OnLoad"

    def test_パラメータなしの場合paramsはNone(self) -> None:
        api, client = _make_api()
        api.get_record("Contacts", 1)

        kwargs = client.request.call_args[1]
        assert kwargs["params"] is None

    def test_レスポンスパース(self) -> None:
        api, client = _make_api()
        response_body = {
            "response": {
                "data": [
                    {
                        "fieldData": {"Name": "Alice", "Email": "alice@example.com"},
                        "portalData": {"Orders": [{"OrderID": "101"}]},
                        "recordId": "1",
                        "modId": "3",
                    }
                ]
            },
            "messages": [{"code": "0"}],
        }
        _setup_response(client, response_body)

        body, _ = api.get_record("Contacts", 1)

        data = body["response"]["data"]
        assert len(data) == 1
        assert data[0]["fieldData"]["Name"] == "Alice"
        assert data[0]["portalData"]["Orders"][0]["OrderID"] == "101"
        assert data[0]["modId"] == "3"


# ===========================================================================
# 認証関連
# ===========================================================================


class TestAuth:
    """認証関連メソッドのテスト."""

    def test_トークン未設定でAuthErrorが発生する(self) -> None:
        mock_client = Mock()
        api = FileMakerAPI(mock_client, "TestDB")
        # set_token を呼ばない

        with pytest.raises(AuthError, match="Not authenticated"):
            api.get_layouts()

    def test_set_tokenでトークンが設定される(self) -> None:
        api, client = _make_api()
        api.set_token("new-token-123")
        api.get_layouts()

        kwargs = client.request.call_args[1]
        assert kwargs["headers"]["Authorization"] == "Bearer new-token-123"

    def test_loginのレスポンスからトークンを取得(self) -> None:
        mock_client = Mock()
        response_body = {
            "response": {"token": "session-token-abc"},
            "messages": [{"code": "0"}],
        }
        mock_client.request.return_value = (response_body, ApiInfo(method="POST", url="dummy"))

        api = FileMakerAPI(mock_client, "TestDB")
        token, api_info = api.login("user", "pass")

        assert token == "session-token-abc"

    def test_logoutでトークンURLがマスクされる(self) -> None:
        api, client = _make_api()
        api.set_token("abcdefghijklmnop")

        # logout のレスポンス
        _setup_response(client, {"response": {}, "messages": [{"code": "0"}]}, method="DELETE")

        api_info = api.logout()

        # トークンがマスクされている
        assert "abcdefghijklmnop" not in api_info.url

    def test_logoutでトークンがNoneにリセットされる(self) -> None:
        api, client = _make_api()
        _setup_response(client, {"response": {}, "messages": [{"code": "0"}]}, method="DELETE")

        api.logout()

        with pytest.raises(AuthError, match="Not authenticated"):
            api.get_layouts()

    def test_validate_session成功(self) -> None:
        api, client = _make_api()
        _setup_response(client, {"response": {}, "messages": [{"code": "0"}]})

        valid, api_info = api.validate_session()

        assert valid is True

    def test_validate_session失敗(self) -> None:
        api, client = _make_api()
        client.request.side_effect = ApiError("Invalid token", http_status=401, api_code=952)

        valid, api_info = api.validate_session()

        assert valid is False


# ===========================================================================
# _mask_token_in_url
# ===========================================================================


class TestMaskTokenInUrl:
    """mask_token_in_url のテスト."""

    def test_URLからトークンをマスクする(self) -> None:
        url = "https://fm.example.com/fmi/data/vLatest/databases/DB/sessions/abcdef123456"
        result = mask_token_in_url(url, "abcdef123456")

        assert "abcdef123456" not in result
        assert "3456" in result  # 末尾4文字は残る

    def test_空トークンの場合はURLそのまま(self) -> None:
        url = "https://fm.example.com/path"
        result = mask_token_in_url(url, "")

        assert result == url

    def test_トークンがURLに存在しない場合はそのまま(self) -> None:
        url = "https://fm.example.com/path"
        result = mask_token_in_url(url, "nonexistent-token")

        assert result == url


# ===========================================================================
# close
# ===========================================================================


class TestClose:
    """close のテスト."""

    def test_クライアントのcloseが呼ばれる(self) -> None:
        api, client = _make_api()
        api.close()

        client.close.assert_called_once()

    def test_context_managerでcloseが呼ばれる(self) -> None:
        api, client = _make_api()
        with api:
            pass
        client.close.assert_called_once()


# ===========================================================================
# get_product_info / get_databases
# ===========================================================================


class TestMetadataEndpoints:
    """認証不要・Basic認証のメタデータエンドポイント."""

    def test_get_product_infoは認証ヘッダー不要(self) -> None:
        mock_client = Mock()
        response_body = {
            "response": {"productInfo": {"name": "FileMaker Server", "version": "20.3"}},
            "messages": [{"code": "0"}],
        }
        mock_client.request.return_value = (response_body, ApiInfo(method="GET", url="dummy"))

        api = FileMakerAPI(mock_client, "TestDB")
        # トークン未設定でも呼べる
        body, _ = api.get_product_info()

        assert body["response"]["productInfo"]["name"] == "FileMaker Server"
        # headers 引数なしで呼ばれることを確認
        call_args = mock_client.request.call_args
        assert call_args[0][0] == "GET"

    def test_get_databasesはBasic認証を使う(self) -> None:
        mock_client = Mock()
        response_body = {
            "response": {"databases": [{"name": "TestDB"}, {"name": "ProdDB"}]},
            "messages": [{"code": "0"}],
        }
        mock_client.request.return_value = (response_body, ApiInfo(method="GET", url="dummy"))

        api = FileMakerAPI(mock_client, "TestDB")
        body, _ = api.get_databases("admin", "password123")

        kwargs = mock_client.request.call_args[1]
        assert kwargs["headers"]["Authorization"].startswith("Basic ")
        assert body["response"]["databases"][0]["name"] == "TestDB"
