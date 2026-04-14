"""テスト共通フィクスチャ."""

from __future__ import annotations

import pytest

from fmcli.domain.envelopes import ApiInfo
from fmcli.domain.models import Profile


@pytest.fixture
def profile() -> Profile:
    """テスト用プロファイル."""
    return Profile(name="test", host="https://fm.example.com", database="TestDB")


@pytest.fixture
def api_info() -> ApiInfo:
    """テスト用 ApiInfo."""
    return ApiInfo(method="GET", url="https://fm.example.com/fmi/data/vLatest/")
