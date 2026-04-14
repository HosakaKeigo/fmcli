"""メタデータサービスのテスト."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from fmcli.core.errors import AuthError
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


class TestHostInfo:
    """host_info のテスト."""

    @patch("fmcli.services.metadata_service.create_api")
    def test_正常にホスト情報を取得できる(self, mock_create_api: MagicMock) -> None:
        mock_api = MagicMock()
        mock_create_api.return_value = mock_api
        product_info = {"name": "FileMaker", "version": "21.0"}
        mock_api.get_product_info.return_value = (
            {"response": {"productInfo": product_info}},
            _api_info(url="https://fm.example.com/fmi/data/vLatest/productInfo"),
        )

        envelope = metadata_service.host_info(_profile())

        assert envelope.ok is True
        assert envelope.command == "host info"
        assert envelope.data == product_info
        mock_api.get_product_info.assert_called_once()
        mock_api.__enter__.assert_called_once()

    @patch("fmcli.services.metadata_service.create_api")
    def test_レスポンスにproductInfoがない場合は空辞書(self, mock_create_api: MagicMock) -> None:
        mock_api = MagicMock()
        mock_create_api.return_value = mock_api
        mock_api.get_product_info.return_value = (
            {"response": {}},
            _api_info(),
        )

        envelope = metadata_service.host_info(_profile())

        assert envelope.data == {}


class TestDatabaseList:
    """database_list のテスト."""

    @patch("fmcli.services.metadata_service.create_api")
    def test_ユーザー名パスワード指定で取得できる(
        self,
        mock_create_api: MagicMock,
    ) -> None:
        mock_api = MagicMock()
        mock_create_api.return_value = mock_api
        databases = [{"name": "DB1"}, {"name": "DB2"}]
        mock_api.get_databases.return_value = (
            {"response": {"databases": databases}},
            _api_info(),
        )

        envelope = metadata_service.database_list(_profile(), username="admin", password="secret")

        assert envelope.ok is True
        assert envelope.command == "database list"
        assert envelope.data == databases
        mock_api.get_databases.assert_called_once_with("admin", "secret")

    @patch("fmcli.infra.auth_store.load_credential")
    @patch("fmcli.services.metadata_service.create_api")
    def test_keyringから認証情報を取得できる(
        self,
        mock_create_api: MagicMock,
        mock_load_credential: MagicMock,
    ) -> None:
        mock_load_credential.return_value = ("keyring_user", "keyring_pass")
        mock_api = MagicMock()
        mock_create_api.return_value = mock_api
        databases = [{"name": "MyDB"}]
        mock_api.get_databases.return_value = (
            {"response": {"databases": databases}},
            _api_info(),
        )

        envelope = metadata_service.database_list(_profile())

        assert envelope.data == databases
        mock_api.get_databases.assert_called_once_with("keyring_user", "keyring_pass")
        mock_load_credential.assert_called_once_with("https://fm.example.com")

    @patch("fmcli.infra.auth_store.load_credential")
    def test_認証情報なしでAuthError(self, mock_load_credential: MagicMock) -> None:
        mock_load_credential.return_value = None

        with pytest.raises(AuthError, match="認証情報がありません"):
            metadata_service.database_list(_profile())

    @patch("fmcli.infra.auth_store.load_credential")
    def test_username_only_triggers_keyring_fallback(self, mock_load_credential: MagicMock) -> None:
        """username だけ指定して password が None の場合も keyring フォールバックする."""
        mock_load_credential.return_value = None

        with pytest.raises(AuthError, match="認証情報がありません"):
            metadata_service.database_list(_profile(), username="admin", password=None)


class TestLayoutList:
    """layout_list のテスト."""

    @patch("fmcli.services.metadata_service.call_with_refresh")
    def test_レイアウト一覧を取得できる(self, mock_call: MagicMock) -> None:
        layouts = [{"name": "Contacts"}, {"name": "Orders"}]
        mock_call.return_value = (
            {"response": {"layouts": layouts}},
            _api_info(),
        )

        envelope = metadata_service.layout_list(_profile())

        assert envelope.ok is True
        assert envelope.command == "layout list"
        assert envelope.data == layouts

    @patch("fmcli.services.metadata_service.call_with_refresh")
    def test_空のレイアウト一覧(self, mock_call: MagicMock) -> None:
        mock_call.return_value = (
            {"response": {"layouts": []}},
            _api_info(),
        )

        envelope = metadata_service.layout_list(_profile())

        assert envelope.data == []


class TestLayoutDescribe:
    """layout_describe のテスト."""

    @patch("fmcli.services.metadata_service.call_with_refresh")
    def test_レイアウトメタデータを取得できる(self, mock_call: MagicMock) -> None:
        fields = [{"name": "Name", "type": "normal"}]
        portals = {"Orders": [{"name": "OrderID"}]}
        value_lists = [{"name": "Status", "values": [{"value": "Active"}]}]
        mock_call.return_value = (
            {
                "response": {
                    "fieldMetaData": fields,
                    "portalMetaData": portals,
                    "valueLists": value_lists,
                }
            },
            _api_info(),
        )

        envelope = metadata_service.layout_describe(_profile(), "Contacts")

        assert envelope.ok is True
        assert envelope.command == "layout describe"
        assert envelope.layout == "Contacts"
        assert envelope.data["fieldMetaData"] == fields
        assert envelope.data["portalMetaData"] == portals
        assert envelope.data["valueLists"] == value_lists

    @patch("fmcli.services.metadata_service.call_with_refresh")
    def test_レスポンスにキーがない場合はデフォルト値(self, mock_call: MagicMock) -> None:
        mock_call.return_value = (
            {"response": {}},
            _api_info(),
        )

        envelope = metadata_service.layout_describe(_profile(), "Empty")

        assert envelope.data == {
            "fieldMetaData": [],
            "portalMetaData": {},
            "valueLists": [],
        }


class TestScriptList:
    """script_list のテスト."""

    @patch("fmcli.services.metadata_service.call_with_refresh")
    def test_スクリプト一覧を取得できる(self, mock_call: MagicMock) -> None:
        scripts = [{"name": "SendEmail", "isFolder": False}, {"name": "Utils", "isFolder": True}]
        mock_call.return_value = (
            {"response": {"scripts": scripts}},
            _api_info(),
        )

        envelope = metadata_service.script_list(_profile())

        assert envelope.ok is True
        assert envelope.command == "script list"
        assert envelope.data == scripts

    @patch("fmcli.services.metadata_service.call_with_refresh")
    def test_空のスクリプト一覧(self, mock_call: MagicMock) -> None:
        mock_call.return_value = (
            {"response": {"scripts": []}},
            _api_info(),
        )

        envelope = metadata_service.script_list(_profile())

        assert envelope.data == []


class TestLayoutValueLists:
    """layout_value_lists のテスト."""

    @patch("fmcli.services.metadata_service.call_with_refresh")
    def test_値リストをフォーマットして返す(self, mock_call: MagicMock) -> None:
        value_lists = [
            {
                "name": "Status",
                "type": "customList",
                "values": [{"value": "Active"}, {"value": "Inactive"}],
            }
        ]
        mock_call.return_value = (
            {"response": {"valueLists": value_lists}},
            _api_info(),
        )

        envelope = metadata_service.layout_value_lists(_profile(), "Contacts")

        assert envelope.command == "layout describe --value-lists"
        assert len(envelope.data) == 1
        assert envelope.data[0]["name"] == "Status"
        assert envelope.data[0]["count"] == 2

    @patch("fmcli.services.metadata_service.call_with_refresh")
    def test_値リストが空の場合(self, mock_call: MagicMock) -> None:
        mock_call.return_value = (
            {"response": {}},
            _api_info(),
        )

        envelope = metadata_service.layout_value_lists(_profile(), "Empty")

        assert envelope.data == []


class TestEnvelopeProfileInfo:
    """Envelope にプロファイル情報が正しく設定されるか."""

    @patch("fmcli.services.metadata_service.create_api")
    def test_profile_keyとdatabaseが設定される(self, mock_create_api: MagicMock) -> None:
        mock_api = MagicMock()
        mock_create_api.return_value = mock_api
        mock_api.get_product_info.return_value = (
            {"response": {"productInfo": {}}},
            _api_info(),
        )

        profile = _profile()
        envelope = metadata_service.host_info(profile)

        assert envelope.profile == profile.profile_key
        assert envelope.database == "TestDB"
