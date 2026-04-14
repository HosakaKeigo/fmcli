"""CLI コマンド横断のエラーハンドリング parametrize テスト."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from fmcli.core.errors import (
    EXIT_API,
    EXIT_AUTH,
    EXIT_CONFIG,
    EXIT_NOT_FOUND,
    EXIT_TRANSPORT,
    ApiError,
    AuthError,
    ConfigError,
    NotFoundError,
    TransportError,
)
from fmcli.main import app
from tests.unit.helpers import make_profile

runner = CliRunner()


# ---------------------------------------------------------------------------
# TestResolveProfileErrors
# ---------------------------------------------------------------------------

_COMMANDS_WITH_RESOLVE_PATH = [
    (["host", "info"], "fmcli.cli.metadata.get_profile"),
    (["layout", "list"], "fmcli.cli.metadata.get_profile"),
    (["script", "list"], "fmcli.cli.metadata.get_profile"),
    (["record", "list", "-l", "L"], "fmcli.cli.record.get_profile"),
    (
        ["record", "find", "-l", "L", "-q", '{"a":"b"}'],
        "fmcli.cli.record.get_profile",
    ),
    (["record", "get", "1", "-l", "L"], "fmcli.cli.record.get_profile"),
    (["schema", "find-schema", "-l", "L"], "fmcli.cli.explain.get_profile"),
    (["schema", "output", "-l", "L"], "fmcli.cli.explain.get_profile"),
    (
        ["explain", "find", "-l", "L", "-q", '{"a":"b"}'],
        "fmcli.cli.explain.get_profile",
    ),
]

_RESOLVE_ERRORS = [
    (ConfigError("接続先が特定できません。"), EXIT_CONFIG),
    (AuthError("認証が必要です", error_type="auth_required"), EXIT_AUTH),
]


class TestResolveProfileErrors:
    """resolve_profile が例外を送出した場合、各コマンドが正しい終了コードを返す."""

    @pytest.mark.parametrize("cmd_args,resolve_path", _COMMANDS_WITH_RESOLVE_PATH)
    @pytest.mark.parametrize("error,expected_exit", _RESOLVE_ERRORS)
    def test_resolve_profile_error(
        self,
        cmd_args: list[str],
        resolve_path: str,
        error: Exception,
        expected_exit: int,
    ) -> None:
        with patch(resolve_path, side_effect=error):
            result = runner.invoke(app, cmd_args)
            assert result.exit_code == expected_exit, (
                f"cmd={cmd_args!r}, error={error!r}: "
                f"expected exit {expected_exit}, got {result.exit_code}\n"
                f"output: {result.output}"
            )


# ---------------------------------------------------------------------------
# TestServiceErrors
# ---------------------------------------------------------------------------

_SERVICE_ERRORS = [
    (ApiError("API エラー", http_status=400, api_code=105), EXIT_API),
    (TransportError("接続エラー"), EXIT_TRANSPORT),
    (NotFoundError("見つかりません"), EXIT_NOT_FOUND),
]

_RECORD_SERVICE_COMMANDS = [
    (
        ["record", "list", "-l", "L"],
        "fmcli.services.record_service.list_records",
    ),
    (
        ["record", "find", "-l", "L", "-q", '{"a":"b"}'],
        "fmcli.services.record_service.find_records",
    ),
    (
        ["record", "get", "1", "-l", "L"],
        "fmcli.services.record_service.get_record",
    ),
]

_METADATA_SERVICE_COMMANDS = [
    (["host", "info"], "fmcli.services.metadata_service.host_info"),
    (["layout", "list"], "fmcli.services.metadata_service.layout_list"),
    (["script", "list"], "fmcli.services.metadata_service.script_list"),
]

_EXPLAIN_SERVICE_COMMANDS = [
    (
        ["schema", "find-schema", "-l", "L"],
        "fmcli.services.explain_service.schema_find",
    ),
    (
        ["schema", "output", "-l", "L"],
        "fmcli.services.explain_service.schema_output",
    ),
    (
        ["explain", "find", "-l", "L", "-q", '{"a":"b"}'],
        "fmcli.services.explain_service.explain_find",
    ),
]

_ALL_SERVICE_COMMANDS = (
    _RECORD_SERVICE_COMMANDS + _METADATA_SERVICE_COMMANDS + _EXPLAIN_SERVICE_COMMANDS
)


class TestServiceErrors:
    """サービス層が例外を送出した場合、各コマンドが正しい終了コードを返す."""

    @pytest.mark.parametrize("cmd_args,service_path", _ALL_SERVICE_COMMANDS)
    @pytest.mark.parametrize("error,expected_exit", _SERVICE_ERRORS)
    def test_service_error(
        self,
        cmd_args: list[str],
        service_path: str,
        error: Exception,
        expected_exit: int,
    ) -> None:
        # resolve_profile の module path をコマンドグループから決定
        if cmd_args[0] in ("host", "layout", "script", "database"):
            resolve_path = "fmcli.cli.metadata.get_profile"
        elif cmd_args[0] == "record":
            resolve_path = "fmcli.cli.record.get_profile"
        else:
            resolve_path = "fmcli.cli.explain.get_profile"

        with (
            patch(resolve_path, return_value=make_profile()),
            patch(service_path, side_effect=error),
        ):
            result = runner.invoke(app, cmd_args)
            assert result.exit_code == expected_exit, (
                f"cmd={cmd_args!r}, error={error!r}: "
                f"expected exit {expected_exit}, got {result.exit_code}\n"
                f"output: {result.output}"
            )
