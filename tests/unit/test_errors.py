"""エラー型のテスト."""

from __future__ import annotations

import json

import pytest
import typer
from typer.testing import CliRunner

from fmcli.cli.error_handler import handle_errors
from fmcli.core.errors import (
    EXIT_API,
    EXIT_AUTH,
    EXIT_CONFIG,
    EXIT_GENERAL,
    EXIT_INPUT,
    EXIT_INTERRUPT,
    EXIT_NOT_FOUND,
    EXIT_TRANSPORT,
    ApiError,
    AuthError,
    ConfigError,
    FmcliError,
    NotFoundError,
    TransportError,
    build_error_envelope,
)


class TestErrors:
    def test_base_error(self) -> None:
        e = FmcliError("test error")
        assert str(e) == "test error"
        assert e.retryable is False
        assert e.exit_code == EXIT_GENERAL

    def test_retryable_error(self) -> None:
        e = FmcliError("retry me", retryable=True)
        assert e.retryable is True

    def test_api_error(self) -> None:
        e = ApiError("Not Found", http_status=404, api_code=401)
        assert e.http_status == 404
        assert e.api_code == 401
        assert isinstance(e, FmcliError)
        assert e.exit_code == EXIT_API

    def test_auth_error(self) -> None:
        e = AuthError("bad credentials")
        assert isinstance(e, FmcliError)
        assert e.error_type == "auth_required"
        assert e.exit_code == EXIT_AUTH

    def test_auth_error_with_context(self) -> None:
        e = AuthError(
            "expired",
            error_type="auth_expired",
            host="https://fm.example.com",
            database="MyDB",
        )
        assert e.error_type == "auth_expired"
        assert e.host == "https://fm.example.com"
        assert e.database == "MyDB"

    def test_transport_error(self) -> None:
        e = TransportError("connection refused")
        assert isinstance(e, FmcliError)
        assert e.exit_code == EXIT_TRANSPORT
        assert e.retryable is True  # デフォルトで retryable

    def test_transport_error_non_retryable(self) -> None:
        e = TransportError("connection refused", retryable=False)
        assert e.retryable is False

    def test_config_error(self) -> None:
        e = ConfigError("missing host")
        assert isinstance(e, FmcliError)
        assert e.exit_code == EXIT_CONFIG

    def test_not_found_error(self) -> None:
        e = NotFoundError("resource missing")
        assert isinstance(e, FmcliError)
        assert e.exit_code == EXIT_NOT_FOUND

    def test_str_returns_japanese_message(self) -> None:
        e = FmcliError("認証エラーが発生しました")
        assert str(e) == "認証エラーが発生しました"

    def test_empty_message(self) -> None:
        e = FmcliError("")
        assert str(e) == ""

    def test_multiline_message(self) -> None:
        msg = "line1\nline2\nline3"
        e = FmcliError(msg)
        assert str(e) == msg

    @pytest.mark.parametrize(
        "cls,expected_code",
        [
            (FmcliError, 1),
            (AuthError, 41),
            (TransportError, 43),
            (ApiError, 44),
            (ConfigError, 51),
            (NotFoundError, 52),
        ],
    )
    def test_exit_code_class_attribute(self, cls: type, expected_code: int) -> None:
        """各サブクラスが固有の exit_code を持つ."""
        assert cls.exit_code == expected_code

    @pytest.mark.parametrize(
        "cls",
        [
            AuthError,
            TransportError,
            ApiError,
            ConfigError,
            NotFoundError,
        ],
    )
    def test_subclass_inherits_base(self, cls: type) -> None:
        """全サブクラスが FmcliError を継承する."""
        assert issubclass(cls, FmcliError)


