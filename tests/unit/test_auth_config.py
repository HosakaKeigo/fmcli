"""auth config ウィザードのテスト."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import click
import pytest

from fmcli.core.errors import ConfigError
from fmcli.domain.envelopes import Envelope
from fmcli.domain.models import validate_host_scheme


class TestAuthConfigAllowInsecureHttp:
    """auth config が --allow-insecure-http を正しく伝搬するテスト."""

    def test_http_rejected_without_flag(self):
        """ウィザードでも http:// はデフォルトで拒否される."""
        with pytest.raises(ConfigError, match="安全でない HTTP"):
            validate_host_scheme("http://legacy.example.com")

    def test_http_accepted_with_flag(self):
        """allow_insecure_http=True なら http:// を許可する."""
        validate_host_scheme("http://legacy.example.com", allow_insecure_http=True)

    def test_run_config_passes_flag(self):
        """run_config が allow_insecure_http を validate_host_scheme に渡す."""
        from fmcli.cli.auth_config import run_config

        with (
            patch("fmcli.cli.auth_config.list_profiles", return_value=[]),
            patch("fmcli.cli.auth_config.validate_host_scheme") as mock_validate,
            patch("fmcli.cli.auth_config.load_credential", return_value=None),
            patch("fmcli.cli.auth_config.questionary") as mock_q,
        ):
            host_prompt = MagicMock()
            host_prompt.ask.return_value = "http://legacy.local"
            user_prompt = MagicMock()
            user_prompt.ask.return_value = None  # → Abort
            mock_q.text.side_effect = [host_prompt, user_prompt]

            with pytest.raises((click.exceptions.Exit, SystemExit)):
                run_config(allow_insecure_http=True)

            mock_validate.assert_called_once_with("http://legacy.local", allow_insecure_http=True)

    def test_run_config_rejects_http_by_default(self):
        """allow_insecure_http=False の場合、http:// は拒否される."""
        from fmcli.cli.auth_config import run_config

        with (
            patch("fmcli.cli.auth_config.list_profiles", return_value=[]),
            patch("fmcli.cli.auth_config.questionary") as mock_q,
        ):
            host_prompt = MagicMock()
            host_prompt.ask.return_value = "http://legacy.local"
            mock_q.text.return_value = host_prompt

            with pytest.raises((click.exceptions.Exit, SystemExit)):
                run_config(allow_insecure_http=False)


class TestAuthConfigCredentialWarning:
    """auth config で save_credential 失敗時に警告が出るテスト."""

    @staticmethod
    def _setup_wizard_mocks(mock_q, mock_api):
        """ウィザードの共通モック設定."""
        host_prompt = MagicMock()
        host_prompt.ask.return_value = "https://host.example.com"
        user_prompt = MagicMock()
        user_prompt.ask.return_value = "admin"
        mock_q.text.side_effect = [host_prompt, user_prompt]
        mock_q.password.return_value.ask.return_value = "pass"

        mock_api_obj = MagicMock()
        mock_api_obj.get_databases.return_value = (
            {"response": {"databases": [{"name": "TestDB"}]}},
            {},
        )
        mock_api.return_value = mock_api_obj

        mock_q.select.return_value.ask.return_value = "← 完了"

    def test_warns_on_credential_save_failure(self):
        """keyring 保存失敗時にコンソールに警告が表示される."""
        from fmcli.cli.auth_config import run_config

        with (
            patch("fmcli.cli.auth_config.questionary") as mock_q,
            patch("fmcli.cli.auth_config.validate_host_scheme"),
            patch("fmcli.cli.auth_config.list_profiles", return_value=[]),
            patch("fmcli.cli.auth_config.load_credential", return_value=None),
            patch("fmcli.cli.auth_config.save_credential", return_value=False),
            patch("fmcli.cli.auth_config.create_api") as mock_api,
            patch("fmcli.cli.auth_config.console") as mock_console,
        ):
            self._setup_wizard_mocks(mock_q, mock_api)
            run_config()

            warning_calls = [
                str(call)
                for call in mock_console.print.call_args_list
                if "認証情報の永続化に失敗" in str(call)
            ]
            assert len(warning_calls) > 0, "keyring 失敗時の警告が表示されていない"

    def test_no_warning_on_credential_save_success(self):
        """keyring 保存成功時に警告は表示されない."""
        from fmcli.cli.auth_config import run_config

        with (
            patch("fmcli.cli.auth_config.questionary") as mock_q,
            patch("fmcli.cli.auth_config.validate_host_scheme"),
            patch("fmcli.cli.auth_config.list_profiles", return_value=[]),
            patch("fmcli.cli.auth_config.load_credential", return_value=None),
            patch("fmcli.cli.auth_config.save_credential", return_value=True),
            patch("fmcli.cli.auth_config.create_api") as mock_api,
            patch("fmcli.cli.auth_config.console") as mock_console,
        ):
            self._setup_wizard_mocks(mock_q, mock_api)
            run_config()

            warning_calls = [
                str(call)
                for call in mock_console.print.call_args_list
                if "認証情報の永続化に失敗" in str(call)
            ]
            assert len(warning_calls) == 0, "keyring 成功時に不要な警告が表示されている"


