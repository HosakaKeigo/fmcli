"""record サブコマンド群."""

import json
import mimetypes
import sys
from pathlib import Path
from typing import Annotated, Any

import typer

from fmcli.cli.common import (
    AllowInsecureHttp,
    DatabaseWithPanel,
    HostWithPanel,
    Layout,
    get_profile,
)
from fmcli.cli.error_handler import handle_errors
from fmcli.core.output import print_output
from fmcli.services import explain_service, record_service

# --- rich_help_panel 定数 ---
_PANEL_SEARCH = "検索オプション"
_PANEL_PAGINATION = "ページネーション"
_PANEL_FIELD_PORTAL = "フィールド・ポータル"
_PANEL_SCRIPT = "スクリプト"
_PANEL_OTHER = "その他"

# --- 共通 Annotated 型エイリアス ---
Fields = Annotated[
    str | None,
    typer.Option(
        "--fields",
        help=(
            "出力フィールド絞り込み (カンマ区切り)。"
            "クライアント側フィルタ: API は全フィールドを返却し表示時に絞り込み"
        ),
        rich_help_panel=_PANEL_FIELD_PORTAL,
    ),
]
Portal = Annotated[
    str | None,
    typer.Option(
        "--portal",
        "-p",
        help="ポータル指定 (カンマ区切り, 例: Portal1:10,Portal2:5:2)",
        rich_help_panel=_PANEL_FIELD_PORTAL,
    ),
]
Script = Annotated[
    str | None,
    typer.Option(
        "--script",
        help="実行スクリプト (データ変更の可能性あり, 例: ScriptName:param)",
        rich_help_panel=_PANEL_SCRIPT,
    ),
]
ScriptPresort = Annotated[
    str | None,
    typer.Option("--script-presort", help="ソート前スクリプト", rich_help_panel=_PANEL_SCRIPT),
]
ScriptPrerequest = Annotated[
    str | None,
    typer.Option(
        "--script-prerequest",
        help="リクエスト前スクリプト",
        rich_help_panel=_PANEL_SCRIPT,
    ),
]
AllowScripts = Annotated[
    bool,
    typer.Option(
        "--allow-scripts",
        help="スクリプト実行を許可する (デフォルト: 無効)",
        rich_help_panel=_PANEL_SCRIPT,
    ),
]


def _validate_script_options(
    script: str | None,
    script_presort: str | None,
    script_prerequest: str | None,
    allow_scripts: bool,
) -> None:
    """スクリプトオプションのバリデーション.

    --allow-scripts なしでスクリプトが指定された場合はエラーを発生させる。
    --allow-scripts ありの場合はデータ変更の可能性を警告する。
    """
    has_scripts = any([script, script_presort, script_prerequest])
    if not has_scripts:
        return

    if not allow_scripts:
        specified: list[str] = []
        if script:
            specified.append("--script")
        if script_presort:
            specified.append("--script-presort")
        if script_prerequest:
            specified.append("--script-prerequest")
        opts = ", ".join(specified)
        raise typer.BadParameter(
            f"スクリプト実行はデフォルトで無効です (read-only 保護)。"
            f"\n指定されたオプション: {opts}"
            f"\nスクリプトはデータを変更する可能性があるため、"
            f"実行するには --allow-scripts フラグを追加してください。"
            f"\n例: fmcli record find -l Layout -q '{{}}' --script MyScript --allow-scripts"
        )

    # allow_scripts が有効な場合は警告のみ
    print(
        "Warning: スクリプトはデータを変更する可能性があります。",
        file=sys.stderr,
    )


_PANEL_WRITE = "書き込みオプション"


def _require_confirmation(*, yes: bool, details: list[str]) -> None:
    """write 操作の共通確認プロンプト."""
    if yes:
        return
    if not sys.stdin.isatty():
        raise typer.BadParameter(
            "write 操作には --yes フラグが必要です (非対話モード)。\n--dry-run で事前確認できます。"
        )
    for line in details:
        print(line, file=sys.stderr)
    if not typer.confirm("実行しますか?", default=False):
        raise typer.Abort()


def _confirm_write(layout: str, field_data: str, *, yes: bool) -> None:
    """write 操作の確認プロンプト."""
    summary = field_data[:200] + ("..." if len(field_data) > 200 else "")
    _require_confirmation(
        yes=yes,
        details=[f"レイアウト '{layout}' にレコードを作成します。", f"fieldData: {summary}"],
    )


