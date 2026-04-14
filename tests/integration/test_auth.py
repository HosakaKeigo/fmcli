"""auth コマンドのインテグレーションテスト.

auth status/logout の全レイヤー通貫テスト。
auth login は対話プロンプトを必要とするため、session 事前作成で代替。
"""

from __future__ import annotations

import respx
from syrupy.assertion import SnapshotAssertion
from typer.testing import CliRunner

from fmcli.main import app

from .conftest import (
    FM_DATABASE,
    FM_HOST,
    FMDATA_BASE,
    make_fm_response,
    parse_json_output,
    sanitize_output,
)


class TestAuthStatus:
    """auth status コマンド."""

    def test_status_with_valid_session(
        self,
        runner: CliRunner,
        setup_session: object,
        respx_mock: respx.MockRouter,
        snapshot: SnapshotAssertion,
    ) -> None:
        """認証済み状態で status を確認できる."""
        respx_mock.get(url__regex=rf".*{FMDATA_BASE}/validateSession").respond(
            200, json=make_fm_response({})
        )

        result = runner.invoke(app, ["auth", "status", "--host", FM_HOST, "-d", FM_DATABASE])

        assert result.exit_code == 0
        data = parse_json_output(result.stdout)
        assert data["ok"] is True
        assert sanitize_output(result.stdout) == snapshot

    def test_status_with_expired_session(
        self, runner: CliRunner, setup_session: object, respx_mock: respx.MockRouter
    ) -> None:
        """セッション期限切れの場合でも status は返る."""
        expired_resp = {
            "messages": [{"code": "952", "message": "Invalid token"}],
            "response": {},
        }
        respx_mock.get(url__regex=rf".*{FMDATA_BASE}/validateSession").respond(
            401, json=expired_resp
        )

        result = runner.invoke(app, ["auth", "status", "--host", FM_HOST, "-d", FM_DATABASE])

        assert result.exit_code == 0
        data = parse_json_output(result.stdout)
        assert data["ok"] is True
        # status は valid=false を含む（エラーではない）

    def test_status_requires_host(self, runner: CliRunner) -> None:
        """--host 未指定時は typer がエラーを出す."""
        result = runner.invoke(app, ["auth", "status"])
        assert result.exit_code != 0


class TestAuthLogout:
    """auth logout コマンド."""

    def test_logout_requires_host(self, runner: CliRunner) -> None:
        """--host 未指定時は typer がエラーを出す."""
        result = runner.invoke(app, ["auth", "logout"])
        assert result.exit_code != 0

    def test_logout(
        self,
        runner: CliRunner,
        setup_session: object,
        respx_mock: respx.MockRouter,
        snapshot: SnapshotAssertion,
    ) -> None:
        """ログアウトが正常に動作する."""
        respx_mock.delete(url__regex=rf".*{FMDATA_BASE}/databases/.*/sessions/.*").respond(
            200, json=make_fm_response({})
        )

        result = runner.invoke(app, ["auth", "logout", "--host", FM_HOST, "-d", FM_DATABASE])

        assert result.exit_code == 0
        data = parse_json_output(result.stdout)
        assert data["ok"] is True
        assert sanitize_output(result.stdout) == snapshot


class TestAuthList:
    """auth list コマンド."""

    def test_list_no_sessions(self, runner: CliRunner, snapshot: SnapshotAssertion) -> None:
        """セッションなしの場合でもエラーにならない."""
        result = runner.invoke(app, ["auth", "list"])

        assert result.exit_code == 0
        data = parse_json_output(result.stdout)
        assert data["ok"] is True
        assert sanitize_output(result.stdout) == snapshot