class TestBuildErrorEnvelope:
    def test_fmcli_error(self) -> None:
        exc = FmcliError("base error", retryable=True)
        envelope = build_error_envelope(exc, command="test")
        assert envelope.ok is False
        assert envelope.command == "test"
        assert envelope.error is not None
        assert envelope.error.message == "base error"
        assert envelope.error.retryable is True

    def test_api_error(self) -> None:
        exc = ApiError("api fail", http_status=500, api_code=100, retryable=True)
        envelope = build_error_envelope(exc, command="record find")
        assert envelope.error is not None
        assert envelope.error.http_status == 500
        assert envelope.error.api_code == 100
        assert envelope.error.retryable is True
        assert "レコードが見つかりません" in envelope.error.hint

    def test_api_error_layout_missing(self) -> None:
        exc = ApiError("Layout is missing", http_status=500, api_code=105)
        envelope = build_error_envelope(exc, command="record find")
        assert envelope.error is not None
        assert "layout list" in envelope.error.hint
        assert "リトライ" not in envelope.error.hint

    def test_api_error_field_not_found(self) -> None:
        exc = ApiError("Field not found", http_status=400, api_code=401)
        envelope = build_error_envelope(exc, command="record find")
        assert envelope.error is not None
        assert "schema find-schema" in envelope.error.hint

    def test_api_error_no_records(self) -> None:
        exc = ApiError("No records match", http_status=400, api_code=402)
        envelope = build_error_envelope(exc, command="record find")
        assert envelope.error is not None
        assert "一致するレコードがありません" in envelope.error.hint

    def test_transport_error_envelope(self) -> None:
        exc = TransportError("connection refused")
        envelope = build_error_envelope(exc, command="test")
        assert envelope.error is not None
        assert "ネットワーク接続" in envelope.error.hint
        assert envelope.error.retryable is True

    def test_config_error_envelope(self) -> None:
        exc = ConfigError("missing config")
        envelope = build_error_envelope(exc, command="test")
        assert envelope.error is not None
        assert "profile list" in envelope.error.hint

    def test_config_error_no_profile_with_available(self) -> None:
        """no_profile エラー時に利用可能プロファイルが含まれる."""
        from unittest.mock import patch

        from fmcli.domain.models import Profile

        profiles = [
            Profile(host="https://fm1.example.com", database="DB1"),
            Profile(host="https://fm2.example.com", database="DB2"),
        ]
        exc = ConfigError("接続先が特定できません", error_code="no_profile")
        with patch(
            "fmcli.infra.profile_store.list_profiles",
            return_value=profiles,
        ):
            envelope = build_error_envelope(exc, command="layout list")
        assert envelope.error is not None
        assert envelope.error.error_code == "no_profile"
        assert envelope.error.available_profiles is not None
        assert len(envelope.error.available_profiles) == 2
        assert envelope.error.available_profiles[0].host == "https://fm1.example.com"
        assert envelope.error.available_profiles[0].database == "DB1"
        assert "リトライ" in envelope.error.hint

    def test_config_error_no_profile_empty(self) -> None:
        """プロファイルが0個の場合はセットアップを促す."""
        from unittest.mock import patch

        exc = ConfigError("接続先が特定できません", error_code="no_profile")
        with patch(
            "fmcli.infra.profile_store.list_profiles",
            return_value=[],
        ):
            envelope = build_error_envelope(exc, command="layout list")
        assert envelope.error is not None
        assert envelope.error.available_profiles is None
        assert "初回セットアップ" in envelope.error.hint

    def test_config_error_no_profile_json_serializable(self) -> None:
        """available_profiles が JSON にシリアライズできる."""
        from unittest.mock import patch

        from fmcli.domain.models import Profile

        profiles = [
            Profile(host="https://fm1.example.com", database="DB1"),
        ]
        exc = ConfigError("接続先が特定できません", error_code="no_profile")
        with patch(
            "fmcli.infra.profile_store.list_profiles",
            return_value=profiles,
        ):
            envelope = build_error_envelope(exc, command="layout list")
        json_str = envelope.model_dump_json(indent=2, exclude_none=True)
        parsed = json.loads(json_str)
        assert "available_profiles" in parsed["error"]
        ap = parsed["error"]["available_profiles"][0]
        assert ap["host"] == "https://fm1.example.com"
        assert ap["database"] == "DB1"

    def test_not_found_error_envelope(self) -> None:
        exc = NotFoundError("layout not found")
        envelope = build_error_envelope(exc, command="test")
        assert envelope.error is not None
        assert "layout list" in envelope.error.hint
        assert "schema find-schema" in envelope.error.hint

    def test_auth_error_required(self) -> None:
        exc = AuthError(
            "Authentication required",
            error_type="auth_required",
            host="https://fm.example.com",
            database="MyDB",
        )
        envelope = build_error_envelope(exc, command="record get")
        assert envelope.error is not None
        assert envelope.error.type == "auth_required"
        assert envelope.error.host == "https://fm.example.com"
        assert envelope.error.database == "MyDB"
        assert "fmcli auth login" in envelope.error.hint
        assert "--host https://fm.example.com" in envelope.error.hint
        assert "--database MyDB" in envelope.error.hint
        assert "セッションがありません" in envelope.error.hint

    def test_auth_error_expired(self) -> None:
        exc = AuthError(
            "Session expired",
            error_type="auth_expired",
            host="https://fm.example.com",
            database="MyDB",
        )
        envelope = build_error_envelope(exc, command="record get")
        assert envelope.error is not None
        assert "有効期限" in envelope.error.hint
        assert "自動リフレッシュ" in envelope.error.hint

    def test_auth_error_invalid(self) -> None:
        exc = AuthError(
            "Bad creds",
            error_type="auth_invalid",
            host="https://fm.example.com",
            database="MyDB",
        )
        envelope = build_error_envelope(exc, command="record get")
        assert envelope.error is not None
        assert "ユーザー名・パスワードを確認" in envelope.error.hint

    def test_auth_error_forbidden(self) -> None:
        exc = AuthError(
            "Forbidden",
            error_type="auth_forbidden",
        )
        envelope = build_error_envelope(exc, command="record get")
        assert envelope.error is not None
        assert "fmrest 拡張アクセス権" in envelope.error.hint

    def test_runtime_error_as_unexpected(self) -> None:
        """RuntimeError は予期しないエラーとして処理される."""
        exc = RuntimeError("not authenticated")
        envelope = build_error_envelope(exc, command="record get")
        assert envelope.error is not None
        assert envelope.error.message == "予期しないエラーが発生しました"

    def test_value_error(self) -> None:
        exc = ValueError("bad query json")
        envelope = build_error_envelope(exc, command="record find")
        assert envelope.error is not None
        assert envelope.error.message == "bad query json"
        assert "入力値" in envelope.error.hint

    def test_unexpected_error(self) -> None:
        exc = OSError("disk full")
        envelope = build_error_envelope(exc, command="test")
        assert envelope.error is not None
        assert envelope.error.message == "予期しないエラーが発生しました"
        assert "disk full" in envelope.error.hint

    def test_auth_error_without_host_database(self) -> None:
        """host/database が空の AuthError でもヒントが生成される."""
        exc = AuthError("No session", error_type="auth_required")
        envelope = build_error_envelope(exc, command="test")
        assert envelope.error is not None
        assert "fmcli auth login" in envelope.error.hint
        assert "--host" not in envelope.error.hint
        assert "--database" not in envelope.error.hint

    def test_auth_error_unknown_type_fallback_hint(self) -> None:
        """定義外の error_type ではフォールバックのヒントが使われる."""
        exc = AuthError("err", error_type="unknown_type")
        envelope = build_error_envelope(exc, command="test")
        assert envelope.error is not None
        assert "fmcli auth login" in envelope.error.hint

    def test_api_error_session_expired_952(self) -> None:
        exc = ApiError("Session expired", http_status=401, api_code=952)
        envelope = build_error_envelope(exc, command="record find")
        assert envelope.error is not None
        assert "セッション切れ" in envelope.error.hint

    def test_api_error_404_layout_hint(self) -> None:
        exc = ApiError("Not found", http_status=404, api_code=0)
        envelope = build_error_envelope(exc, command="record get")
        assert envelope.error is not None
        assert "layout list" in envelope.error.hint

    def test_api_error_400_dry_run_hint(self) -> None:
        exc = ApiError("Bad request", http_status=400, api_code=0)
        envelope = build_error_envelope(exc, command="record find")
        assert envelope.error is not None
        assert "--dry-run" in envelope.error.hint

    def test_api_error_502_server_hint(self) -> None:
        """500以上の HTTP ステータスは全てサーバーエラーヒント."""
        exc = ApiError("Bad gateway", http_status=502, api_code=0)
        envelope = build_error_envelope(exc, command="test")
        assert envelope.error is not None
        assert "FileMaker Server" in envelope.error.hint

    def test_api_error_combined_hints(self) -> None:
        """api_code が fm_code_hints にマッチする場合、そのヒントが優先される."""
        exc = ApiError("Field error on not found", http_status=404, api_code=401)
        envelope = build_error_envelope(exc, command="record find")
        assert envelope.error is not None
        assert "schema find-schema" in envelope.error.hint

    def test_api_error_no_hints(self) -> None:
        """ヒント対象外の status/code ではヒントが空になる."""
        exc = ApiError("Some error", http_status=200, api_code=999)
        envelope = build_error_envelope(exc, command="test")
        assert envelope.error is not None
        assert envelope.error.hint == ""

    def test_empty_command(self) -> None:
        """command が空文字でも構築できる."""
        exc = FmcliError("err")
        envelope = build_error_envelope(exc)
        assert envelope.command == ""

    def test_base_fmcli_error_no_hint(self) -> None:
        """FmcliError（サブクラスでない）にはヒントが設定されない."""
        exc = FmcliError("base error")
        envelope = build_error_envelope(exc, command="test")
        assert envelope.error is not None
        assert envelope.error.hint == ""

    def test_transport_error_retryable_flag(self) -> None:
        exc = TransportError("timeout", retryable=False)
        envelope = build_error_envelope(exc, command="test")
        assert envelope.error is not None
        assert envelope.error.retryable is False

    @pytest.mark.parametrize(
        "exc",
        [
            FmcliError("err"),
            AuthError("err"),
            ApiError("err"),
            TransportError("err"),
            ConfigError("err"),
            NotFoundError("err"),
            ValueError("err"),
            RuntimeError("err"),
        ],
    )
    def test_envelope_ok_is_false(self, exc: Exception) -> None:
        """エラー Envelope は常に ok=False."""
        envelope = build_error_envelope(exc, command="test")
        assert envelope.ok is False

    def test_json_output_format(self) -> None:
        """エラー Envelope を JSON にシリアライズできる."""
        exc = ApiError("Not found", http_status=404, api_code=401)
        envelope = build_error_envelope(exc, command="record find")
        json_str = envelope.model_dump_json(indent=2, exclude_none=True)
        parsed = json.loads(json_str)
        assert parsed["ok"] is False
        assert parsed["command"] == "record find"
        assert "[HTTP 404 見つかりません]" in parsed["error"]["message"]
        assert parsed["error"]["http_status"] == 404


