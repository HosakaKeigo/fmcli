"""record コマンドのインテグレーションテスト.

CLI → record_service → session_helper → FileMakerAPI → HttpClient → HTTP の全レイヤーを通す。
HTTP は respx でモック。
"""

from __future__ import annotations

import httpx
import respx
from syrupy.assertion import SnapshotAssertion
from typer.testing import CliRunner

from fmcli.main import app

from .conftest import (
    FMDATA_BASE,
    PROFILE_ARGS,
    make_fm_response,
    make_record,
    make_records_response,
    parse_json_output,
    sanitize_output,
)


class TestRecordGet:
    """record get コマンド."""

    def test_get_record(
        self,
        runner: CliRunner,
        setup_session: object,
        respx_mock: respx.MockRouter,
        snapshot: SnapshotAssertion,
    ) -> None:
        """単一レコードを取得できる."""
        record = make_record("42", {"Name": "田中太郎", "Email": "tanaka@example.com"})
        respx_mock.get(url__regex=rf".*{FMDATA_BASE}/databases/.*/layouts/.*/records/42").respond(
            200, json=make_fm_response({"data": [record]})
        )

        result = runner.invoke(app, ["record", "get", "42", "-l", "TestLayout", *PROFILE_ARGS])

        assert result.exit_code == 0
        data = parse_json_output(result.stdout)
        assert data["ok"] is True
        # get_record は単一レコードを返す（リストではない）
        assert data["data"]["fieldData"]["Name"] == "田中太郎"
        assert sanitize_output(result.stdout) == snapshot

    def test_get_record_with_fields(
        self, runner: CliRunner, setup_session: object, respx_mock: respx.MockRouter
    ) -> None:
        """--fields でクライアント側フィールドフィルタが効く."""
        record = make_record("1", {"Name": "鈴木", "Email": "suzuki@example.com", "Age": "30"})
        respx_mock.get(url__regex=rf".*{FMDATA_BASE}/databases/.*/layouts/.*/records/1").respond(
            200, json=make_fm_response({"data": [record]})
        )

        result = runner.invoke(
            app,
            ["record", "get", "1", "-l", "TestLayout", "--fields", "Name", *PROFILE_ARGS],
        )

        assert result.exit_code == 0
        data = parse_json_output(result.stdout)
        assert data["ok"] is True
        fields = data["data"]["fieldData"]
        assert "Name" in fields
        assert "Email" not in fields
        assert "Age" not in fields


class TestRecordList:
    """record list コマンド."""

    def test_list_records(
        self,
        runner: CliRunner,
        setup_session: object,
        respx_mock: respx.MockRouter,
        snapshot: SnapshotAssertion,
    ) -> None:
        """レコード一覧を取得できる."""
        records = [
            make_record("1", {"Name": "田中"}),
            make_record("2", {"Name": "鈴木"}),
        ]
        respx_mock.get(url__regex=rf".*{FMDATA_BASE}/databases/.*/layouts/.*/records").respond(
            200, json=make_records_response(records, total_count=2)
        )

        result = runner.invoke(
            app, ["record", "list", "-l", "TestLayout", "--limit", "10", *PROFILE_ARGS]
        )

        assert result.exit_code == 0
        data = parse_json_output(result.stdout)
        assert data["ok"] is True
        assert len(data["data"]) == 2
        assert sanitize_output(result.stdout) == snapshot

    def test_list_records_with_sort(
        self, runner: CliRunner, setup_session: object, respx_mock: respx.MockRouter
    ) -> None:
        """--sort オプションでソートパラメータが送信される."""
        records = [make_record("1", {"Name": "A"})]

        route = respx_mock.get(
            url__regex=rf".*{FMDATA_BASE}/databases/.*/layouts/.*/records"
        ).respond(200, json=make_records_response(records))

        result = runner.invoke(
            app,
            ["record", "list", "-l", "TestLayout", "--sort", "Name:ascend", *PROFILE_ARGS],
        )

        assert result.exit_code == 0
        # _sort パラメータがリクエストに含まれることを検証
        request = route.calls.last.request
        assert "_sort" in str(request.url)


