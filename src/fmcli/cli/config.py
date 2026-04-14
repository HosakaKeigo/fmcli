"""config サブコマンド群."""

from __future__ import annotations

from typing import Annotated

import typer

from fmcli.cli.error_handler import handle_errors
from fmcli.core.output import print_output
from fmcli.domain.envelopes import Envelope
from fmcli.infra.config_store import (
    DEFAULTS,
    VALID_KEYS,
    config_get,
    config_list,
    config_set,
    config_unset,
)

app = typer.Typer(
    no_args_is_help=True,
    help="""\b
グローバル設定管理。サブコマンド: set, get, list, unset

使用例:
  fmcli config set timeout 120    # デフォルトタイムアウトを120秒に設定
  fmcli config get timeout        # 現在のタイムアウト設定を表示
  fmcli config list               # 全設定を表示
  fmcli config unset timeout      # タイムアウト設定を削除
""",
)


@app.command(name="set")
@handle_errors("config set")
def set_cmd(
    key: Annotated[str, typer.Argument(help="設定キー")],
    value: Annotated[str, typer.Argument(help="設定値")],
) -> None:
    """設定値を保存する."""
    converted = config_set(key, value)
    print_output(
        Envelope(
            ok=True,
            command="config set",
            data={"key": key, "value": converted},
            messages=[f"{key} = {converted}"],
        )
    )


@app.command(name="get")
@handle_errors("config get")
def get_cmd(
    key: Annotated[str, typer.Argument(help="設定キー")],
) -> None:
    """設定値を表示する."""
    value = config_get(key)
    if value is None:
        effective = DEFAULTS.get(key)
        print_output(
            Envelope(
                ok=True,
                command="config get",
                data={"key": key, "value": None, "effective": effective},
                messages=[f"{key}: 未設定 (デフォルト: {effective})"],
            )
        )
    else:
        print_output(
            Envelope(
                ok=True,
                command="config get",
                data={"key": key, "value": value},
                messages=[f"{key} = {value}"],
            )
        )


@app.command(name="list")
@handle_errors("config list")
def list_cmd() -> None:
    """全設定を表示する."""
    data = config_list()
    entries = []
    for key, description in VALID_KEYS.items():
        value = data.get(key)
        entries.append(
            {
                "key": key,
                "value": value,
                "default": DEFAULTS.get(key),
                "description": description,
            }
        )
    print_output(Envelope(ok=True, command="config list", data=entries))


@app.command(name="unset")
@handle_errors("config unset")
def unset_cmd(
    key: Annotated[str, typer.Argument(help="設定キー")],
) -> None:
    """設定を削除してデフォルト値に戻す."""
    removed = config_unset(key)
    if removed:
        print_output(
            Envelope(
                ok=True,
                command="config unset",
                data={"key": key, "removed": True},
                messages=[f"{key} を削除しました (デフォルト値に戻ります)"],
            )
        )
    else:
        print_output(
            Envelope(
                ok=True,
                command="config unset",
                data={"key": key, "removed": False},
                messages=[f"{key} は設定されていません"],
            )
        )