def _confirm_update(
    layout: str,
    record_id: int,
    field_data: dict[str, Any],
    current_field_data: dict[str, Any],
    *,
    yes: bool,
) -> None:
    """update 操作の確認プロンプト (diff 表示付き)."""
    lines = [f"レイアウト '{layout}' のレコード {record_id} を更新します。"]
    for key, new_val in field_data.items():
        old_val = current_field_data.get(key, "(未設定)")
        lines.append(f"  {key}: {old_val!r} → {new_val!r}")
    _require_confirmation(yes=yes, details=lines)


def _confirm_upload(
    layout: str,
    record_id: int,
    field_name: str,
    file_path: str,
    file_size: int,
    *,
    yes: bool,
) -> None:
    """upload 操作の確認プロンプト."""
    size_str = _format_file_size(file_size)
    _require_confirmation(
        yes=yes,
        details=[
            f"レイアウト '{layout}' のレコード {record_id} のフィールド '{field_name}' に"
            f"ファイルをアップロードします。",
            f"  ファイル: {file_path} ({size_str})",
        ],
    )


def _format_file_size(size: int) -> str:
    """ファイルサイズを人間が読みやすい形式にフォーマットする."""
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    if size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    return f"{size / (1024 * 1024 * 1024):.1f} GB"


app = typer.Typer(
    no_args_is_help=True,
    help="""\b
レコード操作。サブコマンド: get, list, find, create, update, upload

使用例:
  fmcli record get 1 -l 'レイアウト名'                                      # ID 指定で 1 件取得
  fmcli record list -l 'レイアウト名' --limit 10                             # 一覧取得
  fmcli record find -l 'レイアウト名' -q '{"Name":"田中"}'                    # 検索
  fmcli record create -l 'レイアウト名' --field-data '{"Name":"田中"}' --yes  # レコード作成
  fmcli record update 1 -l 'レイアウト名' --field-data '{"Name":"鈴木"}' --mod-id 5 --yes  # 更新
  fmcli record upload 1 -l 'レイアウト名' --field Photo --file ./photo.jpg --yes  # アップロード
""",
)


@app.command()
@handle_errors("record get")
def get(
    record_id: int = typer.Argument(..., help="レコード ID"),
    layout: Layout = ...,  # type: ignore[assignment]
    fields: Fields = None,
    portal: Portal = None,
    script: Script = None,
    script_presort: ScriptPresort = None,
    script_prerequest: ScriptPrerequest = None,
    host: HostWithPanel = None,
    database: DatabaseWithPanel = None,
    allow_scripts: AllowScripts = False,
    allow_insecure_http: AllowInsecureHttp = False,
) -> None:
    """単一レコードを取得する."""
    _validate_script_options(script, script_presort, script_prerequest, allow_scripts)
    prof = get_profile(host, database, allow_insecure_http)
    envelope = record_service.get_record(
        prof,
        layout,
        record_id,
        fields=fields,
        portal=portal,
        script=script,
        script_presort=script_presort,
        script_prerequest=script_prerequest,
    )
    print_output(envelope)


@app.command(name="list")
@handle_errors("record list")
def list_records(
    layout: Layout = ...,  # type: ignore[assignment]
    limit: int = typer.Option(100, "--limit", help="取得件数", min=1),
    offset: int = typer.Option(1, "--offset", help="開始位置", min=1),
    sort: str = typer.Option(None, "--sort", "-s", help="ソート (例: Name:asc,Age:desc)"),
    fields: Fields = None,
    portal: Portal = None,
    script: Script = None,
    script_presort: ScriptPresort = None,
    script_prerequest: ScriptPrerequest = None,
    dry_run: bool = typer.Option(
        False, "--dry-run", help="実行せずリクエスト内容を表示", rich_help_panel=_PANEL_OTHER
    ),
    host: HostWithPanel = None,
    database: DatabaseWithPanel = None,
    allow_scripts: AllowScripts = False,
    allow_insecure_http: AllowInsecureHttp = False,
) -> None:
    """レコード一覧を取得する.

    \b
    使用例:
      # 基本的なレコード一覧取得
      fmcli record list --layout Contacts

      # 件数・開始位置を指定
      fmcli record list --layout Contacts --limit 50 --offset 10

      # 特定フィールドだけ取得 (トークン節約)
      fmcli record list --layout Contacts --fields "Name,Email,Phone"

      # ソート指定
      fmcli record list --layout Contacts --sort "Name:ascend"

      # ポータルデータを含める
      fmcli record list --layout Contacts --portal "RelatedItems:10"

      # dry-run でリクエスト内容だけ確認
      fmcli record list --layout Contacts --dry-run
    """
    _validate_script_options(script, script_presort, script_prerequest, allow_scripts)
    prof = get_profile(host, database, allow_insecure_http)
    if dry_run:
        envelope = explain_service.dry_run_record_list(
            prof,
            layout,
            offset=offset,
            limit=limit,
            sort=sort,
            portal=portal,
            script=script,
            script_presort=script_presort,
            script_prerequest=script_prerequest,
        )
    else:
        envelope = record_service.list_records(
            prof,
            layout,
            offset=offset,
            limit=limit,
            sort=sort,
            fields=fields,
            portal=portal,
            script=script,
            script_presort=script_presort,
            script_prerequest=script_prerequest,
        )
    print_output(envelope)


