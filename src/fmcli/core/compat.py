"""プラットフォーム互換性ユーティリティ."""

from __future__ import annotations

import functools
import sys
from pathlib import Path


@functools.cache
def ensure_utf8_stdio() -> None:
    """Windows 環境で stdout/stderr を UTF-8 に設定する."""
    if sys.platform == "win32":
        for stream_name in ("stdout", "stderr"):
            stream = getattr(sys, stream_name, None)
            if stream and hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8")


def read_text_utf8(path: Path) -> str:
    """UTF-8 でテキストを読み込む。失敗時は CP932 にフォールバックする.

    旧バージョンが Windows 上で encoding 未指定（= CP932）で書いたファイルとの
    後方互換性を維持するためのヘルパー。
    utf-8-sig を使用し、BOM 付き UTF-8 も透過的に処理する。
    """
    try:
        return path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        return path.read_text(encoding="cp932")
