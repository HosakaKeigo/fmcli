"""explain / schema CLI コマンドのテスト."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from fmcli.core.errors import EXIT_AUTH, EXIT_CONFIG, AuthError, ConfigError
from fmcli.main import app
from tests.unit.helpers import make_envelope, make_profile

runner = CliRunner()


# ===================================================================
# explain find
# ===================================================================


class TestExplainFind:
    """explain find コマンドのテスト."""

    @patch("fmcli.cli.explain.explain_service")
    @patch("fmcli.cli.explain.get_profile")
    def test_explain_find_success(self, mock_resolve: MagicMock, mock_svc: MagicMock) -> None:
        """正常時に JSON 出力する."""
        mock_resolve.return_value = make_profile()
        mock_svc.explain_find.return_value = make_envelope(
            "explain find",
            data={
                "layout": "TestLayout",
                "query": [{"Name": "田中"}],
                "description": "Name が '田中' に一致するレコードを検索",
            },
        )

        result = runner.invoke(
            app, ["explain", "find", "-l", "TestLayout", "-q", '{"Name":"田中"}']
        )

        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output["ok"] is True
        assert output["command"] == "explain find"

    @patch("fmcli.cli.explain.explain_service")
    @patch("fmcli.cli.explain.get_profile")
    def test_explain_find_host_and_database_passed(
        self, mock_resolve: MagicMock, mock_svc: MagicMock
    ) -> None:
        """--host / -d が resolve_profile に渡される."""
        mock_resolve.return_value = make_profile()
        mock_svc.explain_find.return_value = make_envelope("explain find", data={})

        runner.invoke(
            app,
            [
                "explain",
                "find",
                "-l",
                "TestLayout",
                "-q",
                '{"Name":"田中"}',
                "--host",
                "https://other.example.com",
                "-d",
                "OtherDB",
            ],
        )

        call_args = mock_resolve.call_args
        assert call_args.args[0] == "https://other.example.com"
        assert call_args.args[1] == "OtherDB"

    @patch("fmcli.cli.explain.get_profile")
    def test_explain_find_config_error(self, mock_resolve: MagicMock) -> None:
        """プロファイル解決失敗時に EXIT_CONFIG で終了する."""
        mock_resolve.side_effect = ConfigError("接続先が特定できません。")

        result = runner.invoke(
            app, ["explain", "find", "-l", "TestLayout", "-q", '{"Name":"田中"}']
        )

        assert result.exit_code == EXIT_CONFIG

    @patch("fmcli.cli.explain.explain_service")
    @patch("fmcli.cli.explain.get_profile")
    def test_explain_find_auth_error(self, mock_resolve: MagicMock, mock_svc: MagicMock) -> None:
        """認証エラー時に EXIT_AUTH で終了する."""
        mock_resolve.return_value = make_profile()
        mock_svc.explain_find.side_effect = AuthError(
            "セッションがありません",
            error_type="auth_required",
            host="https://fm.example.com",
            database="TestDB",
        )

        result = runner.invoke(
            app, ["explain", "find", "-l", "TestLayout", "-q", '{"Name":"田中"}']
        )

        assert result.exit_code == EXIT_AUTH

    def test_explain_find_help(self) -> None:
        """--help でヘルプを表示する."""
        result = runner.invoke(app, ["explain", "find", "--help"])
        assert result.exit_code == 0


# ===================================================================
# schema find-schema
# ===================================================================


class TestSchemaFindSchema:
    """schema find-schema コマンドのテスト."""

    @patch("fmcli.cli.explain.explain_service")
    @patch("fmcli.cli.explain.get_profile")
    def test_schema_find_success(self, mock_resolve: MagicMock, mock_svc: MagicMock) -> None:
        """正常時に検索可能フィールド一覧を JSON 出力する."""
        mock_resolve.return_value = make_profile()
        mock_svc.schema_find.return_value = make_envelope(
            "schema find",
            data={
                "layout": "TestLayout",
                "findable_fields": [
                    {"name": "Name", "type": "normal"},
                    {"name": "Age", "type": "normal"},
                ],
            },
        )

        result = runner.invoke(app, ["schema", "find-schema", "-l", "TestLayout"])

        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output["ok"] is True
        assert len(output["data"]["findable_fields"]) == 2

    @patch("fmcli.cli.explain.explain_service")
    @patch("fmcli.cli.explain.get_profile")
    def test_schema_find_host_and_database_passed(
        self, mock_resolve: MagicMock, mock_svc: MagicMock
    ) -> None:
        """--host / -d が resolve_profile に渡される."""
        mock_resolve.return_value = make_profile()
        mock_svc.schema_find.return_value = make_envelope("schema find", data={})

        runner.invoke(
            app,
            [
                "schema",
                "find-schema",
                "-l",
                "TestLayout",
                "--host",
                "https://other.example.com",
                "-d",
                "OtherDB",
            ],
        )

        call_args = mock_resolve.call_args
        assert call_args.args[0] == "https://other.example.com"
        assert call_args.args[1] == "OtherDB"

    @patch("fmcli.cli.explain.get_profile")
    def test_schema_find_config_error(self, mock_resolve: MagicMock) -> None:
        """プロファイル解決失敗時に EXIT_CONFIG で終了する."""
        mock_resolve.side_effect = ConfigError("接続先が特定できません。")

        result = runner.invoke(app, ["schema", "find-schema", "-l", "TestLayout"])

        assert result.exit_code == EXIT_CONFIG

    def test_schema_find_help(self) -> None:
        """--help でヘルプを表示する."""
        result = runner.invoke(app, ["schema", "find-schema", "--help"])
        assert result.exit_code == 0


# ===================================================================
# schema find-schema --filter / --type
# ===================================================================

_SCHEMA_FIELDS = [
    {"name": "Name", "type": "normal"},
    {"name": "CreationDate", "type": "date"},
    {"name": "ModDate", "type": "date"},
    {"name": "Email", "type": "text"},
    {"name": "Age", "type": "number"},
]


def _schema_envelope() -> object:
    """schema find 用のフル Envelope を返す."""
    return make_envelope(
        "schema find",
        data={
            "findable_fields": list(_SCHEMA_FIELDS),
            "portals": [],
            "value_lists": [],
        },
    )


class TestSchemaFindFilter:
    """schema find-schema の --filter / --type クライアント側フィルタテスト."""

    @patch("fmcli.cli.explain.explain_service")
    @patch("fmcli.cli.explain.get_profile")
    def test_filter_by_name(self, mock_resolve: MagicMock, mock_svc: MagicMock) -> None:
        """--filter でフィールド名の部分一致フィルタが効く."""
        mock_resolve.return_value = make_profile()
        mock_svc.schema_find.return_value = _schema_envelope()

        result = runner.invoke(app, ["schema", "find-schema", "-l", "L", "--filter", "Date"])

        assert result.exit_code == 0
        output = json.loads(result.output)
        names = [f["name"] for f in output["data"]["findable_fields"]]
        assert names == ["CreationDate", "ModDate"]

    @patch("fmcli.cli.explain.explain_service")
    @patch("fmcli.cli.explain.get_profile")
    def test_filter_by_type(self, mock_resolve: MagicMock, mock_svc: MagicMock) -> None:
        """--type でフィールド型フィルタが効く."""
        mock_resolve.return_value = make_profile()
        mock_svc.schema_find.return_value = _schema_envelope()

        result = runner.invoke(app, ["schema", "find-schema", "-l", "L", "--type", "date"])

        assert result.exit_code == 0
        output = json.loads(result.output)
        names = [f["name"] for f in output["data"]["findable_fields"]]
        assert names == ["CreationDate", "ModDate"]

    @patch("fmcli.cli.explain.explain_service")
    @patch("fmcli.cli.explain.get_profile")
    def test_filter_and_type_combined(self, mock_resolve: MagicMock, mock_svc: MagicMock) -> None:
        """--filter と --type の組み合わせで AND フィルタが効く."""
        mock_resolve.return_value = make_profile()
        mock_svc.schema_find.return_value = _schema_envelope()

        result = runner.invoke(
            app, ["schema", "find-schema", "-l", "L", "--filter", "Creation", "--type", "date"]
        )

        assert result.exit_code == 0
        output = json.loads(result.output)
        names = [f["name"] for f in output["data"]["findable_fields"]]
        assert names == ["CreationDate"]

    @patch("fmcli.cli.explain.explain_service")
    @patch("fmcli.cli.explain.get_profile")
    def test_filter_no_match(self, mock_resolve: MagicMock, mock_svc: MagicMock) -> None:
        """--filter でヒットなしの場合は空リストが返る."""
        mock_resolve.return_value = make_profile()
        mock_svc.schema_find.return_value = _schema_envelope()

        result = runner.invoke(app, ["schema", "find-schema", "-l", "L", "--filter", "NotExist"])

        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output["data"]["findable_fields"] == []

    @patch("fmcli.cli.explain.explain_service")
    @patch("fmcli.cli.explain.get_profile")
    def test_filter_case_insensitive(self, mock_resolve: MagicMock, mock_svc: MagicMock) -> None:
        """--filter は大小文字を区別しない."""
        mock_resolve.return_value = make_profile()
        mock_svc.schema_find.return_value = _schema_envelope()

        result = runner.invoke(app, ["schema", "find-schema", "-l", "L", "--filter", "email"])

        assert result.exit_code == 0
        output = json.loads(result.output)
        names = [f["name"] for f in output["data"]["findable_fields"]]
        assert "Email" in names


# ===================================================================
# schema output
# ===================================================================


class TestSchemaOutput:
    """schema output コマンドのテスト."""

    @patch("fmcli.cli.explain.explain_service")
    @patch("fmcli.cli.explain.get_profile")
    def test_schema_output_success(self, mock_resolve: MagicMock, mock_svc: MagicMock) -> None:
        """正常時にレイアウト出力構造を JSON 出力する."""
        mock_resolve.return_value = make_profile()
        mock_svc.schema_output.return_value = make_envelope(
            "schema output",
            data={
                "layout": "TestLayout",
                "fields": [
                    {"name": "Name", "type": "normal"},
                    {"name": "Address", "type": "normal"},
                ],
            },
        )

        result = runner.invoke(app, ["schema", "output", "-l", "TestLayout"])

        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output["ok"] is True
        assert output["command"] == "schema output"

    @patch("fmcli.cli.explain.get_profile")
    def test_schema_output_config_error(self, mock_resolve: MagicMock) -> None:
        """プロファイル解決失敗時に EXIT_CONFIG で終了する."""
        mock_resolve.side_effect = ConfigError("接続先が特定できません。")

        result = runner.invoke(app, ["schema", "output", "-l", "TestLayout"])

        assert result.exit_code == EXIT_CONFIG

    def test_schema_output_help(self) -> None:
        """--help でヘルプを表示する."""
        result = runner.invoke(app, ["schema", "output", "--help"])
        assert result.exit_code == 0
