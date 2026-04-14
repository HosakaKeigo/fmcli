"""auth config ウィザード."""

from __future__ import annotations

import sys

import questionary
import typer
from rich.console import Console
from rich.table import Table

from fmcli.cli.error_handler import handle_errors
from fmcli.core.errors import FmcliError
from fmcli.domain.models import Profile, make_profile_key, validate_host_scheme
from fmcli.infra.auth_store import load_credential, load_credential_exact, save_credential
from fmcli.infra.profile_store import list_profiles
from fmcli.infra.session_cache import resolve_cached_session
from fmcli.services import auth_service
from fmcli.services.api_factory import create_api

console = Console()

_DONE_LABEL = "← 完了"


def _clear_screen() -> None:
    """画面と scrollback を完全にクリアする."""
    # \033[2J = 画面クリア, \033[3J = scrollback クリア, \033[H = カーソルを左上へ
    sys.stdout.write("\033[2J\033[3J\033[H")
    sys.stdout.flush()


@handle_errors("auth config")
def run_config(*, allow_insecure_http: bool = False) -> None:
    """対話ウィザードで複数 DB を一括設定する."""
    # 1. ホスト URL（既存プロファイルから候補 + 自由入力）
    existing_hosts = sorted({p.canonical_host for p in list_profiles() if p.host})
    new_host_label = "新しいホストを入力..."

    if existing_hosts:
        choices = [questionary.Choice(title=h, value=h) for h in existing_hosts]
        choices.append(questionary.Choice(title=new_host_label, value=new_host_label))
        host = questionary.select("ホスト URL:", choices=choices).ask()
        if not host:
            raise typer.Abort()
        if host == new_host_label:
            host = questionary.text("ホスト URL:", default="https://").ask()
            if not host:
                raise typer.Abort()
    else:
        host = questionary.text("ホスト URL:", default="https://").ask()
        if not host:
            raise typer.Abort()

    host = host.rstrip("/")

    # ホスト URL スキーム検証
    warning = validate_host_scheme(host, allow_insecure_http=allow_insecure_http)
    if warning:
        console.print(f"[yellow]{warning}[/yellow]")

    # 2. 認証情報（keyring にあればデフォルト表示）
    saved_cred = load_credential(host)
    default_user = saved_cred[0] if saved_cred else ""

    username = questionary.text(
        "ユーザー名:",
        default=default_user,
    ).ask()
    if not username:
        raise typer.Abort()

    password = questionary.password("パスワード:").ask()
    if not password:
        raise typer.Abort()

    # 3. DB 一覧を取得
    console.print("[dim]データベース一覧を取得中...[/dim]")
    prof = Profile(host=host, database="")
    api = create_api(prof)
    with api:
        try:
            body, _ = api.get_databases(username, password)
        except FmcliError as e:
            console.print(f"[red]エラー: {e}[/red]")
            raise typer.Abort() from e

    databases: list[str] = [db["name"] for db in body.get("response", {}).get("databases", [])]
    if not databases:
        console.print("[yellow]データベースが見つかりません[/yellow]")
        raise typer.Abort()

    # host レベルの認証情報を保存
    if not save_credential(host, username, password):
        console.print(
            "[yellow]⚠ 認証情報の永続化に失敗しました (keyring 不可)。"
            "セッション期限切れ時の自動リフレッシュは動作しません。[/yellow]"
        )

    # 4. メニューループ: DB一覧 → 選択 → 編集 → 戻る
    while True:
        _clear_screen()
        _print_db_table(host, databases)

        choices = _build_db_choices(host, databases)
        choices.append(questionary.Choice(title=_DONE_LABEL, value=_DONE_LABEL))

        selected = questionary.select(
            "設定するデータベースを選択:",
            choices=choices,
        ).ask()

        if not selected or selected == _DONE_LABEL:
            break

        _configure_database(host, selected, username, password)

    # 最終サマリ
    console.print()
    _print_db_table(host, databases)
    console.print("[bold]設定完了[/bold]")


def _has_credential(host: str, db_name: str) -> bool:
    """DB 単位の認証情報が保存済みか (host フォールバックなし)."""
    profile_key = make_profile_key(host, db_name)
    return load_credential_exact(profile_key) is not None


def _build_db_choices(host: str, databases: list[str]) -> list[questionary.Choice]:
    """DB 選択肢を構築する（設定済みには ✓ マーク）."""
    choices = []
    for db in databases:
        mark = "✓ " if _has_credential(host, db) else "  "
        choices.append(questionary.Choice(title=f"{mark}{db}", value=db))
    return choices


def _print_db_table(host: str, databases: list[str]) -> None:
    """DB 一覧とステータスをテーブル表示する."""
    table = Table(title=f"データベース一覧 ({host})")
    table.add_column("Database", style="cyan")
    table.add_column("User")
    table.add_column("Session", justify="center")

    for db_name in databases:
        prof = Profile(host=host, database=db_name)
        profile_key = prof.profile_key

        # ユーザー名 (DB 単位のみ)
        cred = load_credential_exact(profile_key)
        user_display = cred[0] if cred else "[dim]—[/dim]"

        # セッション状態
        resolved = resolve_cached_session(prof, scope="auto")
        session_display = "[green]✓[/green]" if resolved else "[dim]—[/dim]"

        table.add_row(db_name, user_display, session_display)

    console.print(table)


def _configure_database(
    host: str,
    db_name: str,
    default_user: str,
    default_pass: str,
) -> None:
    """1つの DB の認証情報を編集してログインする.

    失敗時はリトライループ。成功時は Enter で戻る。
    questionary プロンプトで Ctrl+C を押すとメニューに戻る。
    """
    profile_key = make_profile_key(host, db_name)

    # DB 別の認証情報があればそちらをデフォルトに (host フォールバックなし)
    db_cred = load_credential_exact(profile_key)
    db_user = db_cred[0] if db_cred else default_user
    db_pass = db_cred[1] if db_cred else default_pass
    is_new = db_cred is None
    last_error: str | None = None

    while True:
        _clear_screen()
        console.print(f"\n[bold]── {db_name} ──[/bold]")
        if last_error:
            console.print(f"[red]✗ {last_error}[/red]")
            console.print("[dim]再入力してください (Ctrl+C で戻る)[/dim]\n")
        db_user = questionary.text(
            "ユーザー名:",
            default=db_user,
        ).ask()
        if not db_user:
            return

        if is_new:
            console.print("[dim]パスワード (Enter でホスト共通パスワードを使用):[/dim]")
            new_pass = questionary.password("パスワード:").ask()
            if new_pass:
                db_pass = new_pass
        else:
            change_pass = questionary.confirm(
                "パスワードを変更しますか?",
                default=False,
            ).ask()
            if change_pass:
                new_pass = questionary.password("新しいパスワード:").ask()
                if new_pass:
                    db_pass = new_pass

        # ログイン実行
        prof = Profile(host=host, database=db_name)
        try:
            envelope = auth_service.login(prof, db_user, db_pass)
            console.print(f"[green]✓ {db_name}: ログイン成功[/green]")
            # credential 永続化失敗の警告を表示
            for msg in envelope.messages:
                if "警告" in msg or "永続化" in msg or "auto-refresh" in msg.lower():
                    console.print(f"[yellow]  ⚠ {msg}[/yellow]")
            console.input("[dim]Enter で戻る...[/dim]")
            return
        except FmcliError as e:
            last_error = f"{db_name}: {e}"
            is_new = True  # リトライ時はパスワード再入力を促す
