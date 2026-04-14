"""テスト共通ヘルパー関数.

複数テストファイルで重複していたユーティリティを集約する。
"""

from __future__ import annotations

import re
from typing import Any

from fmcli.domain.envelopes import ApiInfo, Envelope
from fmcli.domain.models import Profile

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def strip_ansi(text: str) -> str:
    """ANSI エスケープシーケンスを除去する."""
    return _ANSI_RE.sub("", text)


def make_profile(
    host: str = "https://fm.example.com",
    database: str = "TestDB",
    *,
    name: str = "test",
    **kwargs: Any,
) -> Profile:
    """テスト用プロファイルを生成する."""
    return Profile(name=name, host=host, database=database, **kwargs)


def make_api_info(
    method: str = "GET",
    url: str = "https://fm.example.com/fmi/data/vLatest/...",
    **kwargs: Any,
) -> ApiInfo:
    """テスト用 ApiInfo を生成する."""
    return ApiInfo(method=method, url=url, **kwargs)


def make_fm_response(
    data: list[dict[str, Any]] | None = None,
    data_info: dict[str, Any] | None = None,
    extra_response: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """FileMaker API レスポンスの典型パターンを構築する."""
    if data is None:
        data = [
            {
                "fieldData": {"Name": "Alice", "Age": "30", "Email": "alice@example.com"},
                "portalData": {},
                "recordId": "1",
                "modId": "0",
            },
            {
                "fieldData": {"Name": "Bob", "Age": "25", "Email": "bob@example.com"},
                "portalData": {},
                "recordId": "2",
                "modId": "1",
            },
        ]
    if data_info is None:
        data_info = {
            "totalRecordCount": 100,
            "foundCount": 50,
            "returnedCount": len(data),
        }
    response: dict[str, Any] = {"data": data, "dataInfo": data_info}
    if extra_response:
        response.update(extra_response)
    return {"response": response}


def make_envelope(command: str, data: object = None, *, api_method: str = "GET") -> Envelope:
    """テスト用 Envelope を生成する."""
    prof = make_profile()
    return Envelope.from_profile(
        prof,
        command=command,
        data=data,
        api=ApiInfo(method=api_method, url="https://fm.example.com/fmi/data/vLatest/"),
    )
