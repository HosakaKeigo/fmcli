"""dry-run 機能."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from fmcli.core.masking import mask_token


class DryRunRequest(BaseModel):
    """dry-run で表示する HTTP リクエスト情報."""

    method: str
    url: str
    headers: dict[str, str]
    body: Any = None


def build_dry_run(
    *,
    method: str,
    host: str,
    path: str,
    token: str,
    body: Any = None,
) -> DryRunRequest:
    """dry-run 用リクエスト情報を組み立てる."""
    url = f"{host.rstrip('/')}{path}"
    headers = {
        "Authorization": f"Bearer {mask_token(token)}",
        "Content-Type": "application/json",
    }
    return DryRunRequest(method=method, url=url, headers=headers, body=body)
