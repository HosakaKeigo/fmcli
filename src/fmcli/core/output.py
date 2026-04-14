"""出力ヘルパー."""

from __future__ import annotations

import sys
from contextvars import ContextVar
from dataclasses import dataclass, replace
from typing import Any, Literal

from fmcli.domain.envelopes import Envelope

OutputFormat = Literal["json", "table"]


DEFAULT_TIMEOUT: int = 60


@dataclass(frozen=True)
class OutputConfig:
    """出力設定."""

    verbose: bool = False
    format: OutputFormat = "json"
    timeout: int = DEFAULT_TIMEOUT


_DEFAULT_OUTPUT_CONFIG = OutputConfig()

_output_config_var: ContextVar[OutputConfig] = ContextVar("output_config")


def get_output_config() -> OutputConfig:
    """現在の OutputConfig を返す."""
    return _output_config_var.get(_DEFAULT_OUTPUT_CONFIG)


def set_output_config(config: OutputConfig) -> None:
    """OutputConfig を設定する."""
    _output_config_var.set(config)


def set_verbose(verbose: bool) -> None:
    """verbose モードを設定する（後方互換）."""
    cfg = _output_config_var.get(_DEFAULT_OUTPUT_CONFIG)
    _output_config_var.set(replace(cfg, verbose=verbose))


def is_verbose() -> bool:
    """verbose モードかどうかを返す."""
    return _output_config_var.get(_DEFAULT_OUTPUT_CONFIG).verbose


def set_format(fmt: OutputFormat) -> None:
    """出力形式を設定する（後方互換）."""
    cfg = _output_config_var.get(_DEFAULT_OUTPUT_CONFIG)
    _output_config_var.set(replace(cfg, format=fmt))


def get_format() -> OutputFormat:
    """現在の出力形式を返す."""
    return _output_config_var.get(_DEFAULT_OUTPUT_CONFIG).format


def get_timeout() -> int:
    """現在の timeout 値を返す."""
    return _output_config_var.get(_DEFAULT_OUTPUT_CONFIG).timeout


def render_json(envelope: Envelope) -> str:
    """Envelope を JSON 文字列にレンダリングする."""
    cfg = _output_config_var.get(_DEFAULT_OUTPUT_CONFIG)
    exclude: set[str] | None = None
    if not cfg.verbose:
        exclude = {"api", "pagination"}
    return envelope.model_dump_json(indent=2, exclude_none=True, exclude=exclude)


def print_json(envelope: Envelope) -> None:
    """Envelope を標準出力に JSON で出力する."""
    sys.stdout.write(render_json(envelope) + "\n")


def print_output(envelope: Envelope) -> None:
    """format に応じて出力する."""
    cfg = _output_config_var.get(_DEFAULT_OUTPUT_CONFIG)
    if cfg.format == "table" and _can_render_table(envelope):
        _print_table(envelope)
        _print_messages(envelope)
    else:
        print_json(envelope)


def _can_render_table(envelope: Envelope) -> bool:
    """テーブル表示可能か判定."""
    return envelope.ok and isinstance(envelope.data, list)


def _has_portal_data(rows: list[Any]) -> bool:
    """レコード群に portalData が含まれるか判定する."""
    return any(isinstance(r, dict) and r.get("portalData") for r in rows)


def _flatten_record(row: dict[str, Any]) -> dict[str, Any]:
    """FileMaker レコードを平坦な dict に変換する.

    fieldData キーがあれば展開し、recordId / modId を先頭に含める。
    portalData がある場合はテーブル化せず JSON フォールバックする想定のため、
    呼び出し前に _has_portal_data() でチェックすること。
    """
    if "fieldData" not in row:
        return row

    flat: dict[str, Any] = {}
    if "recordId" in row:
        flat["recordId"] = row["recordId"]
    if "modId" in row:
        flat["modId"] = row["modId"]
    field_data = row["fieldData"]
    if isinstance(field_data, dict):
        flat.update(field_data)
    return flat


def _print_messages(envelope: Envelope) -> None:
    """Envelope のメッセージを標準エラー出力に表示する."""
    if not envelope.messages:
        return
    from rich.console import Console

    console = Console(stderr=True)
    for msg in envelope.messages:
        console.print(f"[yellow]⚠ {msg}[/yellow]")


def _print_table(envelope: Envelope) -> None:
    """Envelope の data をテーブル表示する."""
    from rich.console import Console
    from rich.table import Table

    data = envelope.data
    if not data:
        print_json(envelope)
        return

    # portalData を含むレコードはテーブル化に不向きなので JSON にフォールバック
    if _has_portal_data(data):
        print_json(envelope)
        return

    # カラム推定: data[0] の構造から
    first = data[0]
    if isinstance(first, dict):
        # FileMaker レコード構造のフラット化
        flat_data = [_flatten_record(row) for row in data if isinstance(row, dict)]
        if not flat_data:
            print_json(envelope)
            return
        columns = list(flat_data[0].keys())
    else:
        print_json(envelope)
        return

    table = Table(title=envelope.command or "")
    for col in columns:
        table.add_column(col)

    for row in flat_data:
        table.add_row(*[str(row.get(c, "")) for c in columns])

    console = Console()
    console.print(table)
