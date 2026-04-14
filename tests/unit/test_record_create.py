"""record create 関連のテスト."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from fmcli.main import app
from fmcli.services import record_service
from fmcli.services.query_utils import resolve_field_data
from tests.unit.helpers import make_api_info as _api_info
from tests.unit.helpers import make_profile as _profile
from tests.unit.helpers import strip_ansi

runner = CliRunner()


# ===========================================================================
# resolve_field_data
# ===========================================================================


class TestResolveFieldData:
    """resolve_field_data のテスト."""

    def test_json文字列からdictを返す(self) -> None:
        result = resolve_field_data('{"Name":"田中"}', None)
        assert result == {"Name": "田中"}

    def test_空オブジェクトはdictを返す(self) -> None:
        result = resolve_field_data("{}", None)
        assert result == {}

    def test_不正なJSONでValueError(self) -> None:
        with pytest.raises(ValueError, match="JSON が不正"):
            resolve_field_data("not-json", None)

    def test_配列はValueError(self) -> None:
        with pytest.raises(ValueError, match="JSON オブジェクト"):
            resolve_field_data('[{"Name":"田中"}]', None)

    def test_両方未指定でValueError(self) -> None:
        with pytest.raises(ValueError, match="--field-data"):
            resolve_field_data(None, None)

    def test_ファイルから読み込み(self, tmp_path: Any) -> None:
        f = tmp_path / "data.json"
        f.write_text('{"Name":"鈴木"}', encoding="utf-8")
        result = resolve_field_data(None, str(f))
        assert result == {"Name": "鈴木"}

    def test_ファイル優先_両方指定時(self, tmp_path: Any) -> None:
        """両方指定時は --field-data-file が優先される (resolve_query と同じポリシー)."""
        f = tmp_path / "data.json"
        f.write_text('{"Name":"ファイル"}', encoding="utf-8")
        result = resolve_field_data('{"Name":"文字列"}', str(f))
        assert result == {"Name": "ファイル"}

    def test_存在しないファイルでValueError(self) -> None:
        with pytest.raises(ValueError, match="見つかりません"):
            resolve_field_data(None, "/nonexistent/data.json")

    def test_非jsonファイル拡張子でValueError(self) -> None:
        with pytest.raises(ValueError, match=".json"):
            resolve_field_data(None, "data.txt")


# ===========================================================================
# record_service.create_record
# ===========================================================================


class TestCreateRecordService:
    """record_service.create_record のテスト."""

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_正常作成(self, mock_call: Any) -> None:
        mock_call.return_value = (
            {
                "response": {"recordId": "42", "modId": "0"},
                "messages": [{"code": "0", "message": "OK"}],
            },
            _api_info(method="POST"),
        )

        envelope = record_service.create_record(
            _profile(),
            "Contacts",
            field_data={"Name": "田中"},
        )

        assert envelope.ok is True
        assert envelope.command == "record create"
        assert envelope.data["recordId"] == "42"
        assert envelope.data["modId"] == "0"
        mock_call.assert_called_once()

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_スクリプト結果が付与される(self, mock_call: Any) -> None:
        mock_call.return_value = (
            {
                "response": {
                    "recordId": "42",
                    "modId": "0",
                    "scriptResult": "done",
                    "scriptError": "0",
                },
                "messages": [{"code": "0", "message": "OK"}],
            },
            _api_info(method="POST"),
        )

        envelope = record_service.create_record(
            _profile(),
            "Contacts",
            field_data={"Name": "田中"},
            script="MyScript",
        )

        assert envelope.script_results is not None
        assert envelope.script_results["scriptResult"] == "done"


# ===========================================================================
# record_service.validate_field_names
# ===========================================================================


class TestValidateFieldNames:
    """validate_field_names のテスト."""

    @patch("fmcli.services.metadata_service.layout_describe")
    def test_全フィールドが存在する場合空リスト(self, mock_describe: Any) -> None:
        from tests.unit.helpers import make_envelope

        envelope = make_envelope(
            "layout describe",
            {
                "fieldMetaData": [
                    {"name": "Name", "result": "text"},
                    {"name": "Email", "result": "text"},
                ],
            },
        )
        mock_describe.return_value = envelope

        unknown = record_service.validate_field_names(
            _profile(), "Contacts", {"Name": "田中", "Email": "test@example.com"}
        )
        assert unknown == []

    @patch("fmcli.services.metadata_service.layout_describe")
    def test_存在しないフィールドを検出(self, mock_describe: Any) -> None:
        from tests.unit.helpers import make_envelope

        envelope = make_envelope(
            "layout describe",
            {
                "fieldMetaData": [
                    {"name": "Name", "result": "text"},
                ],
            },
        )
        mock_describe.return_value = envelope

        unknown = record_service.validate_field_names(
            _profile(), "Contacts", {"Name": "田中", "BadField": "value"}
        )
        assert unknown == ["BadField"]


# ===========================================================================
# CLI: record create
# ===========================================================================

_MOCK_PROFILE = "fmcli.cli.record.get_profile"
_MOCK_CREATE = "fmcli.cli.record.record_service.create_record"
_MOCK_VALIDATE = "fmcli.cli.record.record_service.validate_field_names"
_MOCK_DRY_RUN = "fmcli.cli.record.explain_service.dry_run_create"


class TestRecordCreateCli:
    """record create CLI コマンドのテスト."""

    @patch(_MOCK_VALIDATE, return_value=[])
    @patch(_MOCK_CREATE)
    @patch(_MOCK_PROFILE, return_value=_profile())
    def test_正常作成_yes指定(self, _prof: Any, mock_create: Any, _validate: Any) -> None:
        from tests.unit.helpers import make_envelope

        mock_create.return_value = make_envelope(
            "record create", {"recordId": "42", "modId": "0"}, api_method="POST"
        )

        result = runner.invoke(
            app,
            [
                "record",
                "create",
                "-l",
                "Contacts",
                "--field-data",
                '{"Name":"田中"}',
                "--yes",
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["data"]["recordId"] == "42"
        mock_create.assert_called_once()
        # field_data が dict で渡されていることを確認
        call_kwargs = mock_create.call_args
        assert call_kwargs.kwargs["field_data"] == {"Name": "田中"}

    @patch(_MOCK_PROFILE, return_value=_profile())
    def test_非対話環境でyes未指定はエラー(self, _prof: Any) -> None:
        """非対話環境 (CliRunner) では --yes なしで拒否される."""
        result = runner.invoke(
            app,
            [
                "record",
                "create",
                "-l",
                "Contacts",
                "--field-data",
                '{"Name":"田中"}',
                "--skip-field-check",
            ],
        )

        assert result.exit_code != 0
        output = strip_ansi(result.output)
        assert "--yes" in output or "write" in output.lower()

    @patch(_MOCK_DRY_RUN)
    @patch(_MOCK_PROFILE, return_value=_profile())
    def test_dry_runでAPIを呼ばない(self, _prof: Any, mock_dry: Any) -> None:
        from tests.unit.helpers import make_envelope

        mock_dry.return_value = make_envelope("record create --dry-run", {})

        result = runner.invoke(
            app,
            [
                "record",
                "create",
                "-l",
                "Contacts",
                "--field-data",
                '{"Name":"田中"}',
                "--dry-run",
            ],
        )

        assert result.exit_code == 0
        mock_dry.assert_called_once()
        # field_data が dict で渡されていることを確認
        call_kwargs = mock_dry.call_args
        assert call_kwargs.kwargs["field_data"] == {"Name": "田中"}

    @patch(_MOCK_VALIDATE, return_value=["BadField"])
    @patch(_MOCK_PROFILE, return_value=_profile())
    def test_存在しないフィールドでエラー(self, _prof: Any, _validate: Any) -> None:
        result = runner.invoke(
            app,
            [
                "record",
                "create",
                "-l",
                "Contacts",
                "--field-data",
                '{"BadField":"value"}',
                "--yes",
            ],
        )

        assert result.exit_code != 0
        output = strip_ansi(result.output)
        assert "BadField" in output

    @patch(_MOCK_VALIDATE, return_value=["BadField"])
    @patch(_MOCK_CREATE)
    @patch(_MOCK_PROFILE, return_value=_profile())
    def test_skip_field_checkでバリデーションスキップ(
        self, _prof: Any, mock_create: Any, mock_validate: Any
    ) -> None:
        from tests.unit.helpers import make_envelope

        mock_create.return_value = make_envelope(
            "record create", {"recordId": "1", "modId": "0"}, api_method="POST"
        )

        result = runner.invoke(
            app,
            [
                "record",
                "create",
                "-l",
                "Contacts",
                "--field-data",
                '{"BadField":"value"}',
                "--yes",
                "--skip-field-check",
            ],
        )

        assert result.exit_code == 0
        # validate_field_names は呼ばれない
        mock_validate.assert_not_called()

    def test_script無しでallow_scripts不要(self) -> None:
        """--script なしの場合、--allow-scripts バリデーションエラーは出ない."""
        result = runner.invoke(
            app,
            [
                "record",
                "create",
                "-l",
                "Contacts",
                "--field-data",
                '{"Name":"田中"}',
                "--dry-run",
            ],
        )
        output = strip_ansi(result.output)
        assert "--allow-scripts" not in output

    def test_script有りでallow_scripts必須(self) -> None:
        result = runner.invoke(
            app,
            [
                "record",
                "create",
                "-l",
                "Contacts",
                "--field-data",
                '{"Name":"田中"}',
                "--script",
                "MyScript",
                "--yes",
            ],
        )

        assert result.exit_code != 0
        output = strip_ansi(result.output)
        assert "--allow-scripts" in output

    @patch(_MOCK_PROFILE, return_value=_profile())
    def test_field_data未指定でエラー(self, _prof: Any) -> None:
        result = runner.invoke(
            app,
            ["record", "create", "-l", "Contacts", "--yes"],
        )

        assert result.exit_code != 0
        output = strip_ansi(result.output)
        assert "--field-data" in output

    @patch(_MOCK_PROFILE, return_value=_profile())
    def test_不正なJSON_field_dataでエラー(self, _prof: Any) -> None:
        result = runner.invoke(
            app,
            [
                "record",
                "create",
                "-l",
                "Contacts",
                "--field-data",
                "not-json",
                "--yes",
            ],
        )

        assert result.exit_code != 0
        output = strip_ansi(result.output)
        assert "JSON" in output
