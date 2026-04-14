"""URL エンコーディングユーティリティ."""

from __future__ import annotations

from urllib.parse import quote


def encode_fm_value(value: str) -> str:
    """FileMaker API 向けに値を URL エンコードする."""
    return quote(value, safe="")