@app.command()
@handle_errors("record find")
def find(
    layout: Layout = ...,  # type: ignore[assignment]
    query: str | None = typer.Option(
        None,
        "--query",
        "-q",
        help="検索条件 JSON (--query または --query-file が必須)",
        rich_help_panel=_PANEL_SEARCH,
    ),
    query_file: str | None = typer.Option(
        None,
        "--query-file",
        "-f",
        help="検索条件 JSON ファイル (--query の代替)",
        rich_help_panel=_PANEL_SEARCH,
    ),
    first: bool = typer.Option(
        False, "--first", help="最初の 1 件だけ返す", rich_help_panel=_PANEL_SEARCH
    ),
    count: bool = typer.Option(
        False, "--count", help="件数だけ返す (レコードデータなし)", rich_help_panel=_PANEL_SEARCH
    ),
    with_schema: bool = typer.Option(
        False,
        "--with-schema",
        help="レスポンスにフィールドスキーマを含める",
        rich_help_panel=_PANEL_SEARCH,
    ),
    limit: int = typer.Option(
        100, "--limit", help="取得件数", min=1, rich_help_panel=_PANEL_PAGINATION
    ),
    offset: int = typer.Option(
        1, "--offset", help="開始位置", min=1, rich_help_panel=_PANEL_PAGINATION
    ),
    sort: str | None = typer.Option(
        None,
        "--sort",
        "-s",
        help="ソート (例: Name:asc / ascend も可)",
        rich_help_panel=_PANEL_PAGINATION,
    ),
    fields: Fields = None,
    portal: Portal = None,
    script: Script = None,
    script_presort: ScriptPresort = None,
    script_prerequest: ScriptPrerequest = None,
    host: HostWithPanel = None,
    database: DatabaseWithPanel = None,
    dry_run: bool = typer.Option(
        False, "--dry-run", help="実行せずリクエスト内容を表示", rich_help_panel=_PANEL_OTHER
    ),
    allow_scripts: AllowScripts = False,
    allow_insecure_http: AllowInsecureHttp = False,
) -> None:
    """レコードを検索する.

    \b
    ヒント: 検索前にフィールド名を確認してください。
      fmcli schema find-schema -l 'レイアウト名'  # 検索可能フィールド一覧
      fmcli layout describe -l 'レイアウト名'     # フィールド型・属性

    使用例:
      # 単一条件で検索
      fmcli record find --layout Contacts -q '{"Name": "田中"}'

      # 複数条件 (OR 検索)
      fmcli record find --layout Contacts -q '[{"Name": "田中"}, {"Name": "鈴木"}]'

      # 出力フィールドを絞り込み
      fmcli record find --layout Contacts -q '{"Name": "田中"}' --fields "Name,Email"

      # 最初の 1 件だけ取得
      fmcli record find --layout Contacts -q '{"Name": "田中"}' --first

      # 件数だけ確認 (レコードデータなし)
      fmcli record find --layout Contacts -q '{"Name": "田中"}' --count

      # フィールドスキーマ付きで検索 (AI エージェント向け)
      fmcli record find --layout Contacts -q '{"Name": "田中"}' --with-schema

      # ファイルから検索条件を読み込み
      fmcli record find --layout Contacts --query-file query.json

      # ポータルデータを含めて検索
      fmcli record find --layout Contacts -q '{"Name": "田中"}' --portal "Orders:5"

      # dry-run でリクエスト内容だけ確認
      fmcli record find --layout Contacts -q '{"Name": "田中"}' --dry-run
    """
    _validate_script_options(script, script_presort, script_prerequest, allow_scripts)
    prof = get_profile(host, database, allow_insecure_http)

    effective_limit = 1 if first else limit

    if dry_run:
        envelope = explain_service.dry_run_find(
            prof,
            layout,
            query=query,
            query_file=query_file,
            offset=offset,
            limit=effective_limit,
            sort=sort,
            fields=fields,
            portal=portal,
            script=script,
            script_presort=script_presort,
            script_prerequest=script_prerequest,
        )
    else:
        envelope = record_service.find_records(
            prof,
            layout,
            query=query,
            query_file=query_file,
            offset=offset,
            limit=effective_limit,
            sort=sort,
            fields=fields,
            count_only=count,
            portal=portal,
            script=script,
            script_presort=script_presort,
            script_prerequest=script_prerequest,
        )

        if with_schema:
            schema_envelope = explain_service.schema_find(prof, layout)
            if schema_envelope.ok:
                envelope.data = {
                    "records": envelope.data,
                    "schema": schema_envelope.data,
                }
            else:
                envelope.messages.append(
                    "--with-schema が指定されましたが、"
                    "スキーマの取得に失敗しました。"
                    "スキーマは出力に含まれません。"
                )

    print_output(envelope)


