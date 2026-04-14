"""explain / schema コマンドのインテグレーションテスト.

explain find, schema find-schema/output, record list --dry-run を検証。
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


class TestExplainFind:
    """explain find コマンド."""

    def test_explain_find(
        self, runner: CliRunner, setup_session: object, snapshot: SnapshotAssertion
    ) -> None:
        """find クエリの説明を表示できる (HTTP 通信なし)."""
        result = runner.invoke(
            app,
            ["explain", "find", "-l", "TestLayout", "-q", '{"Name":"田中"}', *PROFILE_ARGS],
        )

        assert result.exit_code == 0
        data = parse_json_output(result.stdout)
        assert data["ok"] is True
        # explain は実際の API 呼び出しをせず、リクエスト内容を説明する
        assert "explanation" in data["data"] or "query" in data["data"]
        assert sanitize_output(result.stdout) == snapshot


class TestSchemaFindSchema:
    """schema find-schema コマンド."""

    def test_find_schema(
        self,
        runner: CliRunner,
        setup_session: object,
        respx_mock: respx.MockRouter,
        snapshot: SnapshotAssertion,
    ) -> None:
        """検索可能フィールド一覧を取得できる."""
        metadata = {
            "fieldMetaData": [
                {"name": "Name", "type": "normal", "result": "text"},
                {"name": "Age", "type": "normal", "result": "number"},
                {"name": "Created", "type": "normal", "result": "date"},
            ],
            "portalMetaData": {},
        }
        respx_mock.get(url__regex=rf".*{FMDATA_BASE}/databases/.*/layouts/[^/]+$").respond(
            200, json=make_fm_response(metadata)
        )

        result = runner.invoke(app, ["schema", "find-schema", "-l", "TestLayout", *PROFILE_ARGS])

        assert result.exit_code == 0
        data = parse_json_output(result.stdout)
        assert data["ok"] is True
        assert "findable_fields" in data["data"]
        assert sanitize_output(result.stdout) == snapshot

    def test_find_schema_with_filter(
        self, runner: CliRunner, setup_session: object, respx_mock: respx.MockRouter
    ) -> None:
        """--filter でフィールド名をフィルタできる."""
        metadata = {
            "fieldMetaData": [
                {"name": "Name", "type": "normal", "result": "text"},
                {"name": "NameKana", "type": "normal", "result": "text"},
                {"name": "Age", "type": "normal", "result": "number"},
            ],
            "portalMetaData": {},
        }
        respx_mock.get(url__regex=rf".*{FMDATA_BASE}/databases/.*/layouts/[^/]+$").respond(
            200, json=make_fm_response(metadata)
        )

        result = runner.invoke(
            app,
            ["schema", "find-schema", "-l", "TestLayout", "--filter", "Name", *PROFILE_ARGS],
        )

        assert result.exit_code == 0
        data = parse_json_output(result.stdout)
        assert data["ok"] is True
        fields = data["data"]["findable_fields"]
        assert all("name" in f["name"] or "Name" in f["name"] for f in fields)

    def test_find_schema_with_type_filter(
        self,
        runner: CliRunner,
        setup_session: object,
        respx_mock: respx.MockRouter,
        snapshot: SnapshotAssertion,
    ) -> None:
        """--type でフィールド型をフィルタできる."""
        metadata = {
            "fieldMetaData": [
                {"name": "Name", "type": "normal", "result": "text"},
                {"name": "Birthday", "type": "normal", "result": "date"},
            ],
            "portalMetaData": {},
        }
        respx_mock.get(url__regex=rf".*{FMDATA_BASE}/databases/.*/layouts/[^/]+$").respond(
            200, json=make_fm_response(metadata)
        )

        result = runner.invoke(
            app,
            ["schema", "find-schema", "-l", "TestLayout", "--type", "date", *PROFILE_ARGS],
        )

        assert result.exit_code == 0
        data = parse_json_output(result.stdout)
        fields = data["data"]["findable_fields"]
        assert len(fields) == 1
        assert fields[0]["name"] == "Birthday"
        assert sanitize_output(result.stdout) == snapshot


class TestSchemaOutput:
    """schema output コマンド."""

    def test_schema_output(
        self,
        runner: CliRunner,
        setup_session: object,
        respx_mock: respx.MockRouter,
        snapshot: SnapshotAssertion,
    ) -> None:
        """レイアウト出力構造を表示できる."""
        metadata = {
            "fieldMetaData": [
                {"name": "Name", "type": "normal", "result": "text"},
            ],
            "portalMetaData": {
                "RelatedItems": [
                    {"name": "RelatedItems::Item", "type": "normal", "result": "text"},
                ]
            },
        }
        respx_mock.get(url__regex=rf".*{FMDATA_BASE}/databases/.*/layouts/[^/]+$").respond(
            200, json=make_fm_response(metadata)
        )

        result = runner.invoke(app, ["schema", "output", "-l", "TestLayout", *PROFILE_ARGS])

        assert result.exit_code == 0
        data = parse_json_output(result.stdout)
        assert data["ok"] is True
        assert sanitize_output(result.stdout) == snapshot


class TestDryRun:
    """--dry-run フラグのインテグレーションテスト."""

    def test_record_list_dry_run(
        self, runner: CliRunner, setup_session: object, snapshot: SnapshotAssertion
    ) -> None:
        """record list --dry-run は HTTP 通信なしでリクエスト内容を返す."""
        result = runner.invoke(
            app,
            ["record", "list", "-l", "TestLayout", "--limit", "5", "--dry-run", *PROFILE_ARGS],
        )

        assert result.exit_code == 0
        data = parse_json_output(result.stdout)
        assert data["ok"] is True
        # dry-run はリクエスト情報を含む
        assert "request" in data["data"] or "method" in str(data["data"])
        assert sanitize_output(result.stdout) == snapshot

    def test_record_find_dry_run(
        self, runner: CliRunner, setup_session: object, snapshot: SnapshotAssertion
    ) -> None:
        """record find --dry-run は HTTP 通信なしでリクエスト内容を返す."""
        result = runner.invoke(
            app,
            [
                "record",
                "find",
                "-l",
                "TestLayout",
                "-q",
                '{"Name":"田中"}',
                "--dry-run",
                *PROFILE_ARGS,
            ],
        )

        assert result.exit_code == 0
        data = parse_json_output(result.stdout)
        assert data["ok"] is True
        assert sanitize_output(result.stdout) == snapshot
