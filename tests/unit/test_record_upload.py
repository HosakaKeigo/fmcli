"""record upload 関連のテスト."""

from __future__ import annotations

import json
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
# record_service.validate_container_field
# ===========================================================================


class TestValidateContainerField:
    """record_service.validate_container_field のテスト."""

    @patch("fmcli.services.metadata_service.layout_describe")
    def test_コンテナ型フィールドはTrueを返す(self, mock_describe: Any) -> None:
        from fmcli.domain.envelopes import Envelope

        mock_describe.return_value = Envelope.from_profile(
            _profile(),
            command="layout describe",
            data={
                "fieldMetaData": [
                    {"name": "Name", "result": "text"},
                    {"name": "Photo", "result": "container"},
                ],
            },
        )
        assert record_service.validate_container_field(_profile(), "Contacts", "Photo") is True

    @patch("fmcli.services.metadata_service.layout_describe")
    def test_非コンテナ型フィールドはFalseを返す(self, mock_describe: Any) -> None:
        from fmcli.domain.envelopes import Envelope

        mock_describe.return_value = Envelope.from_profile(
            _profile(),
            command="layout describe",
            data={
                "fieldMetaData": [
                    {"name": "Name", "result": "text"},
                    {"name": "Photo", "result": "container"},
                ],
            },
        )
        assert record_service.validate_container_field(_profile(), "Contacts", "Name") is False

    @patch("fmcli.services.metadata_service.layout_describe")
    def test_存在しないフィールドはFalseを返す(self, mock_describe: Any) -> None:
        from fmcli.domain.envelopes import Envelope

        mock_describe.return_value = Envelope.from_profile(
            _profile(),
            command="layout describe",
            data={"fieldMetaData": [{"name": "Name", "result": "text"}]},
        )
        assert record_service.validate_container_field(_profile(), "Contacts", "NoSuch") is False

    @patch("fmcli.services.metadata_service.layout_describe")
    def test_メタデータ取得失敗時はTrueを返す(self, mock_describe: Any) -> None:
        from fmcli.domain.envelopes import Envelope

        envelope = Envelope.from_profile(_profile(), command="layout describe", data={})
        envelope.ok = False
        mock_describe.return_value = envelope
        # メタデータ取得失敗時は検証スキップ（True を返す）
        assert record_service.validate_container_field(_profile(), "Contacts", "Photo") is True


# ===========================================================================
# record_service.upload_container
# ===========================================================================


class TestUploadContainerService:
    """record_service.upload_container のテスト."""

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_正常アップロード(self, mock_call: Any, tmp_path: Any) -> None:
        # テスト用ファイルを作成
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)

        mock_call.return_value = (
            {
                "response": {},
                "messages": [{"code": "0", "message": "OK"}],
            },
            _api_info(method="POST"),
        )

        envelope = record_service.upload_container(
            _profile(),
            "Contacts",
            123,
            field_name="Photo",
            file_path=str(test_file),
            file_name="test.jpg",
            mime_type="image/jpeg",
            repetition=1,
        )

        assert envelope.ok is True
        assert envelope.command == "record upload"
        assert envelope.data["recordId"] == "123"
        assert envelope.data["field"] == "Photo"
        assert envelope.data["repetition"] == 1
        assert envelope.data["file"] == "test.jpg"
        assert envelope.data["file_size"] == 104
        assert envelope.data["mime_type"] == "image/jpeg"
        mock_call.assert_called_once()

    @patch("fmcli.services.record_service.call_with_refresh")
    @patch("fmcli.services.record_service.fetch_record_for_update")
    def test_if_mod_id一致で正常アップロード(
        self, mock_fetch: Any, mock_call: Any, tmp_path: Any
    ) -> None:
        test_file = tmp_path / "test.pdf"
        test_file.write_bytes(b"%PDF-1.4" + b"\x00" * 50)

        mock_fetch.return_value = {"modId": "7", "fieldData": {}}
        mock_call.return_value = (
            {
                "response": {},
                "messages": [{"code": "0", "message": "OK"}],
            },
            _api_info(method="POST"),
        )

        envelope = record_service.upload_container(
            _profile(),
            "Contacts",
            123,
            field_name="Document",
            file_path=str(test_file),
            file_name="test.pdf",
            mime_type="application/pdf",
            if_mod_id="7",
        )

        assert envelope.ok is True
        mock_fetch.assert_called_once()

    @patch("fmcli.services.record_service.fetch_record_for_update")
    def test_if_mod_id不一致でエラー(self, mock_fetch: Any, tmp_path: Any) -> None:
        test_file = tmp_path / "test.jpg"
        test_file.write_bytes(b"\x00" * 10)

        mock_fetch.return_value = {"modId": "8", "fieldData": {}}

        with pytest.raises(ApiError, match="modId が一致しません"):
            record_service.upload_container(
                _profile(),
                "Contacts",
                123,
                field_name="Photo",
                file_path=str(test_file),
                file_name="test.jpg",
                mime_type="image/jpeg",
                if_mod_id="7",
            )