@app.command()
@handle_errors("record create")
def create(
    layout: Layout = ...,  # type: ignore[assignment]
    field_data: str | None = typer.Option(
        None,
        "--field-data",
        help='フィールドデータ JSON (例: \'{"Name":"田中"}\')',
        rich_help_panel=_PANEL_WRITE,
    ),
    field_data_file: str | None = typer.Option(
        None,
        "--field-data-file",
        "-f",
        help="フィールドデータ JSON ファイル (--field-data の代替)",
        rich_help_panel=_PANEL_WRITE,
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="確認プロンプトをスキップする",
        rich_help_panel=_PANEL_WRITE,
    ),
    skip_field_check: bool = typer.Option(
        False,
        "--skip-field-check",
        help="フィールド名の事前検証をスキップする",
        rich_help_panel=_PANEL_WRITE,
    ),
    script: Script = None,
    script_presort: ScriptPresort = None,
    script_prerequest: ScriptPrerequest = None,
    dry_run: bool = typer.Option(
        False, "--dry-run", help="実行せずリクエスト内容を表示", rich_help_panel=_PANEL_OTHER
    ),
    host: HostWithPanel = None,
    database: DatabaseWithPanel = None,
    allow_scripts: AllowScripts = False,
    allow_insecure_http: AllowInsecureHttp = False,
) -> None:
    """レコードを作成する.

    \b
    ⚠ 書き込み操作です。デフォルトで確認プロンプトが表示されます。
    非対話環境 (パイプ等) では --yes フラグが必須です。

    作成前にフィールド名がレイアウトに存在するか自動検証します。
    検証をスキップするには --skip-field-check を指定してください。

    ヒント: 作成前にフィールド名・型を確認してください。
      fmcli schema find-schema -l 'レイアウト名'  # フィールド一覧
      fmcli layout describe -l 'レイアウト名'     # フィールド型・属性

    使用例:
      # 基本的なレコード作成
      fmcli record create -l Contacts \\
        --field-data '{"Name":"田中","Email":"tanaka@example.com"}' --yes

      # ファイルからフィールドデータを読み込み
      fmcli record create -l Contacts --field-data-file data.json --yes

      # dry-run でリクエスト内容だけ確認
      fmcli record create -l Contacts --field-data '{"Name":"田中"}' --dry-run

      # 確認プロンプト付き (デフォルト)
      fmcli record create -l Contacts --field-data '{"Name":"田中"}'
    """
    _validate_script_options(script, script_presort, script_prerequest, allow_scripts)
    prof = get_profile(host, database, allow_insecure_http)

    # field_data を一度だけ解決（確認・検証・送信すべてで同一の dict を使う）
    from fmcli.services.query_utils import resolve_field_data

    resolved = resolve_field_data(field_data, field_data_file)

    if dry_run:
        envelope = explain_service.dry_run_create(
            prof,
            layout,
            field_data=resolved,
            script=script,
            script_presort=script_presort,
            script_prerequest=script_prerequest,
        )
    else:
        # フィールド名の事前検証（dry-run 時は API を呼ばない）
        if not skip_field_check and resolved:
            unknown = record_service.validate_field_names(prof, layout, resolved)
            if unknown:
                names = ", ".join(unknown)
                raise typer.BadParameter(
                    f"レイアウト '{layout}' に存在しないフィールドがあります: {names}"
                    f"\nフィールド一覧: `fmcli schema find-schema -l '{layout}'`"
                    f"\n検証をスキップするには --skip-field-check を指定してください。"
                )

        _confirm_write(layout, json.dumps(resolved, ensure_ascii=False), yes=yes)

        envelope = record_service.create_record(
            prof,
            layout,
            field_data=resolved,
            script=script,
            script_presort=script_presort,
            script_prerequest=script_prerequest,
        )
    print_output(envelope)


