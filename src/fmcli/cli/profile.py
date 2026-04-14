"""profile サブコマンド群."""

import typer

from fmcli.cli.common import AllowInsecureHttp, Database, Host, get_profile
from fmcli.cli.error_handler import handle_errors
from fmcli.core.output import print_output
from fmcli.domain.envelopes import Envelope
from fmcli.infra.profile_store import list_profiles

app = typer.Typer(
    no_args_is_help=True,
    help="""\b
接続プロファイル管理。サブコマンド: list, show
プロファイルは auth login 時に自動作成されます。

使用例:
  fmcli profile list   # 保存済みプロファイル一覧
  fmcli profile show --host <ホスト> -d <DB>   # プロファイル詳細
""",
)


@app.command(name="list")
@handle_errors("profile list")
def list_cmd() -> None:
    """保存済みプロファイル一覧を表示する."""
    profiles = list_profiles()
    data = []
    for p in profiles:
        entry = p.model_dump()
        entry["profile_key"] = p.profile_key
        data.append(entry)
    print_output(Envelope(ok=True, command="profile list", data=data))


@app.command()
@handle_errors("profile show")
def show(
    host: Host = None,
    database: Database = None,
    allow_insecure_http: AllowInsecureHttp = False,
) -> None:
    """プロファイルの詳細を表示する."""
    prof = get_profile(host, database, allow_insecure_http)
    data = prof.model_dump()
    data["profile_key"] = prof.profile_key
    print_output(Envelope(ok=True, command="profile show", data=data))
