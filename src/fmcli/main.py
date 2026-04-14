"""CLI entry point."""

from __future__ import annotations

from importlib.metadata import version as pkg_version
from typing import Annotated

import typer

from fmcli.cli.auth import app as auth_app
from fmcli.cli.config import app as config_app
from fmcli.cli.explain import explain_app, schema_app
from fmcli.cli.metadata import database_app, host_app, layout_app, script_app
from fmcli.cli.profile import app as profile_app
from fmcli.cli.record import app as record_app
from fmcli.core.compat import ensure_utf8_stdio
from fmcli.core.output import OutputConfig, OutputFormat, set_output_config

# --help やパースエラー等、callback 到達前のパスでも UTF-8 を保証する
ensure_utf8_stdio()


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"fmcli {pkg_version('fmcli')}")
        raise typer.Exit()


app = typer.Typer(
    name="fmcli",
    help="""\b
FileMaker Data API read-only CLI wrapper.

使用例:
  fmcli auth config                                      初回セットアップ
  fmcli layout list                                      レイアウト一覧
  fmcli schema find-schema -l 'レイアウト名'             検索可能フィールド確認
  fmcli record find -l 'レイアウト名' -q '{"Name":"田中"}'    レコード検索
  fmcli record list -l 'レイアウト名' --limit 10         レコード一覧
  fmcli layout describe -l 'レイアウト名'                フィールド型・属性
""",
    no_args_is_help=True,
)


@app.callback()
def main_callback(
    verbose: Annotated[
        bool | None,
        typer.Option("--verbose", "-v", help="API 情報・pagination を出力に含める"),
    ] = None,
    format: Annotated[  # noqa: A002
        OutputFormat | None,
        typer.Option("--format", help="出力形式 (json|table)"),
    ] = None,
    timeout: Annotated[
        int | None,
        typer.Option("--timeout", min=1, help="API タイムアウト秒数"),
    ] = None,
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            help="バージョンを表示",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = None,
) -> None:
    """FileMaker Data API read-only CLI wrapper."""
    from fmcli.core.log import setup_logging

    setup_logging(bool(verbose))
    if timeout is None:
        from fmcli.infra.config_store import config_get_effective

        timeout = config_get_effective("timeout")
    set_output_config(
        OutputConfig(
            verbose=bool(verbose),
            format=format or "json",
            timeout=timeout,
        )
    )


app.add_typer(auth_app, name="auth")
app.add_typer(config_app, name="config")
app.add_typer(profile_app, name="profile")
app.add_typer(host_app, name="host")
app.add_typer(database_app, name="database")
app.add_typer(layout_app, name="layout")
app.add_typer(script_app, name="script")
app.add_typer(record_app, name="record")
app.add_typer(explain_app, name="explain")
app.add_typer(schema_app, name="schema")


if __name__ == "__main__":
    app()
