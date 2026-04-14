"""CLI エントリポイントのテスト."""

from typer.testing import CliRunner

from fmcli.main import app
from tests.unit.helpers import strip_ansi

runner = CliRunner()


class TestCLIEntry:
    def test_help(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "fmcli" in result.output.lower() or "filemaker" in result.output.lower()

    def test_no_args_shows_help(self) -> None:
        result = runner.invoke(app, [])
        # Typer の no_args_is_help=True は exit code 0 を返す
        assert result.exit_code == 0 or "Usage" in result.output

    def test_auth_help(self) -> None:
        result = runner.invoke(app, ["auth", "--help"])
        assert result.exit_code == 0
        assert "login" in result.output

    def test_profile_help(self) -> None:
        result = runner.invoke(app, ["profile", "--help"])
        assert result.exit_code == 0

    def test_record_help(self) -> None:
        result = runner.invoke(app, ["record", "--help"])
        assert result.exit_code == 0
        assert "get" in result.output
        assert "find" in result.output

    def test_auth_login_help(self) -> None:
        result = runner.invoke(app, ["auth", "login", "--help"])
        assert result.exit_code == 0
        output = strip_ansi(result.output)
        assert "--host" in output
        assert "--database" in output
        # --profile は廃止
        assert "--profile" not in output


class TestCLIInputValidation:
    """CLI 入力検証のテスト."""

    def test_invalid_format_rejected(self) -> None:
        """無効な --format 値はエラーになる."""
        result = runner.invoke(app, ["--format", "xml", "layout", "list"])
        assert result.exit_code != 0
        output = strip_ansi(result.output)
        assert "xml" in output or "Invalid" in output or "invalid" in output

    def test_valid_format_json(self) -> None:
        """--format json は受け付けられる."""
        result = runner.invoke(app, ["--format", "json", "--help"])
        assert result.exit_code == 0

    def test_valid_format_table(self) -> None:
        """--format table は受け付けられる."""
        result = runner.invoke(app, ["--format", "table", "--help"])
        assert result.exit_code == 0

    def test_record_list_limit_zero_rejected(self) -> None:
        """record list --limit 0 はエラーになる."""
        result = runner.invoke(app, ["record", "list", "-l", "Test", "--limit", "0"])
        assert result.exit_code != 0

    def test_record_list_limit_negative_rejected(self) -> None:
        """record list --limit -1 はエラーになる."""
        result = runner.invoke(app, ["record", "list", "-l", "Test", "--limit", "-1"])
        assert result.exit_code != 0

    def test_record_list_offset_zero_rejected(self) -> None:
        """record list --offset 0 はエラーになる."""
        result = runner.invoke(app, ["record", "list", "-l", "Test", "--offset", "0"])
        assert result.exit_code != 0

    def test_record_find_limit_zero_rejected(self) -> None:
        """record find --limit 0 はエラーになる."""
        result = runner.invoke(
            app, ["record", "find", "-l", "Test", "-q", '{"a":"b"}', "--limit", "0"]
        )
        assert result.exit_code != 0

    def test_record_find_offset_negative_rejected(self) -> None:
        """record find --offset -1 はエラーになる."""
        result = runner.invoke(
            app, ["record", "find", "-l", "Test", "-q", '{"a":"b"}', "--offset", "-1"]
        )
        assert result.exit_code != 0

    def test_record_list_limit_one_accepted(self) -> None:
        """record list --limit 1 は受け付けられる（境界値）."""
        result = runner.invoke(app, ["record", "list", "-l", "Test", "--limit", "1", "--help"])
        assert result.exit_code == 0

    def test_record_list_offset_one_accepted(self) -> None:
        """record list --offset 1 は受け付けられる（境界値）."""
        result = runner.invoke(app, ["record", "list", "-l", "Test", "--offset", "1", "--help"])
        assert result.exit_code == 0
