"""metadata サブコマンド群 (host, database, layout, script)."""

import importlib

import typer

from fmcli.cli.common import (
    AllowInsecureHttp,
    Database,
    Host,
    Layout,
    filter_layouts_by_keywords,
    get_profile,
)
from fmcli.cli.error_handler import handle_errors
from fmcli.core.output import print_output
from fmcli.infra.auth_store import load_credential, save_credential
from fmcli.infra.profile_store import save_profile
from fmcli.services import metadata_service

host_app = typer.Typer(
    no_args_is_help=True,
    help="ホスト情報。サブコマンド: info",
)
database_app = typer.Typer(
    no_args_is_help=True,
    help="データベース操作。サブコマンド: list",
)
layout_app = typer.Typer(
    no_args_is_help=True,
    help="""\b
レイアウト操作。サブコマンド: list, describe

使用例:
  fmcli layout list                      # レイアウト一覧
  fmcli layout describe -l 'レイアウト名'  # フィールド構造・メタデータ
""",
)
script_app = typer.Typer(
    no_args_is_help=True,
    help="スクリプト操作。サブコマンド: list",
)


def _save_layout_cache(profile_key: str, layout_names: list[str]) -> None:
    """補完モジュールがある場合のみレイアウト名キャッシュを保存する."""
    try:
        completions = importlib.import_module("fmcli.cli.completions")
    except ModuleNotFoundError:
        return

    save_layout_cache = getattr(completions, "save_layout_cache", None)
    if callable(save_layout_cache):
        save_layout_cache(profile_key, layout_names)


@host_app.command()
@handle_errors("host info")
def info(
    host: Host = None,
    database: Database = None,
    allow_insecure_http: AllowInsecureHttp = False,
) -> None:
    """ホスト情報を表示する."""
    prof = get_profile(host, database, allow_insecure_http)
    envelope = metadata_service.host_info(prof)
    print_output(envelope)


@database_app.command(name="list")
@handle_errors("database list")
def database_list(
    host: Host = None,
    username: str = typer.Option(None, "--username", "-u", help="ユーザー名"),
    allow_insecure_http: AllowInsecureHttp = False,
) -> None:
    """データベース一覧を表示する.

    \b
    FileMaker Data API の仕様上、Basic 認証が必要です。
    認証済み (auth login 済み) の場合は keyring の認証情報を再利用します。
    未認証の場合はユーザー名・パスワードを対話入力してください。
    """
    prof = get_profile(host, None, allow_insecure_http)

    # keyring に認証情報があればそのまま呼ぶ（プロンプトなし）
    password: str | None = None
    if not username:
        cred = load_credential(prof.canonical_host)
        if cred:
            username, password = cred

    # keyring になければ対話入力
    if not username:
        username = typer.prompt("Username")
    if not password:
        password = typer.prompt("Password", hide_input=True)

    envelope = metadata_service.database_list(prof, username, password)

    # DB一覧取得成功時にプロファイル・認証情報を保存
    updated_prof = prof.model_copy(update={"name": prof.profile_key, "username": username})
    save_profile(updated_prof)
    save_credential(prof.canonical_host, username, password)

    print_output(envelope)


@layout_app.command(name="list")
@handle_errors("layout list")
def layout_list(
    filter_text: str | None = typer.Option(
        None,
        "--filter",
        help="レイアウト名の絞り込み（部分一致、カンマ区切りで OR 検索）",
    ),
    host: Host = None,
    database: Database = None,
    allow_insecure_http: AllowInsecureHttp = False,
) -> None:
    """レイアウト一覧を表示する.

    \b
    使用例:
      fmcli layout list                    # 全レイアウト
      fmcli layout list --filter 'Cust'       # 「Cust」を含むレイアウト
      fmcli layout list --filter 'Cust,Sales' # 「Cust」または「Sales」を含むレイアウト
    """
    prof = get_profile(host, database, allow_insecure_http)
    envelope = metadata_service.layout_list(prof)

    # レイアウト名をキャッシュに保存 (補完用)
    if envelope.ok and isinstance(envelope.data, list):
        layout_names = [
            item["name"] for item in envelope.data if isinstance(item, dict) and "name" in item
        ]
        _save_layout_cache(prof.profile_key, layout_names)

        if filter_text:
            envelope.data = filter_layouts_by_keywords(envelope.data, filter_text)

    print_output(envelope)


@layout_app.command()
@handle_errors("layout describe")
def describe(
    layout: Layout = ...,  # type: ignore[assignment]
    value_lists: bool = typer.Option(False, "--value-lists", "--vl", help="値リストのみ表示"),
    host: Host = None,
    database: Database = None,
    allow_insecure_http: AllowInsecureHttp = False,
) -> None:
    """レイアウトのメタデータを表示する."""
    prof = get_profile(host, database, allow_insecure_http)
    if value_lists:
        envelope = metadata_service.layout_value_lists(prof, layout)
    else:
        envelope = metadata_service.layout_describe(prof, layout)
    print_output(envelope)


@script_app.command(name="list")
@handle_errors("script list")
def script_list(
    host: Host = None,
    database: Database = None,
    allow_insecure_http: AllowInsecureHttp = False,
) -> None:
    """スクリプト一覧を表示する."""
    prof = get_profile(host, database, allow_insecure_http)
    envelope = metadata_service.script_list(prof)
    print_output(envelope)
