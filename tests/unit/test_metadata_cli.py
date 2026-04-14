"""metadata CLI コマンドのテスト."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from fmcli.core.errors import (
    EXIT_AUTH,
    EXIT_CONFIG,
    EXIT_NOT_FOUND,
    AuthError,
    ConfigError,
    NotFoundError,
)
from fmcli.main import app
from tests.unit.helpers import make_envelope, make_profile, strip_ansi

runner = CliRunner()


# ===================================================================
# host info
# ===================================================================


class TestHostInfo:
    """host info コマンドのテスト."""

    @patch("fmcli.cli.metadata.metadata_service")
    @patch("fmcli.cli.metadata.get_profile")
    def test_host_info_success(self, mock_resolve: MagicMock, mock_svc: MagicMock) -> None:
        """正常時にホスト情報を JSON 出力する."""
        mock_resolve.return_value = make_profile()
        product_info = {"name": "FileMaker Server", "version": "21.0"}
        mock_svc.host_info.return_value = make_envelope("host info", data=product_info)

        result = runner.invoke(app, ["host", "info"])

        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output["ok"] is True
        assert output["data"]["name"] == "FileMaker Server"

    @patch("fmcli.cli.metadata.metadata_service")
    @patch("fmcli.cli.metadata.get_profile")
    def test_host_info_config_error(self, mock_resolve: MagicMock, mock_svc: MagicMock) -> None:
        """プロファイル解決失敗時にエラー出力する."""
        mock_resolve.side_effect = ConfigError("接続先が特定できません。")

        result = runner.invoke(app, ["host", "info"])

        assert result.exit_code == EXIT_CONFIG

    def test_host_info_help(self) -> None:
        """--help でヘルプを表示する."""
        result = runner.invoke(app, ["host", "info", "--help"])
        assert result.exit_code == 0
        output = strip_ansi(result.output)
        assert "ホスト情報" in output


# ===================================================================
# database list
# ===================================================================


class TestDatabaseList:
    """database list コマンドのテスト."""

    @patch("fmcli.cli.metadata.save_profile")
    @patch("fmcli.cli.metadata.save_credential")
    @patch("fmcli.cli.metadata.metadata_service")
    @patch("fmcli.cli.metadata.get_profile")
    @patch("fmcli.cli.metadata.load_credential", return_value=("admin", "pass"))
    def test_database_list_with_keyring_cred(
        self,
        mock_cred: MagicMock,
        mock_resolve: MagicMock,
        mock_svc: MagicMock,
        mock_save_credential: MagicMock,
        mock_save_profile: MagicMock,
    ) -> None:
        """keyring に認証情報がある場合、プロンプトなしでデータベース一覧を取得する."""
        mock_resolve.return_value = make_profile()
        databases = [{"name": "DB1"}, {"name": "DB2"}]
        mock_svc.database_list.return_value = make_envelope("database list", data=databases)

        result = runner.invoke(app, ["database", "list"])

        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output["ok"] is True
        assert len(output["data"]) == 2
        mock_save_profile.assert_called_once()
        mock_save_credential.assert_called_once()

    @patch("fmcli.cli.metadata.save_profile")
    @patch("fmcli.cli.metadata.save_credential")
    @patch("fmcli.cli.metadata.metadata_service")
    @patch("fmcli.cli.metadata.get_profile")
    def test_database_list_with_username_option(
        self,
        mock_resolve: MagicMock,
        mock_svc: MagicMock,
        mock_save_credential: MagicMock,
        mock_save_profile: MagicMock,
    ) -> None:
        """--username 指定時はパスワードのみ対話入力する."""
        mock_resolve.return_value = make_profile()
        databases = [{"name": "TestDB"}]
        mock_svc.database_list.return_value = make_envelope("database list", data=databases)

        result = runner.invoke(app, ["database", "list", "-u", "admin"], input="secret\n")

        assert result.exit_code == 0
        # 出力に ok フラグが含まれることを検証（対話プロンプトが混在する可能性あり）
        assert '"ok"' in result.output
        assert '"database list"' in result.output

    @patch("fmcli.cli.metadata.metadata_service")
    @patch("fmcli.cli.metadata.get_profile")
    def test_database_list_auth_error(self, mock_resolve: MagicMock, mock_svc: MagicMock) -> None:
        """認証エラー時に適切なエラーコードで終了する."""
        mock_resolve.return_value = make_profile()
        mock_svc.database_list.side_effect = AuthError(
            "認証失敗",
            error_type="auth_invalid",
            host="https://fm.example.com",
        )

        result = runner.invoke(app, ["database", "list", "-u", "admin"], input="badpass\n")
        assert result.exit_code == EXIT_AUTH

    def test_database_list_help(self) -> None:
        """--help でヘルプを表示する."""
        result = runner.invoke(app, ["database", "list", "--help"])
        assert result.exit_code == 0
        output = strip_ansi(result.output)
        assert "データベース" in output


# ===================================================================
# layout list
# ===================================================================


class TestLayoutList:
    """layout list コマンドのテスト."""

    @patch("fmcli.cli.metadata._save_layout_cache")
    @patch("fmcli.cli.metadata.metadata_service")
    @patch("fmcli.cli.metadata.get_profile")
    def test_layout_list_success(
        self, mock_resolve: MagicMock, mock_svc: MagicMock, mock_cache: MagicMock
    ) -> None:
        """正常時にレイアウト一覧を出力する."""
        mock_resolve.return_value = make_profile()
        layouts = [{"name": "Layout1"}, {"name": "Layout2"}]
        mock_svc.layout_list.return_value = make_envelope("layout list", data=layouts)

        result = runner.invoke(app, ["layout", "list"])

        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output["ok"] is True
        assert len(output["data"]) == 2

    @patch("fmcli.cli.metadata._save_layout_cache")
    @patch("fmcli.cli.metadata.metadata_service")
    @patch("fmcli.cli.metadata.get_profile")
    def test_layout_list_saves_cache(
        self, mock_resolve: MagicMock, mock_svc: MagicMock, mock_cache: MagicMock
    ) -> None:
        """レイアウト名のキャッシュを保存する."""
        prof = make_profile()
        mock_resolve.return_value = prof
        layouts = [{"name": "LayoutA"}, {"name": "LayoutB"}]
        mock_svc.layout_list.return_value = make_envelope("layout list", data=layouts)

        runner.invoke(app, ["layout", "list"])

        mock_cache.assert_called_once_with(prof.profile_key, ["LayoutA", "LayoutB"])

    @patch("fmcli.cli.metadata.metadata_service")
    @patch("fmcli.cli.metadata.get_profile")
    def test_layout_list_auth_error(self, mock_resolve: MagicMock, mock_svc: MagicMock) -> None:
        """認証エラー時にエラーコードで終了する."""
        mock_resolve.return_value = make_profile()
        mock_svc.layout_list.side_effect = AuthError(
            "セッションがありません",
            error_type="auth_required",
            host="https://fm.example.com",
            database="TestDB",
        )

        result = runner.invoke(app, ["layout", "list"])

        assert result.exit_code == EXIT_AUTH

    @patch("fmcli.cli.metadata._save_layout_cache")
    @patch("fmcli.cli.metadata.metadata_service")
    @patch("fmcli.cli.metadata.get_profile")
    def test_layout_list_filter_single_keyword(
        self, mock_resolve: MagicMock, mock_svc: MagicMock, mock_cache: MagicMock
    ) -> None:
        """--filter で単一キーワードの部分一致フィルタが機能する."""
        mock_resolve.return_value = make_profile()
        layouts = [{"name": "Customers"}, {"name": "Events"}, {"name": "Contacts"}]
        mock_svc.layout_list.return_value = make_envelope("layout list", data=layouts)

        result = runner.invoke(app, ["layout", "list", "--filter", "Cust"])

        assert result.exit_code == 0
        output = json.loads(result.output)
        assert len(output["data"]) == 1
        names = [item["name"] for item in output["data"]]
        assert "Customers" in names

    @patch("fmcli.cli.metadata._save_layout_cache")
    @patch("fmcli.cli.metadata.metadata_service")
    @patch("fmcli.cli.metadata.get_profile")
    def test_layout_list_filter_or_search(
        self, mock_resolve: MagicMock, mock_svc: MagicMock, mock_cache: MagicMock
    ) -> None:
        """--filter でカンマ区切り OR 検索が機能する."""
        mock_resolve.return_value = make_profile()
        layouts = [{"name": "Customers"}, {"name": "Events"}, {"name": "Orders"}]
        mock_svc.layout_list.return_value = make_envelope("layout list", data=layouts)

        result = runner.invoke(app, ["layout", "list", "--filter", "Cust,Order"])

        assert result.exit_code == 0
        output = json.loads(result.output)
        assert len(output["data"]) == 2
        names = [item["name"] for item in output["data"]]
        assert "Customers" in names
        assert "Orders" in names

    @patch("fmcli.cli.metadata._save_layout_cache")
    @patch("fmcli.cli.metadata.metadata_service")
    @patch("fmcli.cli.metadata.get_profile")
    def test_layout_list_filter_case_insensitive(
        self, mock_resolve: MagicMock, mock_svc: MagicMock, mock_cache: MagicMock
    ) -> None:
        """--filter は大文字小文字を区別しない."""
        mock_resolve.return_value = make_profile()
        layouts = [{"name": "MemberList"}, {"name": "CompResult"}]
        mock_svc.layout_list.return_value = make_envelope("layout list", data=layouts)

        result = runner.invoke(app, ["layout", "list", "--filter", "member"])

        assert result.exit_code == 0
        output = json.loads(result.output)
        assert len(output["data"]) == 1
        assert output["data"][0]["name"] == "MemberList"

    @patch("fmcli.cli.metadata._save_layout_cache")
    @patch("fmcli.cli.metadata.metadata_service")
    @patch("fmcli.cli.metadata.get_profile")
    def test_layout_list_filter_no_match(
        self, mock_resolve: MagicMock, mock_svc: MagicMock, mock_cache: MagicMock
    ) -> None:
        """--filter で該当なしの場合は空配列を返す."""
        mock_resolve.return_value = make_profile()
        layouts = [{"name": "Layout1"}, {"name": "Layout2"}]
        mock_svc.layout_list.return_value = make_envelope("layout list", data=layouts)

        result = runner.invoke(app, ["layout", "list", "--filter", "存在しない"])

        assert result.exit_code == 0
        output = json.loads(result.output)
        assert len(output["data"]) == 0

    @patch("fmcli.cli.metadata._save_layout_cache")
    @patch("fmcli.cli.metadata.metadata_service")
    @patch("fmcli.cli.metadata.get_profile")
    def test_layout_list_filter_comma_in_name(
        self, mock_resolve: MagicMock, mock_svc: MagicMock, mock_cache: MagicMock
    ) -> None:
        """既知の制限: レイアウト名にカンマが含まれる場合、OR 区切りとして解釈される."""
        mock_resolve.return_value = make_profile()
        layouts = [{"name": "A,B"}, {"name": "C"}]
        mock_svc.layout_list.return_value = make_envelope("layout list", data=layouts)

        # "A,B" を検索すると "A" OR "B" として扱われ、"A,B" がヒットする（"A" 部分一致）
        result = runner.invoke(app, ["layout", "list", "--filter", "A,B"])

        assert result.exit_code == 0
        output = json.loads(result.output)
        # "A,B" は "A" にマッチするのでヒットする
        names = [item["name"] for item in output["data"]]
        assert "A,B" in names
        # 注意: カンマ入りのレイアウト名を完全一致で検索する手段はない

    def test_layout_list_help(self) -> None:
        """--help でヘルプを表示する."""
        result = runner.invoke(app, ["layout", "list", "--help"])
        assert result.exit_code == 0


# ===================================================================
# layout describe
# ===================================================================


class TestLayoutDescribe:
    """layout describe コマンドのテスト."""

    @patch("fmcli.cli.metadata.metadata_service")
    @patch("fmcli.cli.metadata.get_profile")
    def test_layout_describe_success(self, mock_resolve: MagicMock, mock_svc: MagicMock) -> None:
        """正常時にレイアウトメタデータを出力する."""
        mock_resolve.return_value = make_profile()
        meta = {
            "fieldMetaData": [{"name": "Name", "type": "normal"}],
            "portalMetaData": {},
            "valueLists": [],
        }
        mock_svc.layout_describe.return_value = make_envelope("layout describe", data=meta)

        result = runner.invoke(app, ["layout", "describe", "-l", "TestLayout"])

        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output["ok"] is True
        assert output["data"]["fieldMetaData"][0]["name"] == "Name"

    @patch("fmcli.cli.metadata.metadata_service")
    @patch("fmcli.cli.metadata.get_profile")
    def test_layout_describe_with_value_lists(
        self, mock_resolve: MagicMock, mock_svc: MagicMock
    ) -> None:
        """--value-lists 指定時に値リスト情報を出力する."""
        mock_resolve.return_value = make_profile()
        vl_data = [
            {
                "name": "Colors",
                "type": "customValues",
                "count": 3,
                "values": ["Red", "Blue", "Green"],
            }
        ]
        mock_svc.layout_value_lists.return_value = make_envelope(
            "layout describe --value-lists", data=vl_data
        )

        result = runner.invoke(app, ["layout", "describe", "-l", "TestLayout", "--value-lists"])

        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output["ok"] is True
        assert output["data"][0]["name"] == "Colors"
        # layout_describe ではなく layout_value_lists が呼ばれたことを確認
        mock_svc.layout_value_lists.assert_called_once()
        mock_svc.layout_describe.assert_not_called()

    @patch("fmcli.cli.metadata.metadata_service")
    @patch("fmcli.cli.metadata.get_profile")
    def test_layout_describe_without_value_lists(
        self, mock_resolve: MagicMock, mock_svc: MagicMock
    ) -> None:
        """--value-lists なしの場合は layout_describe が呼ばれる."""
        mock_resolve.return_value = make_profile()
        mock_svc.layout_describe.return_value = make_envelope("layout describe", data={})

        runner.invoke(app, ["layout", "describe", "-l", "TestLayout"])

        mock_svc.layout_describe.assert_called_once()
        mock_svc.layout_value_lists.assert_not_called()

    @patch("fmcli.cli.metadata.metadata_service")
    @patch("fmcli.cli.metadata.get_profile")
    def test_layout_describe_not_found(self, mock_resolve: MagicMock, mock_svc: MagicMock) -> None:
        """存在しないレイアウトに対して NotFoundError がエラー処理される."""
        mock_resolve.return_value = make_profile()
        mock_svc.layout_describe.side_effect = NotFoundError("レイアウトが見つかりません")

        result = runner.invoke(app, ["layout", "describe", "-l", "NonExistent"])

        assert result.exit_code == EXIT_NOT_FOUND

    def test_layout_describe_requires_layout(self) -> None:
        """--layout オプションが未指定だとエラーになる."""
        result = runner.invoke(app, ["layout", "describe"])
        # typer の必須オプション不足は exit_code 2
        assert result.exit_code != 0  # typer validation error

    def test_layout_describe_vl_short_option(self) -> None:
        """--vl ショートオプションが受け付けられる."""
        result = runner.invoke(app, ["layout", "describe", "-l", "Test", "--vl", "--help"])
        # --help が優先されるので exit_code == 0
        assert result.exit_code == 0


# ===================================================================
# script list
# ===================================================================


class TestScriptList:
    """script list コマンドのテスト."""

    @patch("fmcli.cli.metadata.metadata_service")
    @patch("fmcli.cli.metadata.get_profile")
    def test_script_list_success(self, mock_resolve: MagicMock, mock_svc: MagicMock) -> None:
        """正常時にスクリプト一覧を出力する."""
        mock_resolve.return_value = make_profile()
        scripts = [{"name": "Script1", "isFolder": False}, {"name": "Script2", "isFolder": False}]
        mock_svc.script_list.return_value = make_envelope("script list", data=scripts)

        result = runner.invoke(app, ["script", "list"])

        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output["ok"] is True
        assert len(output["data"]) == 2

    @patch("fmcli.cli.metadata.metadata_service")
    @patch("fmcli.cli.metadata.get_profile")
    def test_script_list_auth_error(self, mock_resolve: MagicMock, mock_svc: MagicMock) -> None:
        """認証エラー時にエラーコードで終了する."""
        mock_resolve.return_value = make_profile()
        mock_svc.script_list.side_effect = AuthError(
            "セッションが無効です",
            error_type="auth_expired",
        )

        result = runner.invoke(app, ["script", "list"])

        assert result.exit_code == EXIT_AUTH

    @patch("fmcli.cli.metadata.get_profile")
    def test_script_list_config_error(self, mock_resolve: MagicMock) -> None:
        """プロファイル解決失敗時にエラーコードで終了する."""
        mock_resolve.side_effect = ConfigError("接続先が特定できません。")

        result = runner.invoke(app, ["script", "list"])

        assert result.exit_code == EXIT_CONFIG

    def test_script_list_help(self) -> None:
        """--help でヘルプを表示する."""
        result = runner.invoke(app, ["script", "list", "--help"])
        assert result.exit_code == 0
        output = strip_ansi(result.output)
        assert "スクリプト" in output


# ===================================================================
# 共通オプション
# ===================================================================


class TestMetadataCommonOptions:
    """metadata コマンド共通オプションのテスト."""

    @patch("fmcli.cli.metadata.metadata_service")
    @patch("fmcli.cli.metadata.get_profile")
    def test_host_option_passed_to_resolve(
        self, mock_resolve: MagicMock, mock_svc: MagicMock
    ) -> None:
        """--host オプションが resolve_profile に渡される."""
        mock_resolve.return_value = make_profile()
        mock_svc.host_info.return_value = make_envelope("host info", data={})

        runner.invoke(app, ["host", "info", "--host", "https://other.example.com"])

        call_args = mock_resolve.call_args
        assert call_args.args[0] == "https://other.example.com"

    @patch("fmcli.cli.metadata.metadata_service")
    @patch("fmcli.cli.metadata.get_profile")
    def test_database_option_passed_to_resolve(
        self, mock_resolve: MagicMock, mock_svc: MagicMock
    ) -> None:
        """--database オプションが resolve_profile に渡される."""
        mock_resolve.return_value = make_profile()
        mock_svc.layout_list.return_value = make_envelope("layout list", data=[])

        runner.invoke(app, ["layout", "list", "-d", "OtherDB"])

        call_args = mock_resolve.call_args
        assert call_args.args[1] == "OtherDB"
