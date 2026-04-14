"""explain / schema サブコマンド群."""

import typer

from fmcli.cli.common import (
    AllowInsecureHttp,
    Database,
    Host,
    Layout,
    filter_by_keywords,
    get_profile,
)
from fmcli.cli.error_handler import handle_errors
from fmcli.core.output import print_output
from fmcli.services import explain_service

explain_app = typer.Typer(
    no_args_is_help=True,
    help="クエリ説明。サブコマンド: find",
)
schema_app = typer.Typer(
    no_args_is_help=True,
    help="""\b
フィールド情報の確認。サブコマンド: find-schema, output

使用例:
  fmcli schema find-schema -l 'レイアウト名'  # 検索可能フィールド一覧
  fmcli schema output -l 'レイアウト名'       # レイアウトの出力構造
""",
)


@explain_app.command()
@handle_errors("explain find")
def find(
    layout: Layout = ...,  # type: ignore[assignment]
    query: str = typer.Option(
        None, "--query", "-q", help="検索条件 JSON (--query または --query-file が必須)"
    ),
    query_file: str = typer.Option(
        None, "--query-file", "-f", help="検索条件 JSON ファイル (--query の代替)"
    ),
    limit: int = typer.Option(100, "--limit", help="取得件数"),
    offset: int = typer.Option(1, "--offset", help="開始位置"),
    sort: str = typer.Option(None, "--sort", "-s", help="ソート"),
    host: Host = None,
    database: Database = None,
    allow_insecure_http: AllowInsecureHttp = False,
) -> None:
    """find クエリの説明を表示する."""
    prof = get_profile(host, database, allow_insecure_http)
    envelope = explain_service.explain_find(
        prof, layout, query=query, query_file=query_file, offset=offset, limit=limit, sort=sort
    )
    print_output(envelope)


@schema_app.command()
@handle_errors("schema find")
def find_schema(
    layout: Layout = ...,  # type: ignore[assignment]
    filter_text: str | None = typer.Option(
        None,
        "--filter",
        help="フィールド名の絞り込み（部分一致、カンマ区切りで OR 検索）",
    ),
    field_type: str | None = typer.Option(
        None,
        "--type",
        help="フィールド型でフィルタ（例: date, text, number, time, timestamp, container）",
    ),
    host: Host = None,
    database: Database = None,
    allow_insecure_http: AllowInsecureHttp = False,
) -> None:
    """find に使えるフィールド候補を表示する.

    \b
    使用例:
      fmcli schema find-schema -l 'レイアウト名'                  # 全フィールド
      fmcli schema find-schema -l 'レイアウト名' --filter '日付'    # 名前でフィルタ
      fmcli schema find-schema -l 'レイアウト名' --type date       # 型でフィルタ
      fmcli schema find-schema -l 'レイアウト名' --filter '利用' --type text  # 組み合わせ
    """
    prof = get_profile(host, database, allow_insecure_http)
    envelope = explain_service.schema_find(prof, layout)

    # クライアント側フィルタ
    if envelope.ok and isinstance(envelope.data, dict):
        fields = envelope.data.get("findable_fields", [])

        if filter_text:
            fields = filter_by_keywords(fields, "name", filter_text)

        if field_type:
            type_lower = field_type.strip().lower()
            fields = [f for f in fields if f.get("type", "").lower() == type_lower]

        envelope.data["findable_fields"] = fields

    print_output(envelope)


@schema_app.command()
@handle_errors("schema output")
def output(
    layout: Layout = ...,  # type: ignore[assignment]
    host: Host = None,
    database: Database = None,
    allow_insecure_http: AllowInsecureHttp = False,
) -> None:
    """レイアウトの出力構造を表示する."""
    prof = get_profile(host, database, allow_insecure_http)
    envelope = explain_service.schema_output(prof, layout)
    print_output(envelope)