@app.command()
@handle_errors("record update")
def update(
    record_id: int = typer.Argument(..., help="更新対象のレコード ID"),
    layout: Layout = ...,  # type: ignore[assignment]
    field_data: str | None = typer.Option(
        None,
        "--field-data",
        help='更新フィールドデータ JSON (例: \'{"Status":"完了"}\')',
        rich_help_panel=_PANEL_WRITE,
    ),
    field_data_file: str | None = typer.Option(
        None,
        "--field-data-file",
        "-f",
        help="更新フィールドデータ JSON ファイル",
        rich_help_panel=_PANEL_WRITE,
    ),
    mod_id: str = typer.Option(
        ...,
        "--mod-id",
        help="楽観的ロック用 modId (record get/find で取得)",
        rich_help_panel=_PANEL_WRITE,
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="確認プロンプトをスキップする",
        rich_help_panel=_PANEL_WRITE,
    ),
    no_backup: bool = typer.Option(
        False,
        "--no-backup",
        help="undo 情報の自動保存をスキップする",
        rich_help_panel=_PANEL_WRITE,
    ),
    skip_field_check: bool = typer.Option(
        False,
        "--skip-field-check",
        help="フィールド名の事前検証をスキップする",
        rich_help_panel=_PANEL_WRITE,
    ),
    script: Script = None,
    script_presort: ScriptPresort = None,
    script_prerequest: ScriptPrerequest = None,
    dry_run: bool = typer.Option(
        False, "--dry-run", help="実行せずリクエスト内容を表示", rich_help_panel=_PANEL_OTHER
    ),
    host: HostWithPanel = None,
    database: DatabaseWithPanel = None,
    allow_scripts: AllowScripts = False,
    allow_insecure_http: AllowInsecureHttp = False,
) -> None:
    """レコードを更新する.

    \b
    ⚠ 書き込み操作です。--mod-id が必須です（楽観的ロック）。
    事前に record get / record find で modId を確認してください。
    非対話環境 (パイプ等) では --yes フラグが必須です。

    更新前にフィールド名の自動検証と、現在のレコード状態との diff 表示を行います。
    更新成功時は undo 情報が自動保存されます (--no-backup でスキップ可)。

    ヒント: 更新前にレコードと modId を確認してください。
      fmcli record get <ID> -l 'レイアウト名'
      fmcli schema find-schema -l 'レイアウト名'

    使用例:
      # 基本的なレコード更新
      fmcli record update 123 -l Contacts \\
        --field-data '{"Status":"完了"}' --mod-id 5 --yes

      # ファイルから更新データを読み込み
      fmcli record update 123 -l Contacts \\
        -f changes.json --mod-id 5 --yes

      # dry-run でリクエスト内容だけ確認
      fmcli record update 123 -l Contacts \\
        --field-data '{"Status":"完了"}' --mod-id 5 --dry-run
    """
    _validate_script_options(script, script_presort, script_prerequest, allow_scripts)
    prof = get_profile(host, database, allow_insecure_http)

    from fmcli.services.query_utils import resolve_field_data

    resolved = resolve_field_data(field_data, field_data_file)

    if not resolved:
        raise typer.BadParameter(
            "更新するフィールドが指定されていません。--field-data に値を指定してください。"
        )

    if dry_run:
        envelope = explain_service.dry_run_update(
            prof,
            layout,
            record_id,
            field_data=resolved,
            mod_id=mod_id,
            script=script,
            script_presort=script_presort,
            script_prerequest=script_prerequest,
        )
    else:
        # フィールド名の事前検証
        if not skip_field_check and resolved:
            unknown = record_service.validate_field_names(prof, layout, resolved)
            if unknown:
                names = ", ".join(unknown)
                raise typer.BadParameter(
                    f"レイアウト '{layout}' に存在しないフィールドがあります: {names}"
                    f"\nフィールド一覧: `fmcli schema find-schema -l '{layout}'`"
                    f"\n検証をスキップするには --skip-field-check を指定してください。"
                )

        # 事前 get で現在の値を取得し diff 表示
        current = record_service.fetch_record_for_update(prof, layout, record_id)
        current_field_data = current.get("fieldData", {})
        _confirm_update(layout, record_id, resolved, current_field_data, yes=yes)

        envelope = record_service.update_record(
            prof,
            layout,
            record_id,
            field_data=resolved,
            mod_id=mod_id,
            prefetched_record=current,
            no_backup=no_backup,
            script=script,
            script_presort=script_presort,
            script_prerequest=script_prerequest,
        )
    print_output(envelope)


