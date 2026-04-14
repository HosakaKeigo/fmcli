"""URL エンコードのテスト."""

from __future__ import annotations

from unittest.mock import Mock
from urllib.parse import quote

from fmcli.domain.envelopes import ApiInfo
from fmcli.infra.filemaker_api import FMDATA_API_BASE, FileMakerAPI


def _make_api(database: str) -> tuple[FileMakerAPI, Mock]:
    """テスト用 API インスタンスを生成する."""
    mock_client = Mock()
    mock_client.request.return_value = (
        {"response": {}, "messages": [{"code": "0", "message": "OK"}]},
        ApiInfo(method="GET", url="dummy"),
    )
    api = FileMakerAPI(mock_client, database)
    api.set_token("test-token")
    return api, mock_client


class TestUrlEncodingSpaces:
    """スペースを含むレイアウト名・データベース名のエンコードテスト."""

    def test_get_layout_metadata_encodes_spaces(self) -> None:
        api, client = _make_api("My Database")
        api.get_layout_metadata("My Layout")

        path = client.request.call_args[0][1]
        assert quote("My Database", safe="") in path
        assert quote("My Layout", safe="") in path
        assert "My Database" not in path
        assert "My Layout" not in path

    def test_get_record_encodes_spaces(self) -> None:
        api, client = _make_api("My DB")
        api.get_record("Contact List", 1)

        path = client.request.call_args[0][1]
        assert quote("My DB", safe="") in path
        assert quote("Contact List", safe="") in path

    def test_find_records_encodes_spaces(self) -> None:
        api, client = _make_api("My DB")
        api.find_records("Contact List", [{"Name": "Test"}])

        path = client.request.call_args[0][1]
        assert quote("My DB", safe="") in path
        assert quote("Contact List", safe="") in path

    def test_get_layouts_encodes_database(self) -> None:
        api, client = _make_api("My Database")
        api.get_layouts()

        path = client.request.call_args[0][1]
        assert quote("My Database", safe="") in path
        assert "My Database" not in path


class TestUrlEncodingJapanese:
    """日本語を含むレイアウト名・データベース名のエンコードテスト."""

    def test_get_layout_metadata_encodes_japanese(self) -> None:
        api, client = _make_api("顧客管理")
        api.get_layout_metadata("連絡先一覧")

        path = client.request.call_args[0][1]
        assert quote("顧客管理", safe="") in path
        assert quote("連絡先一覧", safe="") in path
        assert "顧客管理" not in path
        assert "連絡先一覧" not in path

    def test_find_records_encodes_japanese(self) -> None:
        api, client = _make_api("顧客管理")
        api.find_records("連絡先一覧", [{"名前": "テスト"}])

        path = client.request.call_args[0][1]
        assert quote("顧客管理", safe="") in path
        assert quote("連絡先一覧", safe="") in path


class TestGetRecordsParams:
    """get_records が httpx の params 引数を使用するテスト."""

    def test_get_records_uses_params_argument(self) -> None:
        api, client = _make_api("TestDB")
        api.get_records("TestLayout", offset=5, limit=50)

        # path にクエリ文字列が含まれないことを確認
        path = client.request.call_args[0][1]
        assert "?" not in path
        assert f"{FMDATA_API_BASE}/databases/TestDB/layouts/TestLayout/records" == path

        # params が正しく渡されていることを確認
        kwargs = client.request.call_args[1]
        assert kwargs["params"] == {"_offset": "5", "_limit": "50"}

    def test_get_records_with_sort_uses_params(self) -> None:
        api, client = _make_api("TestDB")
        sort = [{"fieldName": "Name", "sortOrder": "ascend"}]
        api.get_records("TestLayout", sort=sort)

        kwargs = client.request.call_args[1]
        params = kwargs["params"]
        assert "_sort" in params
        assert "_offset" in params
        assert "_limit" in params

    def test_get_records_encodes_layout_with_spaces(self) -> None:
        api, client = _make_api("My DB")
        api.get_records("My Layout")

        path = client.request.call_args[0][1]
        assert quote("My DB", safe="") in path
        assert quote("My Layout", safe="") in path
        assert "?" not in path


class TestFindRecordsParams:
    """find_records の POST body 組み立てテスト."""

    def test_find_records_basic_body(self) -> None:
        api, client = _make_api("TestDB")
        api.find_records("TestLayout", [{"Name": "Test"}])

        kwargs = client.request.call_args[1]
        body = kwargs["json_body"]
        assert body["query"] == [{"Name": "Test"}]
        assert body["offset"] == "1"
        assert body["limit"] == "100"