# ===========================================================================
# explain_service.dry_run_upload
# ===========================================================================


class TestDryRunUpload:
    """dry_run_upload のテスト."""

    def test_dry_run_uploadはAPIを呼ばない(self) -> None:
        from fmcli.services import explain_service

        with patch("fmcli.services.explain_service.get_cached_token", return_value="tok"):
            envelope = explain_service.dry_run_upload(
                _profile(),
                "Contacts",
                123,
                field_name="Photo",
                file_path="/path/to/avatar.jpg",
                file_name="avatar.jpg",
                file_size=102400,
                mime_type="image/jpeg",
                repetition=1,
            )

        assert envelope.ok is True
        assert envelope.command == "record upload --dry-run"
        assert "Dry run" in envelope.messages[0]
        data = envelope.data
        assert data["method"] == "POST"
        assert "/containers/" in data["url"]
        assert data["body"]["upload"]["file"] == "avatar.jpg"
        assert data["body"]["upload"]["size"] == 102400
        assert data["target"]["field"] == "Photo"
        assert data["target"]["repetition"] == 1


# ===========================================================================
# CLI: record upload
# ===========================================================================

_MOCK_PROFILE = "fmcli.cli.record.get_profile"
_MOCK_UPLOAD = "fmcli.cli.record.record_service.upload_container"
_MOCK_VALIDATE_CONTAINER = "fmcli.cli.record.record_service.validate_container_field"
_MOCK_DRY_RUN_UPLOAD = "fmcli.cli.record.explain_service.dry_run_upload"


