"""profile CLI コマンドのテスト."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from fmcli.core.errors import EXIT_CONFIG, ConfigError
from fmcli.main import app
from tests.unit.helpers import make_profile, strip_ansi

runner = CliRunner()


# ===================================================================
# profile list
# ===================================================================


class TestProfileList:
    """profile list コマンドのテスト."""

    @patch("fmcli.cli.profile.list_profiles")
    def test_list_with_profiles(self, mock_list: MagicMock) -> None:
        """プロファイルが存在する場合、一覧を JSON 出力する."""
        prof1 = make_profile("https://host1.example.com", "DB1")
        prof2 = make_profile("https://host2.example.com", "DB2")
        mock_list.return_value = [prof1, prof2]

        result = runner.invoke(app, ["profile", "list"])

        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output["ok"] is True
        assert len(output["data"]) == 2

    @patch("fmcli.cli.profile.list_profiles")
    def test_list_empty(self, mock_list: MagicMock) -> None:
        """プロファイルが存在しない場合、空リストを出力する."""
        mock_list.return_value = []

        result = runner.invoke(app, ["profile", "list"])

        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output["ok"] is True
        assert output["data"] == []

    @patch("fmcli.cli.profile.list_profiles")
    def test_list_includes_profile_key(self, mock_list: MagicMock) -> None:
        """出力にprofile_key フィールドが含まれる."""
        prof = make_profile()
        mock_list.return_value = [prof]

        result = runner.invoke(app, ["profile", "list"])

        output = json.loads(result.output)
        assert "profile_key" in output["data"][0]
        assert output["data"][0]["profile_key"] == prof.profile_key

    @patch("fmcli.cli.profile.list_profiles")
    def test_list_command_field(self, mock_list: MagicMock) -> None:
        """envelope の command フィールドが 'profile list' である."""
        mock_list.return_value = []

        result = runner.invoke(app, ["profile", "list"])

        output = json.loads(result.output)
        assert output["command"] == "profile list"

    def test_list_help(self) -> None:
        """--help でヘルプを表示する."""
        result = runner.invoke(app, ["profile", "list", "--help"])
        assert result.exit_code == 0
        output = strip_ansi(result.output)
        assert "プロファイル" in output or "list" in output


# ===================================================================
# profile show
# ===================================================================


class TestProfileShow:
    """profile show コマンドのテスト."""

    @patch("fmcli.cli.profile.get_profile")
    def test_show_default_profile(self, mock_resolve: MagicMock) -> None:
        """引数なしでデフォルトプロファイルの詳細を表示する."""
        prof = make_profile()
        mock_resolve.return_value = prof

        result = runner.invoke(app, ["profile", "show"])

        assert result.exit_code == 0
        output = json.loads(result.output)
        assert output["ok"] is True
        assert output["command"] == "profile show"
        assert output["data"]["host"] == "https://fm.example.com"
        assert output["data"]["database"] == "TestDB"
        assert output["data"]["profile_key"] == prof.profile_key

    @patch("fmcli.cli.profile.get_profile")
    def test_show_with_host_and_database(self, mock_resolve: MagicMock) -> None:
        """--host と --database を指定してプロファイルを表示する."""
        prof = make_profile("https://other.example.com", "OtherDB")
        mock_resolve.return_value = prof

        result = runner.invoke(
            app, ["profile", "show", "--host", "https://other.example.com", "-d", "OtherDB"]
        )

        assert result.exit_code == 0
        call_args = mock_resolve.call_args
        assert call_args.args[0] == "https://other.example.com"
        assert call_args.args[1] == "OtherDB"

    @patch("fmcli.cli.profile.get_profile")
    def test_show_config_error(self, mock_resolve: MagicMock) -> None:
        """プロファイルが見つからない場合にエラーで終了する."""
        mock_resolve.side_effect = ConfigError("接続先が特定できません。")

        result = runner.invoke(app, ["profile", "show"])

        assert result.exit_code == EXIT_CONFIG

    @patch("fmcli.cli.profile.get_profile")
    def test_show_includes_profile_key(self, mock_resolve: MagicMock) -> None:
        """出力に profile_key フィールドが含まれる."""
        prof = make_profile()
        mock_resolve.return_value = prof

        result = runner.invoke(app, ["profile", "show"])

        output = json.loads(result.output)
        assert output["data"]["profile_key"] == prof.profile_key

    def test_show_help(self) -> None:
        """--help でヘルプを表示する."""
        result = runner.invoke(app, ["profile", "show", "--help"])
        assert result.exit_code == 0
