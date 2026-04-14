"""core.compat のテスト."""

from __future__ import annotations

from pathlib import Path

import pytest

from fmcli.core.compat import read_text_utf8


class TestReadTextUtf8:
    """read_text_utf8 のテスト."""

    def test_utf8ファイルを読める(self, tmp_path: Path) -> None:
        f = tmp_path / "test.json"
        f.write_text('{"Name": "田中"}', encoding="utf-8")
        assert read_text_utf8(f) == '{"Name": "田中"}'

    def test_bom付きutf8を読める(self, tmp_path: Path) -> None:
        f = tmp_path / "test.json"
        f.write_bytes(b"\xef\xbb\xbf" + '{"Name": "田中"}'.encode())
        result = read_text_utf8(f)
        # BOM が除去されていること
        assert result == '{"Name": "田中"}'
        assert not result.startswith("\ufeff")

    def test_cp932ファイルにフォールバック(self, tmp_path: Path) -> None:
        f = tmp_path / "test.json"
        f.write_bytes('{"Name": "田中"}'.encode("cp932"))
        assert read_text_utf8(f) == '{"Name": "田中"}'

    def test_存在しないファイルでFileNotFoundError(self, tmp_path: Path) -> None:
        f = tmp_path / "nonexistent.json"
        with pytest.raises(FileNotFoundError):
            read_text_utf8(f)