class TestRecordFind:
    """record find コマンド."""

    def test_find_records(
        self,
        runner: CliRunner,
        setup_session: object,
        respx_mock: respx.MockRouter,
        snapshot: SnapshotAssertion,
    ) -> None:
        """レコード検索が正常に動作する."""
        records = [make_record("10", {"Name": "田中", "City": "東京"})]
        respx_mock.post(url__regex=rf".*{FMDATA_BASE}/databases/.*/layouts/.*/_find").respond(
            200, json=make_records_response(records)
        )

        result = runner.invoke(
            app,
            ["record", "find", "-l", "TestLayout", "-q", '{"Name":"田中"}', *PROFILE_ARGS],
        )

        assert result.exit_code == 0
        data = parse_json_output(result.stdout)
        assert data["ok"] is True
        assert data["data"][0]["fieldData"]["Name"] == "田中"
        assert sanitize_output(result.stdout) == snapshot

    def test_find_with_count(
        self,
        runner: CliRunner,
        setup_session: object,
        respx_mock: respx.MockRouter,
        snapshot: SnapshotAssertion,
    ) -> None:
        """--count で件数のみ返す."""
        records = [make_record("1", {"Name": "A"}), make_record("2", {"Name": "B"})]
        respx_mock.post(url__regex=rf".*{FMDATA_BASE}/databases/.*/layouts/.*/_find").respond(
            200, json=make_records_response(records, total_count=100)
        )

        result = runner.invoke(
            app,
            [
                "record",
                "find",
                "-l",
                "TestLayout",
                "-q",
                '{"Name":"*"}',
                "--count",
                *PROFILE_ARGS,
            ],
        )

        assert result.exit_code == 0
        data = parse_json_output(result.stdout)
        assert data["ok"] is True
        assert data["data"]["found_count"] == 100
        assert sanitize_output(result.stdout) == snapshot

    def test_find_with_first(
        self, runner: CliRunner, setup_session: object, respx_mock: respx.MockRouter
    ) -> None:
        """--first で最初の 1 件だけ返す."""
        records = [make_record("1", {"Name": "田中"})]
        route = respx_mock.post(
            url__regex=rf".*{FMDATA_BASE}/databases/.*/layouts/.*/_find"
        ).respond(200, json=make_records_response(records))

        result = runner.invoke(
            app,
            [
                "record",
                "find",
                "-l",
                "TestLayout",
                "-q",
                '{"Name":"田中"}',
                "--first",
                *PROFILE_ARGS,
            ],
        )

        assert result.exit_code == 0
        # --first は limit=1 でリクエスト
        request = route.calls.last.request
        import json

        body = json.loads(request.content)
        assert body["limit"] == "1"

    def test_find_with_fields_filter(
        self, runner: CliRunner, setup_session: object, respx_mock: respx.MockRouter
    ) -> None:
        """--fields でクライアント側フィールドフィルタが効く."""
        records = [make_record("1", {"Name": "田中", "Email": "t@example.com", "Phone": "090"})]
        respx_mock.post(url__regex=rf".*{FMDATA_BASE}/databases/.*/layouts/.*/_find").respond(
            200, json=make_records_response(records)
        )

        result = runner.invoke(
            app,
            [
                "record",
                "find",
                "-l",
                "TestLayout",
                "-q",
                '{"Name":"田中"}',
                "--fields",
                "Name,Email",
                *PROFILE_ARGS,
            ],
        )

        assert result.exit_code == 0
        data = parse_json_output(result.stdout)
        fields = data["data"][0]["fieldData"]
        assert "Name" in fields
        assert "Email" in fields
        assert "Phone" not in fields


class TestRecordSessionRefresh:
    """セッション自動リフレッシュのインテグレーションテスト."""

    def test_session_refresh_on_401(
        self,
        runner: CliRunner,
        setup_session: object,
        respx_mock: respx.MockRouter,
    ) -> None:
        """401 → 自動再ログイン → リトライの全フローが動作する."""
        from unittest.mock import patch

        # keyring にクレデンシャルを返させる
        credential_json = '{"username": "testuser", "password": "testpass"}'
        with patch("fmcli.infra.auth_store.keyring") as mock_kr:
            mock_kr.get_password.return_value = credential_json
            mock_kr.set_password.return_value = None

            # 1回目: 401 (session expired)
            expired_resp = {
                "messages": [{"code": "952", "message": "Invalid FileMaker Data API token"}],
                "response": {},
            }
            find_route = respx_mock.post(
                url__regex=rf".*{FMDATA_BASE}/databases/.*/layouts/.*/_find"
            ).mock(
                side_effect=[
                    httpx.Response(401, json=expired_resp),
                    httpx.Response(
                        200,
                        json=make_records_response(
                            [make_record("1", {"Name": "田中"})],
                        ),
                    ),
                ]
            )

            # 再ログイン
            respx_mock.post(url__regex=rf".*{FMDATA_BASE}/databases/.*/sessions").respond(
                200, json=make_fm_response({"token": "new-token"})
            )

            result = runner.invoke(
                app,
                [
                    "record",
                    "find",
                    "-l",
                    "TestLayout",
                    "-q",
                    '{"Name":"田中"}',
                    *PROFILE_ARGS,
                ],
            )

            assert result.exit_code == 0
            data = parse_json_output(result.stdout)
            assert data["ok"] is True
            # find が 2 回呼ばれたことを確認（1回目は 401、2回目は成功）
            assert find_route.call_count == 2


class TestRecordApiError:
    """API エラー時のインテグレーションテスト."""

    def test_api_500_error(
        self,
        runner: CliRunner,
        setup_session: object,
        respx_mock: respx.MockRouter,
        snapshot: SnapshotAssertion,
    ) -> None:
        """500 エラー時に適切な exit code とエラー情報が返る."""
        error_resp = {
            "messages": [{"code": "500", "message": "Internal Server Error"}],
            "response": {},
        }
        respx_mock.post(url__regex=rf".*{FMDATA_BASE}/databases/.*/layouts/.*/_find").respond(
            500, json=error_resp
        )

        result = runner.invoke(
            app,
            ["record", "find", "-l", "TestLayout", "-q", '{"Name":"田中"}', *PROFILE_ARGS],
        )

        assert result.exit_code != 0
        # エラー Envelope は stderr に出力される
        data = parse_json_output(result.output)
        assert data["ok"] is False
        assert sanitize_output(result.output) == snapshot

    def test_no_records_match(
        self,
        runner: CliRunner,
        setup_session: object,
        respx_mock: respx.MockRouter,
        snapshot: SnapshotAssertion,
    ) -> None:
        """レコードなし (FM API code 402) の場合でも正常終了する."""
        error_resp = {
            "messages": [{"code": "402", "message": "No records match the request"}],
            "response": {},
        }
        respx_mock.post(url__regex=rf".*{FMDATA_BASE}/databases/.*/layouts/.*/_find").respond(
            500, json=error_resp
        )

        result = runner.invoke(
            app,
            [
                "record",
                "find",
                "-l",
                "TestLayout",
                "-q",
                '{"Name":"nonexistent"}',
                *PROFILE_ARGS,
            ],
        )

        assert result.exit_code == 0
        data = parse_json_output(result.stdout)
        assert data["ok"] is True
        assert data["data"] == []
        assert sanitize_output(result.stdout) == snapshot
