"""metadata コマンドのインテグレーションテスト.

host info, layout list/describe, script list を検証。
"""

from __future__ import annotations

import respx
from syrupy.assertion import SnapshotAssertion
from typer.testing import CliRunner

from fmcli.main import app

from .conftest import (
    FMDATA_BASE,
    PROFILE_ARGS,
    make_fm_response,
    parse_json_output,
    sanitize_output,
)


class TestHostInfo:
    """host info コマンド."""

    def test_host_info(
        self,
        runner: CliRunner,
        setup_session: object,
        respx_mock: respx.MockRouter,
        snapshot: SnapshotAssertion,
    ) -> None:
        """ホスト情報を取得できる."""
        product_info = {
            "productInfo": {
                "name": "FileMaker",
                "buildDate": "03/27/2024",
                "version": "21.0.1.53",
                "dateFormat": "MM/dd/yyyy",
                "timeFormat": "HH:mm:ss",
                "timeStampFormat": "MM/dd/yyyy HH:mm:ss",
            }
        }
        respx_mock.get(url__regex=rf".*{FMDATA_BASE}/productInfo").respond(
            200, json=make_fm_response(product_info)
        )

        result = runner.invoke(app, ["host", "info", *PROFILE_ARGS])

        assert result.exit_code == 0
        data = parse_json_output(result.stdout)
        assert data["ok"] is True
        assert sanitize_output(result.stdout) == snapshot


class TestLayoutList:
    """layout list コマンド."""

    def test_layout_list(
        self,
        runner: CliRunner,
        setup_session: object,
        respx_mock: respx.MockRouter,
        snapshot: SnapshotAssertion,
    ) -> None:
        """レイアウト一覧を取得できる."""
        layouts = {
            "layouts": [
                {"name": "Customers"},
                {"name": "Events"},
                {"name": "Reports"},
            ]
        }
        respx_mock.get(url__regex=rf".*{FMDATA_BASE}/databases/.*/layouts$").respond(
            200, json=make_fm_response(layouts)
        )

        result = runner.invoke(app, ["layout", "list", *PROFILE_ARGS])

        assert result.exit_code == 0
        data = parse_json_output(result.stdout)
        assert data["ok"] is True
        assert len(data["data"]) == 3
        assert sanitize_output(result.stdout) == snapshot

    def test_layout_list_with_filter(
        self,
        runner: CliRunner,
        setup_session: object,
        respx_mock: respx.MockRouter,
        snapshot: SnapshotAssertion,
    ) -> None:
        """--filter でレイアウト名をフィルタできる."""
        layouts = {
            "layouts": [
                {"name": "Customers"},
                {"name": "Events"},
                {"name": "Contacts"},
            ]
        }
        respx_mock.get(url__regex=rf".*{FMDATA_BASE}/databases/.*/layouts$").respond(
            200, json=make_fm_response(layouts)
        )

        result = runner.invoke(app, ["layout", "list", "--filter", "Cust", *PROFILE_ARGS])

        assert result.exit_code == 0
        data = parse_json_output(result.stdout)
        assert data["ok"] is True
        assert len(data["data"]) == 1
        assert all("Cust" in item["name"] for item in data["data"])
        assert sanitize_output(result.stdout) == snapshot


class TestLayoutDescribe:
    """layout describe コマンド."""

    def test_layout_describe(
        self,
        runner: CliRunner,
        setup_session: object,
        respx_mock: respx.MockRouter,
        snapshot: SnapshotAssertion,
    ) -> None:
        """レイアウトメタデータを取得できる."""
        metadata = {
            "fieldMetaData": [
                {
                    "name": "Name",
                    "type": "normal",
                    "displayType": "editText",
                    "result": "text",
                    "global": False,
                    "autoEnter": False,
                    "fourDigitYear": False,
                    "maxRepeat": 1,
                    "maxCharacters": 0,
                    "notEmpty": False,
                    "numeric": False,
                    "repetitions": 1,
                    "timeOfDay": False,
                },
            ],
            "portalMetaData": {},
        }
        respx_mock.get(url__regex=rf".*{FMDATA_BASE}/databases/.*/layouts/[^/]+$").respond(
            200, json=make_fm_response(metadata)
        )

        result = runner.invoke(app, ["layout", "describe", "-l", "TestLayout", *PROFILE_ARGS])

        assert result.exit_code == 0
        data = parse_json_output(result.stdout)
        assert data["ok"] is True
        assert sanitize_output(result.stdout) == snapshot


class TestScriptList:
    """script list コマンド."""

    def test_script_list(
        self,
        runner: CliRunner,
        setup_session: object,
        respx_mock: respx.MockRouter,
        snapshot: SnapshotAssertion,
    ) -> None:
        """スクリプト一覧を取得できる."""
        scripts = {
            "scripts": [
                {"name": "DailyBackup", "isFolder": False},
                {"name": "SendEmail", "isFolder": False},
            ]
        }
        respx_mock.get(url__regex=rf".*{FMDATA_BASE}/databases/.*/scripts").respond(
            200, json=make_fm_response(scripts)
        )

        result = runner.invoke(app, ["script", "list", *PROFILE_ARGS])

        assert result.exit_code == 0
        data = parse_json_output(result.stdout)
        assert data["ok"] is True
        assert sanitize_output(result.stdout) == snapshot