class TestConfigureDatabaseCredentialWarning:
    """DB 単位ログイン時に auth_service.login() の警告メッセージを表示するテスト."""

    def test_db_login_shows_credential_warning(self):
        """DB 単位ログインで keyring 保存失敗時に警告が表示される."""
        from fmcli.cli.auth_config import _configure_database

        warning_envelope = Envelope(
            ok=True,
            command="auth login",
            messages=["警告: 認証情報を keyring に保存できませんでした。"],
        )

        with (
            patch("fmcli.cli.auth_config.questionary") as mock_q,
            patch("fmcli.cli.auth_config.load_credential_exact", return_value=None),
            patch("fmcli.cli.auth_config.auth_service") as mock_auth,
            patch("fmcli.cli.auth_config.console") as mock_console,
        ):
            user_prompt = MagicMock()
            user_prompt.ask.return_value = "admin"
            mock_q.text.return_value = user_prompt
            mock_q.password.return_value.ask.return_value = ""  # ホスト共通パスワードを使用

            mock_auth.login.return_value = warning_envelope
            mock_console.input.return_value = ""  # Enter で戻る

            _configure_database("https://host.example.com", "TestDB", "admin", "pass")

            warning_calls = [
                str(call)
                for call in mock_console.print.call_args_list
                if "警告" in str(call) and "keyring" in str(call)
            ]
            assert len(warning_calls) > 0, "DB 単位ログイン時の keyring 警告が表示されていない"

    def test_db_login_no_warning_on_success(self):
        """DB 単位ログインで keyring 保存成功時に警告は出ない."""
        from fmcli.cli.auth_config import _configure_database

        ok_envelope = Envelope(ok=True, command="auth login", messages=[])

        with (
            patch("fmcli.cli.auth_config.questionary") as mock_q,
            patch("fmcli.cli.auth_config.load_credential_exact", return_value=None),
            patch("fmcli.cli.auth_config.auth_service") as mock_auth,
            patch("fmcli.cli.auth_config.console") as mock_console,
        ):
            user_prompt = MagicMock()
            user_prompt.ask.return_value = "admin"
            mock_q.text.return_value = user_prompt
            mock_q.password.return_value.ask.return_value = ""

            mock_auth.login.return_value = ok_envelope
            mock_console.input.return_value = ""

            _configure_database("https://host.example.com", "TestDB", "admin", "pass")

            warning_calls = [
                str(call)
                for call in mock_console.print.call_args_list
                if "警告" in str(call) and "keyring" in str(call)
            ]
            assert len(warning_calls) == 0, "keyring 成功時に不要な警告が表示されている"
