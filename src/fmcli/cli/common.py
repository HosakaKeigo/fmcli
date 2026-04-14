"""CLI 共通オプション定義."""

from __future__ import annotations

from typing import Annotated

import typer

from fmcli.cli.completions import complete_database, complete_host, complete_layout
from fmcli.domain.models import Profile
from fmcli.infra.profile_store import resolve_profile

_PANEL_CONNECTION = "接続"

# --- Plain versions (metadata, explain, auth, profile) ---
Host = Annotated[
    str | None,
    typer.Option("--host", "-h", help="ホスト URL", autocompletion=complete_host),
]
Database = Annotated[
    str | None,
    typer.Option("--database", "-d", help="データベース名", autocompletion=complete_database),
]
# --- Required versions (auth login) ---
HostRequired = Annotated[
    str,
    typer.Option(..., "--host", "-h", help="ホスト URL（必須）", autocompletion=complete_host),
]
DatabaseRequired = Annotated[
    str,
    typer.Option(
        ..., "--database", "-d", help="データベース名（必須）", autocompletion=complete_database
    ),
]
AllowInsecureHttp = Annotated[
    bool,
    typer.Option("--allow-insecure-http", help="安全でない HTTP 接続を許可する (非推奨)"),
]
Layout = Annotated[
    str,
    typer.Option(..., "--layout", "-l", help="レイアウト名", autocompletion=complete_layout),
]

# --- With rich_help_panel (record.py) ---
HostWithPanel = Annotated[
    str | None,
    typer.Option(
        "--host",
        "-h",
        help="ホスト URL",
        autocompletion=complete_host,
        rich_help_panel=_PANEL_CONNECTION,
    ),
]
DatabaseWithPanel = Annotated[
    str | None,
    typer.Option(
        "--database",
        "-d",
        help="データベース名",
        autocompletion=complete_database,
        rich_help_panel=_PANEL_CONNECTION,
    ),
]


def get_profile(
    host: str | None,
    database: str | None,
    allow_insecure_http: bool = False,
) -> Profile:
    """共通のプロファイル解決ヘルパー."""
    return resolve_profile(host=host, database=database, allow_insecure_http=allow_insecure_http)


def _parse_keywords(keywords_csv: str) -> list[str]:
    """カンマ区切りキーワード文字列をパースして小文字リストにする."""
    return [k.strip().lower() for k in keywords_csv.split(",") if k.strip()]


def _match_keywords(value: str, keywords: list[str]) -> bool:
    """値がいずれかのキーワードに部分一致するか判定."""
    lower = value.lower()
    return any(kw in lower for kw in keywords)


def filter_by_keywords(
    items: list[dict[str, object]], field: str, keywords_csv: str
) -> list[dict[str, object]]:
    """カンマ区切りキーワードによる部分一致フィルタ (OR)."""
    keywords = _parse_keywords(keywords_csv)
    if not keywords:
        return items
    return [
        item
        for item in items
        if isinstance(item, dict) and _match_keywords(str(item.get(field, "")), keywords)
    ]


def filter_layouts_by_keywords(
    items: list[dict[str, object]], keywords_csv: str
) -> list[dict[str, object]]:
    """レイアウト一覧をキーワードフィルタする.

    フォルダの場合、フォルダ名自体に加えて folderLayoutNames 内の
    レイアウト名もマッチ対象にする。フォルダ名がマッチした場合はフォルダ
    ごと残し、子レイアウトのみマッチした場合はマッチした子を通常レイアウト
    としてフラットに展開する（--format table でも正しく表示されるようにする）。
    """
    keywords = _parse_keywords(keywords_csv)
    if not keywords:
        return items

    result: list[dict[str, object]] = []
    for item in items:
        if not isinstance(item, dict):
            continue

        name = str(item.get("name", ""))
        folder_children = item.get("folderLayoutNames")

        # フォルダでない通常レイアウト
        if not isinstance(folder_children, list):
            if _match_keywords(name, keywords):
                result.append(item)
            continue

        # フォルダ名自体がマッチ → フォルダごと残す
        if _match_keywords(name, keywords):
            result.append(item)
            continue

        # 子レイアウト名でマッチするものをフラット展開
        for child in folder_children:
            if isinstance(child, dict) and _match_keywords(str(child.get("name", "")), keywords):
                result.append(child)

    return result