@app.command()
@handle_errors("record upload")
def upload(
    record_id: int = typer.Argument(..., help="対象レコード ID"),
    layout: Layout = ...,  # type: ignore[assignment]
    field: str = typer.Option(
        ...,
        "--field",
        help="コンテナフィールド名",
        rich_help_panel=_PANEL_WRITE,
    ),
    file: str = typer.Option(
        ...,
        "--file",
        help="アップロードするファイルのパス",
        rich_help_panel=_PANEL_WRITE,
    ),
    repetition: int = typer.Option(
        1,
        "--repetition",
        help="フィールドの繰り返し番号 (デフォルト: 1)",
        min=1,
        rich_help_panel=_PANEL_WRITE,
    ),
    if_mod_id: str | None = typer.Option(
        None,
        "--if-mod-id",
        help="事前 modId 検証 (不一致なら中止)",
        rich_help_panel=_PANEL_WRITE,
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="確認プロンプトをスキップする",
        rich_help_panel=_PANEL_WRITE,
    ),
    skip_field_check: bool = typer.Option(
        False,
        "--skip-field-check",
        help="コンテナフィールド型の事前検証をスキップする",
        rich_help_panel=_PANEL_WRITE,
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="実行せずリクエスト内容を表示", rich_help_panel=_PANEL_OTHER
    ),
    host: HostWithPanel = None,
    database: DatabaseWithPanel = None,
    allow_insecure_http: AllowInsecureHttp = False,
) -> None:
    """コンテナフィールドにファイルをアップロードする.

    \b
    ⚠ 書き込み操作です。既存のコンテナデータは上書きされます。
    非対話環境 (パイプ等) では --yes フラグが必須です。

    コンテナフィールド型かどうか自動検証します。
    検証をスキップするには --skip-field-check を指定してください。

    使用例:
      # 基本的なファイルアップロード
      fmcli record upload 123 -l Contacts --field Photo --file ./avatar.jpg --yes

      # 繰り返しフィールドの 2 番目に指定
      fmcli record upload 123 -l Contacts --field Photo --file ./avatar.jpg \\
        --repetition 2 --yes

      # modId による事前検証付き
      fmcli record upload 123 -l Contacts --field Photo --file ./avatar.jpg \\
        --if-mod-id 7 --yes

      # dry-run でリクエスト内容だけ確認
      fmcli record upload 123 -l Contacts --field Photo --file ./avatar.jpg --dry-run
    """
    prof = get_profile(host, database, allow_insecure_http)

    # ローカルファイルの検証（TOCTOU を避けるため try/except でまとめる）
    file_path = Path(file)
    if not file_path.is_file():
        if not file_path.exists():
            raise typer.BadParameter(f"ファイルが見つかりません: {file}")
        raise typer.BadParameter(f"通常のファイルではありません: {file}")
    try:
        file_size = file_path.stat().st_size
    except PermissionError:
        raise typer.BadParameter(f"ファイルを読み取れません: {file}") from None
    file_name = file_path.name
    mime_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"

    if dry_run:
        envelope = explain_service.dry_run_upload(
            prof,
            layout,
            record_id,
            field_name=field,
            file_path=str(file_path),
            file_name=file_name,
            file_size=file_size,
            mime_type=mime_type,
            repetition=repetition,
        )
    else:
        # コンテナフィールド型の事前検証
        if not skip_field_check:
            is_container = record_service.validate_container_field(prof, layout, field)
            if not is_container:
                raise typer.BadParameter(
                    f"フィールド '{field}' はコンテナ型ではありません。"
                    f"\nフィールド型を確認: `fmcli layout describe -l '{layout}'`"
                    f"\n検証をスキップするには --skip-field-check を指定してください。"
                )

        _confirm_upload(layout, record_id, field, str(file_path), file_size, yes=yes)

        envelope = record_service.upload_container(
            prof,
            layout,
            record_id,
            field_name=field,
            file_path=str(file_path),
            file_name=file_name,
            mime_type=mime_type,
            repetition=repetition,
            if_mod_id=if_mod_id,
        )
    print_output(envelope)
