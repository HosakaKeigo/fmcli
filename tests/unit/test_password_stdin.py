"""--password-stdin オプションのテスト."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from fmcli.core.errors import EXIT_CONFIG
from fmcli.domain.envelopes import Envelope
from fmcli.main import app

runner = CliRunner()


class TestPasswordStdin:
    """--password-stdin フラグのテスト."""

    @patch("fmcli.cli.auth.auth_service")
    def test_password_read_from_stdin(self, mock_service: MagicMock) -> None:
        """--password-stdin でパスワードが stdin から読み取れること."""
        mock_service.login.return_value = Envelope(ok=True, data={"token": "xxx"})
        result = runner.invoke(
            app,
            [
                "auth",
                "login",
                "--host",
                "https://fm.example.com",
                "-d",
                "MyDB",
                "-u",
                "admin",
                "--password-stdin",
            ],
            input="secret123\n",
        )
        assert result.exit_code == 0, result.output
        mock_service.login.assert_called_once()
        _prof, username, password = mock_service.login.call_args[0][:3]
        assert username == "admin"
        assert password == "secret123"

    def test_password_stdin_without_username(self) -> None:
        """--password-stdin 時に -u 未指定でエラーになること."""
        result = runner.invoke(
            app,
            [
                "auth",
                "login",
                "--host",
                "https://fm.example.com",
                "-d",
                "MyDB",
                "--password-stdin",
            ],
            input="secret123\n",
        )
        assert result.exit_code == EXIT_CONFIG
        assert "--password-stdin" in result.output
        assert "-u" in result.output or "--username" in result.output

    def test_password_stdin_empty_input(self) -> None:
        """--password-stdin 時に stdin が空でエラーになること."""
        result = runner.invoke(
            app,
            [
                "auth",
                "login",
                "--host",
                "https://fm.example.com",
                "-d",
                "MyDB",
                "-u",
                "admin",
                "--password-stdin",
            ],
            input="",
        )
        assert result.exit_code == EXIT_CONFIG
        assert "標準入力" in result.output or "stdin" in result.output.lower()

    @patch("fmcli.cli.auth.auth_service")
    @patch("fmcli.cli.auth.typer.prompt")
    def test_interactive_flow_unchanged(
        self, mock_prompt: MagicMock, mock_service: MagicMock
    ) -> None:
        """--password-stdin なしの場合、既存の対話フローが壊れないこと."""
        mock_prompt.side_effect = ["admin", "secret"]
        mock_service.login.return_value = Envelope(ok=True, data={"token": "xxx"})
        result = runner.invoke(
            app,
            [
                "auth",
                "login",
                "--host",
                "https://fm.example.com",
                "-d",
                "MyDB",
            ],
        )
        assert result.exit_code == 0, result.output
        assert mock_prompt.call_count == 2  # Username + Password

    @patch("fmcli.cli.auth.auth_service")
    def test_password_stdin_with_whitespace(self, mock_service: MagicMock) -> None:
        """--password-stdin で前後の空白が除去されること."""
        mock_service.login.return_value = Envelope(ok=True, data={"token": "xxx"})
        result = runner.invoke(
            app,
            [
                "auth",
                "login",
                "--host",
                "https://fm.example.com",
                "-d",
                "MyDB",
                "-u",
                "admin",
                "--password-stdin",
            ],
            input="  mypassword  \n",
        )
        assert result.exit_code == 0, result.output
        _prof, _username, password = mock_service.login.call_args[0][:3]
        assert password == "mypassword"
