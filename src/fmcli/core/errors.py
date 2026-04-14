"""共通エラー型."""

from __future__ import annotations

import logging
import sys

from fmcli.domain.envelopes import Envelope, ErrorDetail
from fmcli.domain.error_codes import AuthErrorType, FmApiCode, HttpStatus

logger = logging.getLogger(__name__)

# --- 終了コード定義 ---
EXIT_GENERAL = 1
EXIT_INTERRUPT = 130
EXIT_AUTH = 41
EXIT_INPUT = 42
EXIT_TRANSPORT = 43
EXIT_API = 44
EXIT_CONFIG = 51
EXIT_NOT_FOUND = 52


class FmcliError(Exception):
    """CLI 基底エラー."""

    exit_code: int = EXIT_GENERAL

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


class AuthError(FmcliError):
    """認証エラー."""

    exit_code = EXIT_AUTH

    def __init__(
        self,
        message: str,
        *,
        error_type: AuthErrorType | str = AuthErrorType.REQUIRED,
        host: str = "",
        database: str = "",
        retryable: bool = False,
    ) -> None:
        super().__init__(message, retryable=retryable)
        self.error_type = error_type.value if isinstance(error_type, AuthErrorType) else error_type
        self.host = host
        self.database = database


class TransportError(FmcliError):
    """HTTP 通信エラー."""

    exit_code = EXIT_TRANSPORT

    def __init__(self, message: str, *, retryable: bool = True) -> None:
        super().__init__(message, retryable=retryable)


class ApiError(FmcliError):
    """FileMaker Data API エラー."""

    exit_code = EXIT_API

    def __init__(
        self,
        message: str,
        *,
        http_status: int = 0,
        api_code: int = 0,
        retryable: bool = False,
    ) -> None:
        super().__init__(message, retryable=retryable)
        self.http_status = http_status
        self.api_code = api_code


class ConfigError(FmcliError):
    """設定エラー."""

    exit_code = EXIT_CONFIG

    def __init__(
        self,
        message: str,
        *,
        error_code: str = "",
        retryable: bool = False,
    ) -> None:
        super().__init__(message, retryable=retryable)
        self.error_code = error_code


class NotFoundError(FmcliError):
    """リソースが見つからない."""

    exit_code = EXIT_NOT_FOUND


def _build_auth_hint(exc: AuthError) -> str:
    """AuthError の error_type に応じたアクション提示メッセージを生成する."""
    login_cmd_parts = ["fmcli auth login"]
    if exc.host:
        login_cmd_parts.append(f"--host {exc.host}")
    if exc.database:
        login_cmd_parts.append(f"--database {exc.database}")
    login_cmd = " ".join(login_cmd_parts)

    hints_by_type: dict[str, str] = {
        AuthErrorType.REQUIRED: (
            f"セッションがありません。次のコマンドで認証してください:\n  $ {login_cmd}"
        ),
        AuthErrorType.EXPIRED: (
            "セッションの有効期限が切れました。"
            "keyring に認証情報を保存していれば自動リフレッシュされます。\n"
            f"手動で再認証する場合:\n  $ {login_cmd}"
        ),
        AuthErrorType.INVALID: (
            "認証情報が正しくありません。ユーザー名・パスワードを確認して再ログインしてください:\n"
            f"  $ {login_cmd}"
        ),
        AuthErrorType.FORBIDDEN: (
            "アクセス権限がありません。FileMaker Server 側で fmrest 拡張アクセス権が"
            "有効になっているか確認してください。"
        ),
    }
    return hints_by_type.get(exc.error_type, f"次のコマンドで認証してください:\n  $ {login_cmd}")


_HTTP_HINTS: dict[int, str] = {
    HttpStatus.BAD_REQUEST: "リクエスト内容を確認してください。`--dry-run` で事前確認できます。",
    HttpStatus.NOT_FOUND: "URL が無効です。レイアウト名等を確認してください: `fmcli layout list`",
    HttpStatus.METHOD_NOT_ALLOWED: "HTTP メソッドが不正です。CLI のバージョンを確認してください。",
    HttpStatus.UNSUPPORTED_MEDIA_TYPE: (
        "Content-Type ヘッダが不正です。CLI のバージョンを確認してください。"
    ),
}


