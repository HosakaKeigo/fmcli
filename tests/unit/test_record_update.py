"""record update 関連のテスト."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from fmcli.core.errors import ApiError
from fmcli.main import app
from fmcli.services import record_service
from tests.unit.helpers import make_api_info as _api_info
from tests.unit.helpers import make_envelope, strip_ansi
from tests.unit.helpers import make_profile as _profile

runner = CliRunner()


# ===========================================================================
# record_service.update_record
# ===========================================================================

_CURRENT_RECORD = {
    "fieldData": {"Name": "田中", "Status": "未完了", "Email": "tanaka@example.com"},
    "portalData": {},
    "recordId": "123",
    "modId": "5",
}


class TestUpdateRecordService:
    """record_service.update_record のテスト."""

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_正常更新(self, mock_call: Any) -> None:
        # call_with_refresh は 1 回だけ呼ばれる (PATCH のみ)
        mock_call.return_value = (
            {
                "response": {"modId": "6"},
                "messages": [{"code": "0", "message": "OK"}],
            },
            _api_info(method="PATCH"),
        )

        envelope = record_service.update_record(
            _profile(),
            "Contacts",
            123,
            field_data={"Status": "完了"},
            mod_id="5",
            prefetched_record=_CURRENT_RECORD,
            no_backup=True,
        )

        assert envelope.ok is True
        assert envelope.command == "record update"
        assert envelope.data["recordId"] == "123"
        assert envelope.data["modId"] == "6"
        assert envelope.data["previous_modId"] == "5"
        assert envelope.data["updated_fields"] == ["Status"]
        mock_call.assert_called_once()

    def test_modId不一致でエラー(self) -> None:
        with pytest.raises(ApiError, match="modId が一致しません"):
            record_service.update_record(
                _profile(),
                "Contacts",
                123,
                field_data={"Status": "完了"},
                mod_id="999",  # 不一致
                prefetched_record=_CURRENT_RECORD,
                no_backup=True,
            )

    @patch("fmcli.infra.undo_store.save_undo", return_value="/tmp/undo.json")
    @patch("fmcli.services.record_service.call_with_refresh")
    def test_undo保存成功時にファイルパスを返す(self, mock_call: Any, _save: Any) -> None:
        mock_call.return_value = (
            {
                "response": {"modId": "6"},
                "messages": [{"code": "0", "message": "OK"}],
            },
            _api_info(method="PATCH"),
        )

        envelope = record_service.update_record(
            _profile(),
            "Contacts",
            123,
            field_data={"Status": "完了"},
            mod_id="5",
            prefetched_record=_CURRENT_RECORD,
        )

        assert envelope.data["undo_file"] == "/tmp/undo.json"
        assert not envelope.messages

    @patch("fmcli.infra.undo_store.save_undo", return_value=None)
    @patch("fmcli.services.record_service.call_with_refresh")
    def test_undo保存失敗時に警告メッセージ(self, mock_call: Any, _save: Any) -> None:
        mock_call.return_value = (
            {
                "response": {"modId": "6"},
                "messages": [{"code": "0", "message": "OK"}],
            },
            _api_info(method="PATCH"),
        )

        envelope = record_service.update_record(
            _profile(),
            "Contacts",
            123,
            field_data={"Status": "完了"},
            mod_id="5",
            prefetched_record=_CURRENT_RECORD,
        )

        assert envelope.ok is True
        assert any("undo" in m for m in envelope.messages)
        assert "undo_file" not in envelope.data

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_fetch_record_for_update_レコード未存在(self, mock_call: Any) -> None:
        mock_call.return_value = (
            {"response": {"data": []}},
            _api_info(),
        )

        from fmcli.core.errors import NotFoundError

        with pytest.raises(NotFoundError):
            record_service.fetch_record_for_update(
                _profile(),
                "Contacts",
                999,
            )


# ===========================================================================
# undo_store
# ===========================================================================


class TestDryRunUpdate:
    """dry_run_update のテスト."""

    def test_dry_run_update_はAPIを呼ばない(self) -> None:
        from fmcli.services import explain_service

        with patch("fmcli.services.explain_service.get_cached_token", return_value="tok"):
            envelope = explain_service.dry_run_update(
                _profile(),
                "Contacts",
                123,
                field_data={"Status": "完了"},
                mod_id="5",
            )

        assert envelope.ok is True
        assert envelope.command == "record update --dry-run"
        assert "Dry run" in envelope.messages[0]
        data = envelope.data
        assert data["method"] == "PATCH"
        assert data["body"]["fieldData"] == {"Status": "完了"}
        assert data["body"]["modId"] == "5"


class TestUndoStore:
    """undo_store のテスト."""

    def test_save_undo(self, tmp_path: Any) -> None:
        from fmcli.infra import undo_store

        with patch.object(undo_store, "_get_undo_dir", return_value=tmp_path / "undo"):
            result = undo_store.save_undo(
                record_id=123,
                layout="Contacts",
                host="https://fm.example.com",
                database="TestDB",
                mod_id_before="5",
                mod_id_after="6",
                field_data_before={"Status": "未完了"},
                updated_fields=["Status"],
            )

        assert result is not None
        assert result.endswith(".json")
        with open(result, encoding="utf-8") as f:
            data = json.loads(f.read())
        assert data["record_id"] == 123
        assert data["mod_id_before"] == "5"
        assert data["field_data_before"] == {"Status": "未完了"}

    def test_save_undo_ディレクトリ作成失敗(self) -> None:
        from fmcli.infra import undo_store

        def _fail_mkdir(*_args: Any, **_kwargs: Any) -> None:
            raise OSError("permission denied")

        with (
            patch.object(undo_store, "_get_undo_dir", return_value=Path("/tmp/undo-test")),
            patch.object(Path, "mkdir", side_effect=_fail_mkdir),
        ):
            result = undo_store.save_undo(
                record_id=1,
                layout="L",
                host="h",
                database="d",
                mod_id_before="1",
                mod_id_after="2",
                field_data_before={},
                updated_fields=[],
            )

        assert result is None

    def test_get_undo_dir_xdg(self) -> None:
        from fmcli.infra.undo_store import _get_undo_dir

        with patch.dict("os.environ", {"XDG_CACHE_HOME": "/tmp/test-xdg"}):
            result = _get_undo_dir()
        # Windows ではパスセパレータが異なるため部分一致で確認
        parts = result.parts
        assert "fmcli" in parts
        assert "undo" in parts

    def test_get_undo_dir_default(self) -> None:
        from fmcli.infra.undo_store import _get_undo_dir

        with patch.dict("os.environ", {"XDG_CACHE_HOME": ""}):
            result = _get_undo_dir()
        parts = result.parts
        assert "fmcli" in parts
        assert "undo" in parts


# ===========================================================================
# CLI: record update
# ===========================================================================

_MOCK_PROFILE = "fmcli.cli.record.get_profile"
_MOCK_UPDATE = "fmcli.cli.record.record_service.update_record"
_MOCK_VALIDATE = "fmcli.cli.record.record_service.validate_field_names"
_MOCK_FETCH = "fmcli.cli.record.record_service.fetch_record_for_update"
_MOCK_DRY_RUN = "fmcli.cli.record.explain_service.dry_run_update"


class TestRecordUpdateCli:
    """record update CLI コマンドのテスト."""

    @patch(_MOCK_FETCH, return_value=_CURRENT_RECORD)
    @patch(_MOCK_VALIDATE, return_value=[])
    @patch(_MOCK_UPDATE)
    @patch(_MOCK_PROFILE, return_value=_profile())
    def test_正常更新_yes指定(
        self, _prof: Any, mock_update: Any, _validate: Any, _get: Any
    ) -> None:
        mock_update.return_value = make_envelope(
            "record update",
            {"recordId": "123", "modId": "6", "previous_modId": "5", "updated_fields": ["Status"]},
            api_method="PATCH",
        )

        result = runner.invoke(
            app,
            [
                "record",
                "update",
                "123",
                "-l",
                "Contacts",
                "--field-data",
                '{"Status":"完了"}',
                "--mod-id",
                "5",
                "--yes",
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["data"]["modId"] == "6"

    @patch(_MOCK_DRY_RUN)
    @patch(_MOCK_PROFILE, return_value=_profile())
    def test_dry_run(self, _prof: Any, mock_dry: Any) -> None:
        mock_dry.return_value = make_envelope("record update --dry-run", {})

        result = runner.invoke(
            app,
            [
                "record",
                "update",
                "123",
                "-l",
                "Contacts",
                "--field-data",
                '{"Status":"完了"}',
                "--mod-id",
                "5",
                "--dry-run",
            ],
        )

        assert result.exit_code == 0
        mock_dry.assert_called_once()

    @patch(_MOCK_FETCH, return_value=_CURRENT_RECORD)
    @patch(_MOCK_VALIDATE, return_value=["BadField"])
    @patch(_MOCK_PROFILE, return_value=_profile())
    def test_存在しないフィールドでエラー(self, _prof: Any, _validate: Any, _get: Any) -> None:
        result = runner.invoke(
            app,
            [
                "record",
                "update",
                "123",
                "-l",
                "Contacts",
                "--field-data",
                '{"BadField":"value"}',
                "--mod-id",
                "5",
                "--yes",
            ],
        )

        assert result.exit_code != 0
        output = strip_ansi(result.output)
        assert "BadField" in output

    @patch(_MOCK_FETCH, return_value=_CURRENT_RECORD)
    @patch(_MOCK_PROFILE, return_value=_profile())
    def test_非対話環境でyes未指定はエラー(self, _prof: Any, _get: Any) -> None:
        result = runner.invoke(
            app,
            [
                "record",
                "update",
                "123",
                "-l",
                "Contacts",
                "--field-data",
                '{"Status":"完了"}',
                "--mod-id",
                "5",
                "--skip-field-check",
            ],
        )

        assert result.exit_code != 0
        output = strip_ansi(result.output)
        assert "--yes" in output or "write" in output.lower()

    def test_mod_id未指定でエラー(self) -> None:
        result = runner.invoke(
            app,
            [
                "record",
                "update",
                "123",
                "-l",
                "Contacts",
                "--field-data",
                '{"Status":"完了"}',
                "--yes",
            ],
        )

        assert result.exit_code != 0
        output = strip_ansi(result.output)
        assert "--mod-id" in output

    @patch(_MOCK_PROFILE, return_value=_profile())
    def test_field_data未指定でエラー(self, _prof: Any) -> None:
        result = runner.invoke(
            app,
            [
                "record",
                "update",
                "123",
                "-l",
                "Contacts",
                "--mod-id",
                "5",
                "--yes",
            ],
        )

        assert result.exit_code != 0
        output = strip_ansi(result.output)
        assert "--field-data" in output

    @patch(_MOCK_PROFILE, return_value=_profile())
    def test_空field_dataでエラー(self, _prof: Any) -> None:
        result = runner.invoke(
            app,
            [
                "record",
                "update",
                "123",
                "-l",
                "Contacts",
                "--field-data",
                "{}",
                "--mod-id",
                "5",
                "--yes",
            ],
        )

        assert result.exit_code != 0
        output = strip_ansi(result.output)
        assert "フィールド" in output

    def test_script有りでallow_scripts必須(self) -> None:
        result = runner.invoke(
            app,
            [
                "record",
                "update",
                "123",
                "-l",
                "Contacts",
                "--field-data",
                '{"Status":"完了"}',
                "--mod-id",
                "5",
                "--script",
                "MyScript",
                "--yes",
            ],
        )

        assert result.exit_code != 0
        output = strip_ansi(result.output)
        assert "--allow-scripts" in output
