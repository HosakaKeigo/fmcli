"""auth サブコマンド群."""

import sys

import typer

from fmcli.cli.common import AllowInsecureHttp, DatabaseRequired, HostRequired, get_profile
from fmcli.cli.error_handler import handle_errors
from fmcli.core.errors import ConfigError
from fmcli.core.output import print_output
from fmcli.domain.models import Profile
from fmcli.domain.types import AuthScope as LoginScope
from fmcli.domain.types import StatusScope
from fmcli.services import auth_service

app = typer.Typer(
    no_args_is_help=True,
    help="""\b
認証管理。サブコマンド: login, logout, status, list, config

初期設定は対話ウィザード (config) を推奨:
  fmcli auth config    # ホスト・DB を対話的に一括設定

使用例:
  fmcli auth config                           # 対話ウィザードで一括設定（推奨）
  fmcli auth login --host https://fm.example.com -d MyDB  # 個別ログイン
  fmcli auth status                           # 認証状態を確認
  fmcli auth list                             # 保存済みセッション一覧
  fmcli auth logout                           # ログアウト
""",
)


@app.command()
@handle_errors("auth login")
def login(
    host: HostRequired,
    database: DatabaseRequired,
    username: str = typer.Option(None, "--username", "-u", help="ユーザー名"),
    scope: LoginScope = typer.Option("database", "--scope", help="保存 scope (database|host)"),
    no_verify_ssl: bool = typer.Option(False, "--no-verify-ssl", help="SSL 検証を無効化"),
    password_stdin: bool = typer.Option(
        False,
        "--password-stdin",
        help="パスワードを標準入力から読み取る（非対話モード用）",
    ),
    allow_insecure_http: AllowInsecureHttp = False,
) -> None:
    """FileMaker Data API にログインする.

    \b
    --host と -d（データベース名）は必須。
    初回セットアップには対話ウィザード (fmcli auth config) が便利です。

    \b
    接続情報を受け取り、認証し、profile を自動保存する。
    profile 名は host|database から自動生成される。

    \b
    使用例:
      # 初期設定（推奨）
      fmcli auth config

      # 個別ログイン
      fmcli auth login --host https://fm.example.com -d MyDB

      # host scope でログイン (同一 host 上の全 database で共有)
      fmcli auth login --host https://fm.example.com -d MyDB --scope host

      # 非対話的にログイン (パイプ経由)
      echo 'mypass' | fmcli auth login \\
        --host https://fm.example.com -d MyDB -u admin --password-stdin
    """
    if no_verify_ssl:
        print(
            "⚠ WARNING: SSL 検証が無効化されています。"
            "中間者攻撃のリスクがあります。本番環境では使用しないでください。",
            file=sys.stderr,
        )
    prof = _build_login_profile(
        host=host,
        database=database,
        no_verify_ssl=no_verify_ssl,
        allow_insecure_http=allow_insecure_http,
    )

    if password_stdin:
        if not username:
            raise ConfigError("--password-stdin を使用する場合は -u/--username の指定が必要です。")
        password = sys.stdin.readline().strip()
        if not password:
            raise ConfigError(
                "--password-stdin が指定されましたが、"
                "標準入力からパスワードを読み取れませんでした。"
            )
    else:
        if not username:
            username = prof.username or typer.prompt("Username")
        password = typer.prompt("Password", hide_input=True)

    envelope = auth_service.login(prof, username, password, scope=scope)
    print_output(envelope)


@app.command()
def config(
    allow_insecure_http: AllowInsecureHttp = False,
) -> None:
    """対話ウィザードで複数 DB を一括設定する（初期設定に推奨）."""
    from fmcli.cli.auth_config import run_config

    run_config(allow_insecure_http=allow_insecure_http)


@app.command(name="list")
@handle_errors("auth list")
def list_sessions() -> None:
    """保存済みセッション一覧を表示する."""
    envelope = auth_service.list_sessions()
    print_output(envelope)


@app.command()
@handle_errors("auth logout")
def logout(
    host: HostRequired,
    database: DatabaseRequired,
    scope: StatusScope = typer.Option("auto", "--scope", help="削除 scope (auto|database|host)"),
    allow_insecure_http: AllowInsecureHttp = False,
) -> None:
    """セッションを破棄する."""
    prof = get_profile(host, database, allow_insecure_http)
    envelope = auth_service.logout(prof, scope=scope)
    print_output(envelope)


@app.command()
@handle_errors("auth status")
def status(
    host: HostRequired,
    database: DatabaseRequired,
    scope: StatusScope = typer.Option("auto", "--scope", help="確認 scope (auto|database|host)"),
    allow_insecure_http: AllowInsecureHttp = False,
) -> None:
    """現在の認証状態を表示する."""
    prof = get_profile(host, database, allow_insecure_http)
    envelope = auth_service.status(prof, scope=scope)
    print_output(envelope)


def _build_login_profile(
    *,
    host: str,
    database: str,
    no_verify_ssl: bool,
    allow_insecure_http: bool = False,
) -> Profile:
    """login 用の Profile を構築する."""
    from fmcli.domain.models import validate_host_scheme

    warning = validate_host_scheme(host, allow_insecure_http=allow_insecure_http)
    if warning:
        print(warning, file=sys.stderr)
    return Profile(
        host=host,
        database=database,
        verify_ssl=not no_verify_ssl,
    )
