"""auth CLI のテスト."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from fmcli.cli.auth import _build_login_profile
from fmcli.main import app

runner = CliRunner()


class TestBuildLoginProfile:
    def test_builds_profile_from_host_and_database(self) -> None:
        profile = _build_login_profile(
            host="https://fm.example.com",
            database="MainDB",
            no_verify_ssl=False,
        )
        assert profile.host == "https://fm.example.com"
        assert profile.database == "MainDB"

    def test_no_verify_ssl(self) -> None:
        profile = _build_login_profile(
            host="https://fm.example.com",
            database="DB",
            no_verify_ssl=True,
        )
        assert profile.verify_ssl is False


class TestLoginRequiredOptions:
    """--host と -d が必須であることの回帰テスト."""

    def test_missing_both_host_and_database(self) -> None:
        result = runner.invoke(app, ["auth", "login"])
        assert result.exit_code == 2, result.output

    def test_missing_database(self) -> None:
        result = runner.invoke(app, ["auth", "login", "--host", "https://fm.example.com"])
        assert result.exit_code == 2, result.output

    @pytest.mark.parametrize(
        "args",
        [
            ["auth", "login", "-d", "MyDB"],
        ],
    )
    def test_missing_host(self, args: list[str]) -> None:
        result = runner.invoke(app, args)
        assert result.exit_code == 2, result.output
