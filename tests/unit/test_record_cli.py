"""record CLI コマンドのテスト."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from fmcli.core.errors import EXIT_AUTH, EXIT_CONFIG, AuthError, ConfigError
from fmcli.main import app
from tests.unit.helpers import make_envelope, make_profile, strip_ansi

runner = CliRunner()


# ===================================================================
# --allow-scripts バリデーション
# ===================================================================


class TestAllowScriptsValidation:
    """--allow-scripts フラグのバリデーションテスト."""

    # -----------------------------------------------------------------
    # record get
    # -----------------------------------------------------------------

    def test_get_script_without_allow_scripts_rejected(self) -> None:
        """record get: --script を --allow-scripts なしで指定するとエラー."""
        result = runner.invoke(app, ["record", "get", "1", "-l", "Layout", "--script", "MyScript"])
        assert result.exit_code != 0
        output = strip_ansi(result.output)
        assert "read-only" in output or "--allow-scripts" in output

    def test_get_script_presort_without_allow_scripts_rejected(self) -> None:
        """record get: --script-presort を --allow-scripts なしで指定するとエラー."""
        result = runner.invoke(
            app,
            ["record", "get", "1", "-l", "Layout", "--script-presort", "PreSort"],
        )
        assert result.exit_code != 0
        output = strip_ansi(result.output)
        assert "--allow-scripts" in output

    def test_get_script_prerequest_without_allow_scripts_rejected(self) -> None:
        """record get: --script-prerequest を --allow-scripts なしで指定するとエラー."""
        result = runner.invoke(
            app,
            [
                "record",
                "get",
                "1",
                "-l",
                "Layout",
                "--script-prerequest",
                "PreReq",
            ],
        )
        assert result.exit_code != 0
        output = strip_ansi(result.output)
        assert "--allow-scripts" in output

    def test_get_no_script_no_error(self) -> None:
        """record get: スクリプトなしの場合、--allow-scripts 不要でバリデーションエラーなし.

        (プロファイル解決で別のエラーになるが、スクリプトバリデーションは通過)
        """
        result = runner.invoke(app, ["record", "get", "1", "-l", "Layout"])
        output = strip_ansi(result.output)
        # スクリプト関連エラーは出ない (プロファイルエラーは出る可能性あり)
        assert "--allow-scripts" not in output

    # -----------------------------------------------------------------
    # record list
    # -----------------------------------------------------------------

    def test_list_script_without_allow_scripts_rejected(self) -> None:
        """record list: --script を --allow-scripts なしで指定するとエラー."""
        result = runner.invoke(
            app,
            ["record", "list", "-l", "Layout", "--script", "MyScript"],
        )
        assert result.exit_code != 0
        output = strip_ansi(result.output)
        assert "--allow-scripts" in output

    def test_list_multiple_scripts_without_allow_scripts_rejected(self) -> None:
        """record list: 複数スクリプトオプション指定時、全て列挙される."""
        result = runner.invoke(
            app,
            [
                "record",
                "list",
                "-l",
                "Layout",
                "--script",
                "A",
                "--script-presort",
                "B",
            ],
        )
        assert result.exit_code != 0
        output = strip_ansi(result.output)
        assert "--script" in output
        assert "--script-presort" in output

    def test_list_no_script_no_error(self) -> None:
        """record list: スクリプトなしの場合はバリデーションエラーなし."""
        result = runner.invoke(app, ["record", "list", "-l", "Layout"])
        output = strip_ansi(result.output)
        assert "--allow-scripts" not in output

    # -----------------------------------------------------------------
    # record find
    # -----------------------------------------------------------------

    def test_find_script_without_allow_scripts_rejected(self) -> None:
        """record find: --script を --allow-scripts なしで指定するとエラー."""
        result = runner.invoke(
            app,
            [
                "record",
                "find",
                "-l",
                "Layout",
                "-q",
                '{"Name":"test"}',
                "--script",
                "MyScript",
            ],
        )
        assert result.exit_code != 0
        output = strip_ansi(result.output)
        assert "--allow-scripts" in output

    def test_find_all_scripts_without_allow_scripts_shows_all(self) -> None:
        """record find: 3 種類全てのスクリプトオプションがエラーメッセージに列挙される."""
        result = runner.invoke(
            app,
            [
                "record",
                "find",
                "-l",
                "Layout",
                "-q",
                '{"Name":"test"}',
                "--script",
                "A",
                "--script-presort",
                "B",
                "--script-prerequest",
                "C",
            ],
        )
        assert result.exit_code != 0
        output = strip_ansi(result.output)
        assert "--script" in output
        assert "--script-presort" in output
        assert "--script-prerequest" in output

    def test_find_no_script_no_error(self) -> None:
        """record find: スクリプトなしの場合はバリデーションエラーなし."""
        result = runner.invoke(app, ["record", "find", "-l", "Layout", "-q", '{"Name":"test"}'])
        output = strip_ansi(result.output)
        assert "--allow-scripts" not in output


class TestAllowScriptsOptIn:
    """--allow-scripts フラグ付きでスクリプトが受理されるテスト.

    プロファイル解決でエラーになるが、スクリプトバリデーションは通過する。
    """

    def test_get_with_allow_scripts_passes_validation(self) -> None:
        """record get: --allow-scripts 付きならスクリプトバリデーション通過."""
        result = runner.invoke(
            app,
            [
                "record",
                "get",
                "1",
                "-l",
                "Layout",
                "--script",
                "MyScript",
                "--allow-scripts",
            ],
        )
        output = strip_ansi(result.output)
        # スクリプトバリデーションエラーは出ない
        assert "read-only" not in output
        assert "--allow-scripts フラグを追加" not in output

    def test_list_with_allow_scripts_passes_validation(self) -> None:
        """record list: --allow-scripts 付きならスクリプトバリデーション通過."""
        result = runner.invoke(
            app,
            [
                "record",
                "list",
                "-l",
                "Layout",
                "--script",
                "MyScript",
                "--allow-scripts",
            ],
        )
        output = strip_ansi(result.output)
        assert "read-only" not in output
        assert "--allow-scripts フラグを追加" not in output

    def test_find_with_allow_scripts_passes_validation(self) -> None:
        """record find: --allow-scripts 付きならスクリプトバリデーション通過."""
        result = runner.invoke(
            app,
            [
                "record",
                "find",
                "-l",
                "Layout",
                "-q",
                '{"Name":"test"}',
                "--script",
                "MyScript",
                "--allow-scripts",
            ],
        )
        output = strip_ansi(result.output)
        assert "read-only" not in output
        assert "--allow-scripts フラグを追加" not in output

    def test_find_with_all_scripts_and_allow_scripts(self) -> None:
        """record find: 全スクリプトオプション + --allow-scripts でバリデーション通過."""
        result = runner.invoke(
            app,
            [
                "record",
                "find",
                "-l",
                "Layout",
                "-q",
                '{"Name":"test"}',
                "--script",
                "A",
                "--script-presort",
                "B",
                "--script-prerequest",
                "C",
                "--allow-scripts",
            ],
        )
        output = strip_ansi(result.output)
        assert "read-only" not in output
        assert "--allow-scripts フラグを追加" not in output


# ===================================================================
# record get — 正常系・オプション・エラーハンドリング
# ===================================================================


class TestRecordGet:
    """record get コマンドのテスト."""

    @patch("fmcli.cli.record.record_service")
    @patch("fmcli.cli.record.get_profile")
    def test_get_success(self, mock_resolve: MagicMock, mock_svc: MagicMock) -> None:
        """正常時にレコードを JSON 出力する."""
        mock_resolve.return_value = make_profile()
        record_data = {"fieldData": {"Name": "田中", "Email": "tanaka@example.com"}}
        mock_svc.get_record.return_value = make_envelope("record get", data=record_data)

        result = runner.invoke(app, ["record", "get", "1", "-l", "TestLayout"])

        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output["ok"] is True
        assert output["data"]["fieldData"]["Name"] == "田中"

    @patch("fmcli.cli.record.record_service")
    @patch("fmcli.cli.record.get_profile")
    def test_get_fields_passed_to_service(
        self, mock_resolve: MagicMock, mock_svc: MagicMock
    ) -> None:
        """--fields オプションが record_service.get_record に渡される."""
        mock_resolve.return_value = make_profile()
        mock_svc.get_record.return_value = make_envelope("record get", data={})

        runner.invoke(app, ["record", "get", "1", "-l", "TestLayout", "--fields", "Name,Email"])

        mock_svc.get_record.assert_called_once()
        call_kwargs = mock_svc.get_record.call_args
        assert call_kwargs.kwargs.get("fields") == "Name,Email"

    @patch("fmcli.cli.record.record_service")
    @patch("fmcli.cli.record.get_profile")
    def test_get_portal_passed_to_service(
        self, mock_resolve: MagicMock, mock_svc: MagicMock
    ) -> None:
        """--portal オプションが record_service.get_record に渡される."""
        mock_resolve.return_value = make_profile()
        mock_svc.get_record.return_value = make_envelope("record get", data={})

        runner.invoke(app, ["record", "get", "1", "-l", "TestLayout", "--portal", "Portal1:10"])

        mock_svc.get_record.assert_called_once()
        call_kwargs = mock_svc.get_record.call_args
        assert call_kwargs.kwargs.get("portal") == "Portal1:10"

    @patch("fmcli.cli.record.record_service")
    @patch("fmcli.cli.record.get_profile")
    def test_get_host_and_database_passed_to_resolve(
        self, mock_resolve: MagicMock, mock_svc: MagicMock
    ) -> None:
        """--host と -d オプションが resolve_profile に渡される."""
        mock_resolve.return_value = make_profile()
        mock_svc.get_record.return_value = make_envelope("record get", data={})

        runner.invoke(
            app,
            [
                "record",
                "get",
                "1",
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

    @patch("fmcli.cli.record.get_profile")
    def test_get_config_error(self, mock_resolve: MagicMock) -> None:
        """プロファイル解決失敗時に EXIT_CONFIG で終了する."""
        mock_resolve.side_effect = ConfigError("接続先が特定できません。")

        result = runner.invoke(app, ["record", "get", "1", "-l", "TestLayout"])

        assert result.exit_code == EXIT_CONFIG

    @patch("fmcli.cli.record.record_service")
    @patch("fmcli.cli.record.get_profile")
    def test_get_auth_error(self, mock_resolve: MagicMock, mock_svc: MagicMock) -> None:
        """認証エラー時に EXIT_AUTH で終了する."""
        mock_resolve.return_value = make_profile()
        mock_svc.get_record.side_effect = AuthError(
            "セッションが無効です",
            error_type="auth_expired",
        )

        result = runner.invoke(app, ["record", "get", "1", "-l", "TestLayout"])

        assert result.exit_code == EXIT_AUTH

    def test_get_help(self) -> None:
        """--help でヘルプを表示する."""
        result = runner.invoke(app, ["record", "get", "--help"])
        assert result.exit_code == 0
        output = strip_ansi(result.output)
        assert "レコード" in output or "record" in output.lower()


# ===================================================================
# record list — 正常系・オプション・エラーハンドリング
# ===================================================================


class TestRecordList:
    """record list コマンドのテスト."""

    @patch("fmcli.cli.record.record_service")
    @patch("fmcli.cli.record.get_profile")
    def test_list_success(self, mock_resolve: MagicMock, mock_svc: MagicMock) -> None:
        """正常時にレコード一覧を JSON 出力する."""
        mock_resolve.return_value = make_profile()
        records = [
            {"fieldData": {"Name": "Alice"}, "recordId": "1"},
            {"fieldData": {"Name": "Bob"}, "recordId": "2"},
        ]
        mock_svc.list_records.return_value = make_envelope("record list", data=records)

        result = runner.invoke(app, ["record", "list", "-l", "Contacts"])

        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output["ok"] is True
        assert len(output["data"]) == 2

    @patch("fmcli.cli.record.record_service")
    @patch("fmcli.cli.record.get_profile")
    def test_list_limit_and_offset_passed(
        self, mock_resolve: MagicMock, mock_svc: MagicMock
    ) -> None:
        """--limit と --offset がサービスに渡される."""
        mock_resolve.return_value = make_profile()
        mock_svc.list_records.return_value = make_envelope("record list", data=[])

        runner.invoke(app, ["record", "list", "-l", "Contacts", "--limit", "50", "--offset", "10"])

        call_kwargs = mock_svc.list_records.call_args
        assert call_kwargs.kwargs.get("limit") == 50
        assert call_kwargs.kwargs.get("offset") == 10

    @patch("fmcli.cli.record.record_service")
    @patch("fmcli.cli.record.get_profile")
    def test_list_sort_passed(self, mock_resolve: MagicMock, mock_svc: MagicMock) -> None:
        """--sort がサービスに渡される."""
        mock_resolve.return_value = make_profile()
        mock_svc.list_records.return_value = make_envelope("record list", data=[])

        runner.invoke(app, ["record", "list", "-l", "Contacts", "--sort", "Name:ascend"])

        call_kwargs = mock_svc.list_records.call_args
        assert call_kwargs.kwargs.get("sort") == "Name:ascend"

    @patch("fmcli.cli.record.record_service")
    @patch("fmcli.cli.record.get_profile")
    def test_list_fields_passed(self, mock_resolve: MagicMock, mock_svc: MagicMock) -> None:
        """--fields がサービスに渡される."""
        mock_resolve.return_value = make_profile()
        mock_svc.list_records.return_value = make_envelope("record list", data=[])

        runner.invoke(app, ["record", "list", "-l", "Contacts", "--fields", "Name,Email"])

        call_kwargs = mock_svc.list_records.call_args
        assert call_kwargs.kwargs.get("fields") == "Name,Email"

    @patch("fmcli.cli.record.record_service")
    @patch("fmcli.cli.record.get_profile")
    def test_list_portal_passed(self, mock_resolve: MagicMock, mock_svc: MagicMock) -> None:
        """--portal がサービスに渡される."""
        mock_resolve.return_value = make_profile()
        mock_svc.list_records.return_value = make_envelope("record list", data=[])

        runner.invoke(app, ["record", "list", "-l", "Contacts", "--portal", "Portal1:10"])

        call_kwargs = mock_svc.list_records.call_args
        assert call_kwargs.kwargs.get("portal") == "Portal1:10"

    @patch("fmcli.cli.record.explain_service")
    @patch("fmcli.cli.record.get_profile")
    def test_list_dry_run_calls_explain_service(
        self, mock_resolve: MagicMock, mock_explain: MagicMock
    ) -> None:
        """--dry-run で dry_run_record_list が呼ばれオプションが伝搬される."""
        mock_resolve.return_value = make_profile()
        mock_explain.dry_run_record_list.return_value = make_envelope(
            "record list --dry-run", data={"method": "GET", "url": "..."}
        )

        result = runner.invoke(
            app,
            [
                "record",
                "list",
                "-l",
                "Contacts",
                "--limit",
                "25",
                "--offset",
                "5",
                "--sort",
                "Name:ascend",
                "--portal",
                "Portal1:10",
                "--dry-run",
            ],
        )

        assert result.exit_code == 0
        mock_explain.dry_run_record_list.assert_called_once()
        call_kwargs = mock_explain.dry_run_record_list.call_args.kwargs
        assert call_kwargs.get("limit") == 25
        assert call_kwargs.get("offset") == 5
        assert call_kwargs.get("sort") == "Name:ascend"
        assert call_kwargs.get("portal") == "Portal1:10"

    @patch("fmcli.cli.record.get_profile")
    def test_list_config_error(self, mock_resolve: MagicMock) -> None:
        """ConfigError 時に EXIT_CONFIG で終了する."""
        mock_resolve.side_effect = ConfigError("接続先が特定できません。")

        result = runner.invoke(app, ["record", "list", "-l", "Contacts"])

        assert result.exit_code == EXIT_CONFIG

    @patch("fmcli.cli.record.record_service")
    @patch("fmcli.cli.record.get_profile")
    def test_list_auth_error(self, mock_resolve: MagicMock, mock_svc: MagicMock) -> None:
        """AuthError 時に EXIT_AUTH で終了する."""
        mock_resolve.return_value = make_profile()
        mock_svc.list_records.side_effect = AuthError(
            "セッションが無効です",
            error_type="auth_expired",
        )

        result = runner.invoke(app, ["record", "list", "-l", "Contacts"])

        assert result.exit_code == EXIT_AUTH

    def test_list_help(self) -> None:
        """--help でヘルプを表示する."""
        result = runner.invoke(app, ["record", "list", "--help"])
        assert result.exit_code == 0
        output = strip_ansi(result.output)
        assert "レコード一覧" in output


# ===================================================================
# record find — 正常系・オプション・エラーハンドリング
# ===================================================================


class TestRecordFind:
    """record find コマンドのテスト."""

    @patch("fmcli.cli.record.record_service")
    @patch("fmcli.cli.record.get_profile")
    def test_find_success_with_query(self, mock_resolve: MagicMock, mock_svc: MagicMock) -> None:
        """正常時に検索結果を JSON 出力する."""
        mock_resolve.return_value = make_profile()
        records = [{"fieldData": {"Name": "田中"}, "recordId": "1"}]
        mock_svc.find_records.return_value = make_envelope("record find", data=records)

        result = runner.invoke(app, ["record", "find", "-l", "Contacts", "-q", '{"Name":"田中"}'])

        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output["ok"] is True
        assert output["data"][0]["fieldData"]["Name"] == "田中"

    @patch("fmcli.cli.record.record_service")
    @patch("fmcli.cli.record.get_profile")
    def test_find_with_query_file(self, mock_resolve: MagicMock, mock_svc: MagicMock) -> None:
        """--query-file が service に渡される."""
        mock_resolve.return_value = make_profile()
        mock_svc.find_records.return_value = make_envelope("record find", data=[])

        runner.invoke(app, ["record", "find", "-l", "Contacts", "-f", "/tmp/query.json"])

        mock_svc.find_records.assert_called_once()
        call_kwargs = mock_svc.find_records.call_args
        assert call_kwargs.kwargs.get("query_file") == "/tmp/query.json"

    @patch("fmcli.cli.record.record_service")
    @patch("fmcli.cli.record.get_profile")
    def test_find_first_sets_limit_one(self, mock_resolve: MagicMock, mock_svc: MagicMock) -> None:
        """--first を指定すると limit=1 が service に渡される."""
        mock_resolve.return_value = make_profile()
        mock_svc.find_records.return_value = make_envelope("record find", data=[])

        runner.invoke(
            app,
            ["record", "find", "-l", "Contacts", "-q", '{"Name":"田中"}', "--first"],
        )

        mock_svc.find_records.assert_called_once()
        call_kwargs = mock_svc.find_records.call_args
        assert call_kwargs.kwargs.get("limit") == 1

    @patch("fmcli.cli.record.record_service")
    @patch("fmcli.cli.record.get_profile")
    def test_find_count_only(self, mock_resolve: MagicMock, mock_svc: MagicMock) -> None:
        """--count を指定すると count_only=True が service に渡される."""
        mock_resolve.return_value = make_profile()
        mock_svc.find_records.return_value = make_envelope("record find", data=[])

        runner.invoke(
            app,
            ["record", "find", "-l", "Contacts", "-q", '{"Name":"田中"}', "--count"],
        )

        mock_svc.find_records.assert_called_once()
        call_kwargs = mock_svc.find_records.call_args
        assert call_kwargs.kwargs.get("count_only") is True

    @patch("fmcli.cli.record.explain_service")
    @patch("fmcli.cli.record.record_service")
    @patch("fmcli.cli.record.get_profile")
    def test_find_with_schema(
        self, mock_resolve: MagicMock, mock_svc: MagicMock, mock_explain: MagicMock
    ) -> None:
        """--with-schema でスキーマ情報がレスポンスに付加される."""
        mock_resolve.return_value = make_profile()
        records = [{"fieldData": {"Name": "田中"}, "recordId": "1"}]
        mock_svc.find_records.return_value = make_envelope("record find", data=records)
        schema_data = {
            "findable_fields": [{"name": "Name", "type": "normal", "global": False}],
            "portals": [],
            "value_lists": [],
        }
        mock_explain.schema_find.return_value = make_envelope(
            "schema find-schema", data=schema_data
        )

        result = runner.invoke(
            app,
            [
                "record",
                "find",
                "-l",
                "Contacts",
                "-q",
                '{"Name":"田中"}',
                "--with-schema",
            ],
        )

        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output["ok"] is True
        assert "records" in output["data"]
        assert "schema" in output["data"]
        assert output["data"]["schema"]["findable_fields"][0]["name"] == "Name"
        mock_explain.schema_find.assert_called_once()

    @patch("fmcli.cli.record.record_service")
    @patch("fmcli.cli.record.get_profile")
    def test_find_fields_passed(self, mock_resolve: MagicMock, mock_svc: MagicMock) -> None:
        """--fields が service に渡される."""
        mock_resolve.return_value = make_profile()
        mock_svc.find_records.return_value = make_envelope("record find", data=[])

        runner.invoke(
            app,
            [
                "record",
                "find",
                "-l",
                "Contacts",
                "-q",
                '{"Name":"田中"}',
                "--fields",
                "Name,Email",
            ],
        )

        mock_svc.find_records.assert_called_once()
        call_kwargs = mock_svc.find_records.call_args
        assert call_kwargs.kwargs.get("fields") == "Name,Email"

    @patch("fmcli.cli.record.record_service")
    @patch("fmcli.cli.record.get_profile")
    def test_find_sort_passed(self, mock_resolve: MagicMock, mock_svc: MagicMock) -> None:
        """--sort が service に渡される."""
        mock_resolve.return_value = make_profile()
        mock_svc.find_records.return_value = make_envelope("record find", data=[])

        runner.invoke(
            app,
            [
                "record",
                "find",
                "-l",
                "Contacts",
                "-q",
                '{"Name":"田中"}',
                "--sort",
                "Name:ascend",
            ],
        )

        mock_svc.find_records.assert_called_once()
        call_kwargs = mock_svc.find_records.call_args
        assert call_kwargs.kwargs.get("sort") == "Name:ascend"

    @patch("fmcli.cli.record.record_service")
    @patch("fmcli.cli.record.get_profile")
    def test_find_portal_passed(self, mock_resolve: MagicMock, mock_svc: MagicMock) -> None:
        """--portal が service に渡される."""
        mock_resolve.return_value = make_profile()
        mock_svc.find_records.return_value = make_envelope("record find", data=[])

        runner.invoke(
            app,
            [
                "record",
                "find",
                "-l",
                "Contacts",
                "-q",
                '{"Name":"田中"}',
                "--portal",
                "Portal1:10",
            ],
        )

        mock_svc.find_records.assert_called_once()
        call_kwargs = mock_svc.find_records.call_args
        assert call_kwargs.kwargs.get("portal") == "Portal1:10"

    @patch("fmcli.cli.record.explain_service")
    @patch("fmcli.cli.record.get_profile")
    def test_find_dry_run_calls_explain_service(
        self, mock_resolve: MagicMock, mock_explain: MagicMock
    ) -> None:
        """--dry-run で explain_service.dry_run_find が呼ばれ、オプションが伝搬される."""
        mock_resolve.return_value = make_profile()
        mock_explain.dry_run_find.return_value = make_envelope(
            "record find --dry-run", data={"request": {}}
        )

        result = runner.invoke(
            app,
            [
                "record",
                "find",
                "-l",
                "Contacts",
                "-q",
                '{"Name":"田中"}',
                "--limit",
                "50",
                "--offset",
                "3",
                "--sort",
                "Name:descend",
                "--fields",
                "Name,Email",
                "--portal",
                "Orders:5",
                "--dry-run",
            ],
        )

        assert result.exit_code == 0
        mock_explain.dry_run_find.assert_called_once()
        call_kwargs = mock_explain.dry_run_find.call_args.kwargs
        assert call_kwargs.get("query") == '{"Name":"田中"}'
        assert call_kwargs.get("limit") == 50
        assert call_kwargs.get("offset") == 3
        assert call_kwargs.get("sort") == "Name:descend"
        assert call_kwargs.get("fields") == "Name,Email"
        assert call_kwargs.get("portal") == "Orders:5"

    @patch("fmcli.cli.record.get_profile")
    def test_find_config_error(self, mock_resolve: MagicMock) -> None:
        """ConfigError 発生時に EXIT_CONFIG で終了する."""
        mock_resolve.side_effect = ConfigError("接続先が特定できません。")

        result = runner.invoke(app, ["record", "find", "-l", "Contacts", "-q", '{"Name":"田中"}'])

        assert result.exit_code == EXIT_CONFIG

    @patch("fmcli.cli.record.record_service")
    @patch("fmcli.cli.record.get_profile")
    def test_find_auth_error(self, mock_resolve: MagicMock, mock_svc: MagicMock) -> None:
        """AuthError 発生時に EXIT_AUTH で終了する."""
        mock_resolve.return_value = make_profile()
        mock_svc.find_records.side_effect = AuthError(
            "セッションが無効です",
            error_type="auth_expired",
        )

        result = runner.invoke(app, ["record", "find", "-l", "Contacts", "-q", '{"Name":"田中"}'])

        assert result.exit_code == EXIT_AUTH

    def test_find_help(self) -> None:
        """--help でヘルプを表示する."""
        result = runner.invoke(app, ["record", "find", "--help"])
        assert result.exit_code == 0
        output = strip_ansi(result.output)
        assert "検索" in output
