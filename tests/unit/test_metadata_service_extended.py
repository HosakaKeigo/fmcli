"""metadata_service の追加テスト — エラーケース・エッジケース."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from fmcli.core.errors import ApiError, AuthError, TransportError
from fmcli.domain.envelopes import ApiInfo
from fmcli.domain.models import Profile
from fmcli.services import metadata_service


def _profile() -> Profile:
    return Profile(name="test", host="https://fm.example.com", database="TestDB")


def _api_info(
    method: str = "GET",
    url: str = "https://fm.example.com/fmi/data/vLatest/",
) -> ApiInfo:
    return ApiInfo(method=method, url=url)


# ---------------------------------------------------------------------------
# host_info エラーケース
# ---------------------------------------------------------------------------
class TestHostInfoErrors:
    """host_info のエラーケース."""

    @patch("fmcli.services.metadata_service.create_api")
    def test_API例外がそのまま伝播する(self, mock_create_api: MagicMock) -> None:
        mock_api = MagicMock()
        mock_create_api.return_value = mock_api
        mock_api.get_product_info.side_effect = TransportError("接続できません")

        with pytest.raises(TransportError, match="接続できません"):
            metadata_service.host_info(_profile())


# ---------------------------------------------------------------------------
# database_list 追加テスト
# ---------------------------------------------------------------------------
class TestDatabaseListExtended:
    """database_list の追加テスト."""

    @patch("fmcli.services.metadata_service.create_api")
    def test_空のデータベース一覧(
        self,
        mock_create_api: MagicMock,
    ) -> None:
        mock_api = MagicMock()
        mock_create_api.return_value = mock_api
        mock_api.get_databases.return_value = (
            {"response": {"databases": []}},
            _api_info(),
        )

        envelope = metadata_service.database_list(_profile(), username="admin", password="pass")

        assert envelope.ok is True
        assert envelope.data == []

    @patch("fmcli.services.metadata_service.create_api")
    def test_API例外がそのまま伝播する(
        self,
        mock_create_api: MagicMock,
    ) -> None:
        mock_api = MagicMock()
        mock_create_api.return_value = mock_api
        mock_api.get_databases.side_effect = ApiError(
            "認証失敗",
            http_status=401,
            api_code=212,
        )

        with pytest.raises(ApiError, match="認証失敗"):
            metadata_service.database_list(_profile(), username="bad", password="cred")

    @patch("fmcli.infra.auth_store.load_credential")
    def test_password_only_triggers_keyring_fallback(self, mock_load_credential: MagicMock) -> None:
        """password だけ指定して username が None の場合も keyring フォールバックする."""
        mock_load_credential.return_value = None

        with pytest.raises(AuthError, match="認証情報がありません"):
            metadata_service.database_list(_profile(), username=None, password="secret")

    @patch("fmcli.services.metadata_service.create_api")
    def test_レスポンスにdatabasesキーがない場合は空リスト(
        self,
        mock_create_api: MagicMock,
    ) -> None:
        mock_api = MagicMock()
        mock_create_api.return_value = mock_api
        mock_api.get_databases.return_value = (
            {"response": {}},
            _api_info(),
        )

        envelope = metadata_service.database_list(_profile(), username="admin", password="pass")

        assert envelope.data == []


# ---------------------------------------------------------------------------
# layout_list 追加テスト
# ---------------------------------------------------------------------------
class TestLayoutListExtended:
    """layout_list の追加テスト."""

    @patch("fmcli.services.metadata_service.call_with_refresh")
    def test_ネストされたレイアウト(self, mock_call: MagicMock) -> None:
        """フォルダ構造を持つレイアウト一覧."""
        layouts = [
            {"name": "Contacts", "isFolder": False},
            {
                "name": "Admin",
                "isFolder": True,
                "folderLayoutNames": [{"name": "Users"}, {"name": "Roles"}],
            },
        ]
        mock_call.return_value = (
            {"response": {"layouts": layouts}},
            _api_info(),
        )

        envelope = metadata_service.layout_list(_profile())

        assert len(envelope.data) == 2
        assert envelope.data[1]["isFolder"] is True

    @patch("fmcli.services.metadata_service.call_with_refresh")
    def test_call_with_refreshにprofileが渡される(self, mock_call: MagicMock) -> None:
        mock_call.return_value = (
            {"response": {"layouts": []}},
            _api_info(),
        )

        profile = _profile()
        metadata_service.layout_list(profile)

        call_args = mock_call.call_args
        assert call_args[0][0] is profile

    @patch("fmcli.services.metadata_service.call_with_refresh")
    def test_AuthErrorが伝播する(self, mock_call: MagicMock) -> None:
        mock_call.side_effect = AuthError(
            "セッション切れ",
            error_type="auth_required",
            host="https://fm.example.com",
            database="TestDB",
        )

        with pytest.raises(AuthError, match="セッション切れ"):
            metadata_service.layout_list(_profile())

    @patch("fmcli.services.metadata_service.call_with_refresh")
    def test_レスポンスにlayoutsキーがない場合は空リスト(self, mock_call: MagicMock) -> None:
        mock_call.return_value = (
            {"response": {}},
            _api_info(),
        )

        envelope = metadata_service.layout_list(_profile())

        assert envelope.data == []


# ---------------------------------------------------------------------------
# layout_describe 追加テスト
# ---------------------------------------------------------------------------
class TestLayoutDescribeExtended:
    """layout_describe の追加テスト."""

    @patch("fmcli.services.metadata_service.call_with_refresh")
    def test_複数フィールドの型情報が保持される(self, mock_call: MagicMock) -> None:
        fields = [
            {"name": "Name", "result": "text", "type": "normal", "global": False},
            {"name": "BirthDate", "result": "date", "type": "normal", "global": False},
            {"name": "Photo", "result": "container", "type": "normal", "global": False},
        ]
        mock_call.return_value = (
            {"response": {"fieldMetaData": fields, "portalMetaData": {}, "valueLists": []}},
            _api_info(),
        )

        envelope = metadata_service.layout_describe(_profile(), "Contacts")

        assert len(envelope.data["fieldMetaData"]) == 3
        assert envelope.data["fieldMetaData"][0]["result"] == "text"
        assert envelope.data["fieldMetaData"][2]["result"] == "container"

    @patch("fmcli.services.metadata_service.call_with_refresh")
    def test_複数ポータルのメタデータ(self, mock_call: MagicMock) -> None:
        portals = {
            "Orders": [{"name": "Orders::ID"}, {"name": "Orders::Amount"}],
            "Addresses": [{"name": "Addresses::City"}],
        }
        mock_call.return_value = (
            {"response": {"fieldMetaData": [], "portalMetaData": portals, "valueLists": []}},
            _api_info(),
        )

        envelope = metadata_service.layout_describe(_profile(), "Contacts")

        assert len(envelope.data["portalMetaData"]) == 2
        assert len(envelope.data["portalMetaData"]["Orders"]) == 2

    @patch("fmcli.services.metadata_service.call_with_refresh")
    def test_値リスト付きレイアウト(self, mock_call: MagicMock) -> None:
        value_lists = [
            {"name": "Status", "type": "customList", "values": [{"value": "A"}, {"value": "B"}]},
            {"name": "Category", "type": "valueListFromField", "values": []},
        ]
        mock_call.return_value = (
            {
                "response": {
                    "fieldMetaData": [],
                    "portalMetaData": {},
                    "valueLists": value_lists,
                }
            },
            _api_info(),
        )

        envelope = metadata_service.layout_describe(_profile(), "Contacts")

        assert len(envelope.data["valueLists"]) == 2
        assert envelope.data["valueLists"][0]["name"] == "Status"

    @patch("fmcli.services.metadata_service.call_with_refresh")
    def test_ApiErrorが伝播する(self, mock_call: MagicMock) -> None:
        mock_call.side_effect = ApiError(
            "レイアウトが見つかりません",
            http_status=404,
            api_code=105,
        )

        with pytest.raises(ApiError, match="レイアウトが見つかりません"):
            metadata_service.layout_describe(_profile(), "NonExistent")


# ---------------------------------------------------------------------------
# layout_value_lists 追加テスト
# ---------------------------------------------------------------------------
class TestLayoutValueListsExtended:
    """layout_value_lists の追加テスト."""

    @patch("fmcli.services.metadata_service.call_with_refresh")
    def test_複数の値リストをフォーマットする(self, mock_call: MagicMock) -> None:
        value_lists = [
            {
                "name": "Status",
                "type": "customList",
                "values": [{"value": "Active"}, {"value": "Inactive"}],
            },
            {
                "name": "Colors",
                "type": "customList",
                "values": [{"value": "Red"}, {"value": "Blue"}, {"value": "Green"}],
            },
        ]
        mock_call.return_value = (
            {"response": {"valueLists": value_lists}},
            _api_info(),
        )

        envelope = metadata_service.layout_value_lists(_profile(), "Contacts")

        assert len(envelope.data) == 2
        assert envelope.data[0]["count"] == 2
        assert envelope.data[1]["count"] == 3
        assert envelope.data[1]["name"] == "Colors"

    @patch("fmcli.services.metadata_service.call_with_refresh")
    def test_値のない値リスト(self, mock_call: MagicMock) -> None:
        """values キーが空リストの値リスト."""
        value_lists = [{"name": "Empty", "type": "customList", "values": []}]
        mock_call.return_value = (
            {"response": {"valueLists": value_lists}},
            _api_info(),
        )

        envelope = metadata_service.layout_value_lists(_profile(), "Contacts")

        assert envelope.data[0]["count"] == 0
        assert envelope.data[0]["values"] == []

    @patch("fmcli.services.metadata_service.call_with_refresh")
    def test_typeやnameがない値リスト(self, mock_call: MagicMock) -> None:
        """不完全なデータの値リスト."""
        value_lists = [{"values": [{"value": "X"}]}]
        mock_call.return_value = (
            {"response": {"valueLists": value_lists}},
            _api_info(),
        )

        envelope = metadata_service.layout_value_lists(_profile(), "Contacts")

        assert envelope.data[0]["name"] == ""
        assert envelope.data[0]["type"] == ""
        assert envelope.data[0]["count"] == 1


# ---------------------------------------------------------------------------
# script_list 追加テスト
# ---------------------------------------------------------------------------
class TestScriptListExtended:
    """script_list の追加テスト."""

    @patch("fmcli.services.metadata_service.call_with_refresh")
    def test_フォルダとスクリプトの混在(self, mock_call: MagicMock) -> None:
        scripts = [
            {"name": "RunReport", "isFolder": False},
            {
                "name": "Utilities",
                "isFolder": True,
                "folderScriptNames": [{"name": "CleanUp"}],
            },
            {"name": "SendEmail", "isFolder": False},
        ]
        mock_call.return_value = (
            {"response": {"scripts": scripts}},
            _api_info(),
        )

        envelope = metadata_service.script_list(_profile())

        assert len(envelope.data) == 3
        assert envelope.data[1]["isFolder"] is True

    @patch("fmcli.services.metadata_service.call_with_refresh")
    def test_AuthErrorが伝播する(self, mock_call: MagicMock) -> None:
        mock_call.side_effect = AuthError(
            "セッション切れ",
            error_type="auth_required",
            host="https://fm.example.com",
            database="TestDB",
        )

        with pytest.raises(AuthError, match="セッション切れ"):
            metadata_service.script_list(_profile())

    @patch("fmcli.services.metadata_service.call_with_refresh")
    def test_レスポンスにscriptsキーがない場合は空リスト(self, mock_call: MagicMock) -> None:
        mock_call.return_value = (
            {"response": {}},
            _api_info(),
        )

        envelope = metadata_service.script_list(_profile())

        assert envelope.data == []

    @patch("fmcli.services.metadata_service.call_with_refresh")
    def test_call_with_refreshにprofileが渡される(self, mock_call: MagicMock) -> None:
        mock_call.return_value = (
            {"response": {"scripts": []}},
            _api_info(),
        )

        profile = _profile()
        metadata_service.script_list(profile)

        call_args = mock_call.call_args
        assert call_args[0][0] is profile