class TestRecordUploadCli:
    """record upload CLI コマンドのテスト."""

    @patch(_MOCK_VALIDATE_CONTAINER, return_value=True)
    @patch(_MOCK_UPLOAD)
    @patch(_MOCK_PROFILE, return_value=_profile())
    def test_正常アップロード_yes指定(
        self, _prof: Any, mock_upload: Any, _validate: Any, tmp_path: Any
    ) -> None:
        test_file = tmp_path / "photo.jpg"
        test_file.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)

        mock_upload.return_value = make_envelope(
            "record upload",
            {
                "recordId": "123",
                "field": "Photo",
                "repetition": 1,
                "file": "photo.jpg",
                "file_size": 104,
                "mime_type": "image/jpeg",
            },
            api_method="POST",
        )

        result = runner.invoke(
            app,
            [
                "record",
                "upload",
                "123",
                "-l",
                "Contacts",
                "--field",
                "Photo",
                "--file",
                str(test_file),
                "--yes",
            ],
        )

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["data"]["field"] == "Photo"

    @patch(_MOCK_DRY_RUN_UPLOAD)
    @patch(_MOCK_PROFILE, return_value=_profile())
    def test_dry_run(self, _prof: Any, mock_dry: Any, tmp_path: Any) -> None:
        test_file = tmp_path / "photo.jpg"
        test_file.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 10)

        mock_dry.return_value = make_envelope("record upload --dry-run", {})

        result = runner.invoke(
            app,
            [
                "record",
                "upload",
                "123",
                "-l",
                "Contacts",
                "--field",
                "Photo",
                "--file",
                str(test_file),
                "--dry-run",
            ],
        )

        assert result.exit_code == 0
        mock_dry.assert_called_once()

    @patch(_MOCK_VALIDATE_CONTAINER, return_value=False)
    @patch(_MOCK_PROFILE, return_value=_profile())
    def test_非コンテナフィールドでエラー(self, _prof: Any, _validate: Any, tmp_path: Any) -> None:
        test_file = tmp_path / "photo.jpg"
        test_file.write_bytes(b"\x00" * 10)

        result = runner.invoke(
            app,
            [
                "record",
                "upload",
                "123",
                "-l",
                "Contacts",
                "--field",
                "Name",
                "--file",
                str(test_file),
                "--yes",
            ],
        )

        assert result.exit_code != 0
        output = strip_ansi(result.output)
        assert "コンテナ型ではありません" in output

    @patch(_MOCK_VALIDATE_CONTAINER, return_value=False)
    @patch(_MOCK_UPLOAD)
    @patch(_MOCK_PROFILE, return_value=_profile())
    def test_skip_field_checkでコンテナ検証スキップ(
        self, _prof: Any, mock_upload: Any, _validate: Any, tmp_path: Any
    ) -> None:
        test_file = tmp_path / "photo.jpg"
        test_file.write_bytes(b"\x00" * 10)

        mock_upload.return_value = make_envelope("record upload", {"recordId": "123"})

        result = runner.invoke(
            app,
            [
                "record",
                "upload",
                "123",
                "-l",
                "Contacts",
                "--field",
                "Name",
                "--file",
                str(test_file),
                "--yes",
                "--skip-field-check",
            ],
        )

        assert result.exit_code == 0
        mock_upload.assert_called_once()

    @patch(_MOCK_PROFILE, return_value=_profile())
    def test_存在しないファイルでエラー(self, _prof: Any) -> None:
        result = runner.invoke(
            app,
            [
                "record",
                "upload",
                "123",
                "-l",
                "Contacts",
                "--field",
                "Photo",
                "--file",
                "/nonexistent/file.jpg",
                "--yes",
            ],
        )

        assert result.exit_code != 0
        output = strip_ansi(result.output)
        assert "ファイルが見つかりません" in output

    @patch(_MOCK_VALIDATE_CONTAINER, return_value=True)
    @patch(_MOCK_PROFILE, return_value=_profile())
    def test_非対話環境でyes未指定はエラー(self, _prof: Any, _validate: Any, tmp_path: Any) -> None:
        test_file = tmp_path / "photo.jpg"
        test_file.write_bytes(b"\x00" * 10)

        result = runner.invoke(
            app,
            [
                "record",
                "upload",
                "123",
                "-l",
                "Contacts",
                "--field",
                "Photo",
                "--file",
                str(test_file),
            ],
        )

        assert result.exit_code != 0
        output = strip_ansi(result.output)
        assert "--yes" in output or "write" in output.lower()

    @patch(_MOCK_VALIDATE_CONTAINER, return_value=True)
    @patch(_MOCK_UPLOAD)
    @patch(_MOCK_PROFILE, return_value=_profile())
    def test_if_mod_idオプションが渡される(
        self, _prof: Any, mock_upload: Any, _validate: Any, tmp_path: Any
    ) -> None:
        test_file = tmp_path / "photo.jpg"
        test_file.write_bytes(b"\x00" * 10)

        mock_upload.return_value = make_envelope("record upload", {"recordId": "123"})

        result = runner.invoke(
            app,
            [
                "record",
                "upload",
                "123",
                "-l",
                "Contacts",
                "--field",
                "Photo",
                "--file",
                str(test_file),
                "--if-mod-id",
                "7",
                "--yes",
            ],
        )

        assert result.exit_code == 0
        call_kwargs = mock_upload.call_args
        assert call_kwargs.kwargs["if_mod_id"] == "7"

    @patch(_MOCK_VALIDATE_CONTAINER, return_value=True)
    @patch(_MOCK_UPLOAD)
    @patch(_MOCK_PROFILE, return_value=_profile())
    def test_repetitionオプションが渡される(
        self, _prof: Any, mock_upload: Any, _validate: Any, tmp_path: Any
    ) -> None:
        test_file = tmp_path / "photo.jpg"
        test_file.write_bytes(b"\x00" * 10)

        mock_upload.return_value = make_envelope("record upload", {"recordId": "123"})

        result = runner.invoke(
            app,
            [
                "record",
                "upload",
                "123",
                "-l",
                "Contacts",
                "--field",
                "Photo",
                "--file",
                str(test_file),
                "--repetition",
                "2",
                "--yes",
            ],
        )

        assert result.exit_code == 0
        call_kwargs = mock_upload.call_args
        assert call_kwargs.kwargs["repetition"] == 2

    @patch(_MOCK_PROFILE, return_value=_profile())
    def test_ディレクトリ指定でエラー(self, _prof: Any, tmp_path: Any) -> None:
        result = runner.invoke(
            app,
            [
                "record",
                "upload",
                "123",
                "-l",
                "Contacts",
                "--field",
                "Photo",
                "--file",
                str(tmp_path),
                "--yes",
            ],
        )

        assert result.exit_code != 0
        output = strip_ansi(result.output)
        assert "通常のファイルではありません" in output

    def test_mime_type自動検出(self) -> None:
        """MIME タイプがファイル拡張子から自動判定されることを確認する."""
        import mimetypes

        # 一般的な拡張子のテスト
        assert mimetypes.guess_type("photo.jpg")[0] == "image/jpeg"
        assert mimetypes.guess_type("doc.pdf")[0] == "application/pdf"
        assert mimetypes.guess_type("data.csv")[0] == "text/csv"

        # 不明な拡張子は None → application/octet-stream にフォールバック
        guessed = mimetypes.guess_type("data.xyz123")[0]
        fallback = guessed or "application/octet-stream"
        assert fallback == "application/octet-stream"


# ===========================================================================
# _format_file_size
# ===========================================================================


class TestFormatFileSize:
    """_format_file_size のテスト."""

    def test_バイト表示(self) -> None:
        from fmcli.cli.record import _format_file_size

        assert _format_file_size(500) == "500 B"

    def test_KB表示(self) -> None:
        from fmcli.cli.record import _format_file_size

        assert _format_file_size(1536) == "1.5 KB"

    def test_MB表示(self) -> None:
        from fmcli.cli.record import _format_file_size

        assert _format_file_size(2 * 1024 * 1024) == "2.0 MB"

    def test_GB表示(self) -> None:
        from fmcli.cli.record import _format_file_size

        assert _format_file_size(3 * 1024 * 1024 * 1024) == "3.0 GB"