def _build_api_hint(exc: ApiError) -> str:
    """ApiError の http_status / api_code に応じたヒントを生成する."""
    hints: list[str] = []

    # --- FileMaker API エラーコード別ヒント ---
    try:
        fm_code = FmApiCode(exc.api_code)
        if fm_code.hint:
            hints.append(fm_code.hint)
    except ValueError:
        fm_code = None

    # --- HTTP ステータスコード別ヒント (FM コード固有ヒントがない場合のみ) ---
    if fm_code is None and exc.http_status in _HTTP_HINTS:
        hints.append(_HTTP_HINTS[exc.http_status])
    elif fm_code is None and exc.http_status >= 500:
        hints.append("FileMaker Server 側のエラーです。しばらく待ってリトライしてください。")

    return "\n".join(hints) if hints else ""


def _build_config_error_detail(exc: ConfigError) -> ErrorDetail:
    """ConfigError から ErrorDetail を構築する.

    error_code が 'no_profile' の場合は利用可能なプロファイル一覧を含める。
    """
    from fmcli.domain.envelopes import AvailableProfile

    available: list[AvailableProfile] | None = None
    error_code = exc.error_code or None
    hint = ""

    if exc.error_code == "no_profile":
        from fmcli.infra.profile_store import list_profiles

        try:
            profiles = list_profiles()
        except Exception:
            profiles = []

        if profiles:
            available = [
                AvailableProfile(
                    profile_key=p.profile_key,
                    host=p.host,
                    database=p.database,
                )
                for p in profiles
            ]
            hint = (
                "利用可能なプロファイルがあります。"
                "--host と --database を指定してリトライしてください。"
            )
        else:
            hint = (
                "プロファイルが存在しません。初回セットアップを行ってください:\n"
                "  $ fmcli auth login --host <ホスト> --database <データベース>"
            )
    else:
        hint = (
            "プロファイル設定を確認してください: `fmcli profile list`\n"
            "既存セッション一覧: `fmcli auth list`\n"
            "初回は `fmcli auth login` で認証してください。"
        )

    return ErrorDetail(
        message=str(exc),
        error_code=error_code,
        retryable=False,
        hint=hint,
        available_profiles=available,
    )


def build_error_envelope(
    exc: Exception,
    *,
    command: str = "",
) -> Envelope:
    """例外から正規化エラー Envelope を構築する."""
    if isinstance(exc, AuthError):
        detail = ErrorDetail(
            type=exc.error_type,
            message=str(exc),
            retryable=exc.retryable,
            hint=_build_auth_hint(exc),
            host=exc.host,
            database=exc.database,
        )
    elif isinstance(exc, ApiError):
        try:
            hs = HttpStatus(exc.http_status)
            status_desc = hs.label
        except ValueError:
            status_desc = ""
        message = str(exc)
        if status_desc and status_desc not in message:
            message = f"[HTTP {exc.http_status} {status_desc}] {message}"
        detail = ErrorDetail(
            message=message,
            http_status=exc.http_status,
            api_code=exc.api_code,
            retryable=exc.retryable,
            hint=_build_api_hint(exc),
        )
    elif isinstance(exc, TransportError):
        detail = ErrorDetail(
            message=str(exc),
            retryable=exc.retryable,
            hint="ネットワーク接続を確認してください。"
            "ホスト名・ポートが正しいか `fmcli auth status` で確認できます。",
        )
    elif isinstance(exc, ConfigError):
        detail = _build_config_error_detail(exc)
    elif isinstance(exc, NotFoundError):
        detail = ErrorDetail(
            message=str(exc),
            retryable=False,
            hint="リソース名を確認してください。"
            "レイアウト一覧: `fmcli layout list`、"
            "フィールド一覧: `fmcli schema find-schema -l <レイアウト名>`",
        )
    elif isinstance(exc, FmcliError):
        detail = ErrorDetail(
            message=str(exc),
            retryable=exc.retryable,
        )
    elif isinstance(exc, ValueError):
        detail = ErrorDetail(
            message=str(exc),
            hint="入力値を確認してください",
        )
    else:
        detail = ErrorDetail(
            message="予期しないエラーが発生しました",
            hint=str(exc),
        )
    return Envelope(ok=False, command=command, error=detail)


def emit_error_envelope(envelope: Envelope) -> None:
    """エラー Envelope を stderr に JSON 出力する."""
    sys.stderr.write(envelope.model_dump_json(indent=2, exclude_none=True) + "\n")
