"""インテグレーションテスト共通フィクスチャ.

CLI → サービス → API クライアント → HTTP の全レイヤーを通すテスト用。
HTTP 通信は respx でモック、設定ディレクトリは tmp_path で隔離する。
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from fmcli.domain.models import Profile

FM_HOST = "https://fm.example.com"
FM_DATABASE = "TestDB"
FM_PROFILE_KEY = f"{FM_HOST}|{FM_DATABASE}"
FM_TOKEN = "test-session-token-12345"
FM_USERNAME = "testuser"
FM_PASSWORD = "testpass"

FMDATA_BASE = "/fmi/data/vLatest"

# --host / -d を明示するための共通引数
PROFILE_ARGS = ["--host", FM_HOST, "-d", FM_DATABASE]


@pytest.fixture
def runner() -> CliRunner:
    """Typer CliRunner."""
    return CliRunner()


@pytest.fixture(autouse=True)
def isolated_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """設定ディレクトリを tmp_path に隔離する.

    config.py のモジュールレベル定数と auth_store の _SESSIONS_DIR をパッチし、
    ユーザー環境を汚さないようにする。
    """
    config_dir = tmp_path / ".config" / "fmcli"
    cache_dir = tmp_path / ".cache" / "fmcli"
    profiles_dir = config_dir / "profiles"
    sessions_dir = config_dir / "sessions"

    for d in (config_dir, cache_dir, profiles_dir, sessions_dir):
        d.mkdir(parents=True, exist_ok=True)

    # config.py のモジュールレベル定数をパッチ
    import fmcli.core.config as config_mod

    monkeypatch.setattr(config_mod, "DEFAULT_CONFIG_DIR", config_dir)
    monkeypatch.setattr(config_mod, "DEFAULT_CONFIG_FILE", config_dir / "config.json")
    monkeypatch.setattr(config_mod, "DEFAULT_PROFILES_DIR", profiles_dir)
    monkeypatch.setattr(config_mod, "DEFAULT_CACHE_DIR", cache_dir)

    # profile_store が DEFAULT_PROFILES_DIR を from import しているため、そちらもパッチ
    import fmcli.infra.profile_store as ps_mod

    monkeypatch.setattr(ps_mod, "DEFAULT_PROFILES_DIR", profiles_dir)

    # auth_store の _SESSIONS_DIR もパッチ
    import fmcli.infra.auth_store as auth_mod

    monkeypatch.setattr(auth_mod, "DEFAULT_CONFIG_DIR", config_dir)
    monkeypatch.setattr(auth_mod, "_SESSIONS_DIR", sessions_dir)

    return tmp_path


@pytest.fixture(autouse=True)
def mock_keyring(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """keyring を無効化し、ファイルフォールバックを使わせる."""
    from keyring.errors import KeyringError

    mock_kr = MagicMock()
    mock_kr.get_password.side_effect = KeyringError("test: keyring disabled")
    mock_kr.set_password.side_effect = KeyringError("test: keyring disabled")
    mock_kr.delete_password.side_effect = KeyringError("test: keyring disabled")

    monkeypatch.setattr("fmcli.infra.auth_store.keyring", mock_kr)
    return mock_kr


@pytest.fixture
def setup_profile(isolated_config: Path) -> Profile:
    """テスト用プロファイルとデフォルト設定を作成する."""
    from fmcli.infra.profile_store import save_profile

    profile = Profile(
        name=FM_PROFILE_KEY,
        host=FM_HOST,
        database=FM_DATABASE,
        username=FM_USERNAME,
    )
    save_profile(profile)
    return profile


@pytest.fixture
def setup_session(setup_profile: Profile, isolated_config: Path) -> Profile:
    """プロファイル + セッショントークンを事前作成する.

    多くのインテグレーションテストで必要な「認証済み状態」をセットアップする。
    """
    from fmcli.infra.auth_store import _save_to_file

    session_key = f"{FM_HOST}|{FM_DATABASE}"
    _save_to_file(session_key, FM_TOKEN)
    return setup_profile


def make_fm_response(
    data: Any = None,
    *,
    message: str = "OK",
    code: int = 0,
) -> dict[str, Any]:
    """FileMaker Data API 標準レスポンスを構築するヘルパー."""
    resp: dict[str, Any] = {
        "messages": [{"code": str(code), "message": message}],
    }
    if data is not None:
        resp["response"] = data
    else:
        resp["response"] = {}
    return resp


def make_records_response(
    records: list[dict[str, Any]],
    *,
    total_count: int | None = None,
) -> dict[str, Any]:
    """レコード取得レスポンスを構築するヘルパー."""
    info: dict[str, Any] = {
        "database": FM_DATABASE,
        "layout": "TestLayout",
        "table": "TestTable",
    }
    if total_count is not None:
        info["foundCount"] = total_count
    else:
        info["foundCount"] = len(records)
    info["returnedCount"] = len(records)
    return make_fm_response({"dataInfo": info, "data": records})


def make_record(
    record_id: str,
    field_data: dict[str, Any],
    *,
    mod_id: str = "1",
) -> dict[str, Any]:
    """単一レコードを構築するヘルパー."""
    return {
        "recordId": record_id,
        "modId": mod_id,
        "fieldData": field_data,
        "portalData": {},
    }


def sanitize_output(output: str) -> str:
    """動的データを固定文字列に置換してスナップショット比較可能にする."""
    # duration_ms
    output = re.sub(r'"duration_ms":\s*[\d.]+', '"duration_ms": 0.0', output)
    # URL のホスト部分は安定しているのでそのまま
    return output


def parse_json_output(output: str) -> dict[str, Any]:
    """CLI の stdout から JSON をパースする."""
    result: dict[str, Any] = json.loads(output)
    return result
