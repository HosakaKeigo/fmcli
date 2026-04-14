"""トークンマスキングユーティリティ."""

from __future__ import annotations

import re

_TOKEN_IN_URL = re.compile(r"(/sessions/)([^/?]+)")


def mask_token(token: str) -> str:
    """トークンをマスクする (末尾4文字のみ表示)."""
    suffix = token[-4:] if len(token) > 4 else "****"
    return f"{'*' * 8}...{suffix}"


def mask_url(url: str) -> str:
    """URL 中の /sessions/<token> 部分をマスクする.

    トークン値が不明な場合に正規表現で検出してマスクする。
    """

    return _TOKEN_IN_URL.sub(lambda m: m.group(1) + mask_token(m.group(2)), url)


def mask_token_in_url(url: str, token: str) -> str:
    """URL 中の既知トークン文字列をマスクする.

    トークン値が既知の場合に str.replace でマスクする。
    """
    if not token:
        return url
    return url.replace(token, mask_token(token))