class TestAuthErrorEdgeCases:
    """AuthError の追加エッジケース."""

    def test_default_error_type(self) -> None:
        e = AuthError("err")
        assert e.error_type == "auth_required"
        assert e.host == ""
        assert e.database == ""

    def test_unknown_error_type(self) -> None:
        """定義外の error_type も受け入れられる."""
        e = AuthError("err", error_type="custom_type")
        assert e.error_type == "custom_type"

    def test_retryable_auth_error(self) -> None:
        e = AuthError("expired", error_type="auth_expired", retryable=True)
        assert e.retryable is True


class TestApiErrorEdgeCases:
    """ApiError の追加エッジケース."""

    def test_defaults(self) -> None:
        e = ApiError("fail")
        assert e.http_status == 0
        assert e.api_code == 0
        assert e.retryable is False

    def test_session_expired_code(self) -> None:
        e = ApiError("Session expired", http_status=401, api_code=952)
        assert e.api_code == 952


class TestHandleErrorsDecorator:
    def test_handles_auth_error(self) -> None:
        test_app = typer.Typer()

        @test_app.command()
        @handle_errors("test cmd")
        def failing_cmd() -> None:
            raise AuthError(
                "Authentication required",
                error_type="auth_required",
                host="https://fm.example.com",
                database="MyDB",
            )

        runner = CliRunner()
        result = runner.invoke(test_app, [])
        assert result.exit_code == EXIT_AUTH
        parsed = json.loads(result.output)
        assert parsed["ok"] is False
        assert parsed["error"]["type"] == "auth_required"

    def test_handles_config_error(self) -> None:
        test_app = typer.Typer()

        @test_app.command()
        @handle_errors("test cmd")
        def failing_cmd() -> None:
            raise ConfigError("missing config")

        runner = CliRunner()
        result = runner.invoke(test_app, [])
        assert result.exit_code == EXIT_CONFIG

    def test_handles_transport_error(self) -> None:
        test_app = typer.Typer()

        @test_app.command()
        @handle_errors("test cmd")
        def failing_cmd() -> None:
            raise TransportError("connection refused")

        runner = CliRunner()
        result = runner.invoke(test_app, [])
        assert result.exit_code == EXIT_TRANSPORT

    def test_handles_value_error(self) -> None:
        test_app = typer.Typer()

        @test_app.command()
        @handle_errors("test cmd")
        def failing_cmd() -> None:
            raise ValueError("bad input")

        runner = CliRunner()
        result = runner.invoke(test_app, [])
        assert result.exit_code == EXIT_INPUT

    def test_handles_runtime_error(self) -> None:
        test_app = typer.Typer()

        @test_app.command()
        @handle_errors("test cmd")
        def failing_cmd() -> None:
            raise RuntimeError("not authed")

        runner = CliRunner()
        result = runner.invoke(test_app, [])
        assert result.exit_code == EXIT_GENERAL

    def test_handles_abort_as_interrupt_without_json(self) -> None:
        test_app = typer.Typer()

        @test_app.command()
        @handle_errors("test cmd")
        def aborted_cmd() -> None:
            raise typer.Abort()

        runner = CliRunner()
        result = runner.invoke(test_app, [])
        assert result.exit_code == EXIT_INTERRUPT
        assert '"ok": false' not in result.output

    def test_handles_keyboard_interrupt_without_json(self) -> None:
        test_app = typer.Typer()

        @test_app.command()
        @handle_errors("test cmd")
        def interrupted_cmd() -> None:
            raise KeyboardInterrupt()

        runner = CliRunner()
        result = runner.invoke(test_app, [])
        assert result.exit_code == EXIT_INTERRUPT
        assert '"ok": false' not in result.output

    def test_handles_unexpected_error(self) -> None:
        test_app = typer.Typer()

        @test_app.command()
        @handle_errors("test cmd")
        def failing_cmd() -> None:
            raise OSError("boom")

        runner = CliRunner()
        result = runner.invoke(test_app, [])
        assert result.exit_code == EXIT_GENERAL

    def test_success_passes_through(self) -> None:
        test_app = typer.Typer()

        @test_app.command()
        @handle_errors("test cmd")
        def ok_cmd() -> None:
            print("ok")

        runner = CliRunner()
        result = runner.invoke(test_app, [])
        assert result.exit_code == 0
        assert "ok" in result.output

    def test_not_found_error_exit_code(self) -> None:
        app = typer.Typer()

        @app.command()
        @handle_errors("test")
        def cmd() -> None:
            raise NotFoundError("layout not found")

        runner = CliRunner()
        result = runner.invoke(app, [])
        assert result.exit_code == EXIT_NOT_FOUND

    def test_api_error_exit_code(self) -> None:
        app = typer.Typer()

        @app.command()
        @handle_errors("test")
        def cmd() -> None:
            raise ApiError("api fail", http_status=500, api_code=100)

        runner = CliRunner()
        result = runner.invoke(app, [])
        assert result.exit_code == EXIT_API

    def test_typer_exit_passes_through(self) -> None:
        """typer.Exit はそのまま通過する."""
        app = typer.Typer()

        @app.command()
        @handle_errors("test")
        def cmd() -> None:
            raise typer.Exit(0)

        runner = CliRunner()
        result = runner.invoke(app, [])
        assert result.exit_code == 0

    def test_error_output_is_valid_json(self) -> None:
        """エラー出力が正しい JSON 形式である."""
        app = typer.Typer()

        @app.command()
        @handle_errors("test cmd")
        def cmd() -> None:
            raise AuthError(
                "No session",
                error_type="auth_required",
                host="https://fm.example.com",
                database="TestDB",
            )

        runner = CliRunner()
        result = runner.invoke(app, [])
        parsed = json.loads(result.output)
        assert "error" in parsed
        assert parsed["error"]["type"] == "auth_required"
        assert parsed["error"]["host"] == "https://fm.example.com"

    def test_decorator_preserves_function_name(self) -> None:
        """functools.wraps により関数名が保持される."""

        @handle_errors("test")
        def my_function() -> None:
            pass

        assert my_function.__name__ == "my_function"
