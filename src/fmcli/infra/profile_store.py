"""プロファイル永続化.

profile は host|database を一意キーとし、ファイル名はキーの hash で管理する。
"""

from __future__ import annotations

import hashlib
import json
import os
import sys

from fmcli.core.compat import read_text_utf8
from fmcli.core.config import DEFAULT_PROFILES_DIR
from fmcli.core.errors import ConfigError, NotFoundError
from fmcli.domain.models import Profile


def _ensure_dirs() -> None:
    DEFAULT_PROFILES_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)


def _profile_filename(profile_key: str) -> str:
    """profile_key からファイル名を生成する (hash ベース)."""
    return hashlib.sha256(profile_key.encode()).hexdigest()[:16] + ".json"


def save_profile(profile: Profile) -> None:
    """プロファイルを保存する."""
    _ensure_dirs()
    path = DEFAULT_PROFILES_DIR / _profile_filename(profile.profile_key)
    path.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
    os.chmod(path, 0o600)


def load_profile_by_key(profile_key: str) -> Profile:
    """profile_key でプロファイルを読み込む."""
    path = DEFAULT_PROFILES_DIR / _profile_filename(profile_key)
    try:
        raw = read_text_utf8(path)
    except FileNotFoundError as err:
        raise NotFoundError(f"Profile not found for key '{profile_key}'") from err
    try:
        data = json.loads(raw)
        return Profile.model_validate(data)
    except (json.JSONDecodeError, ValueError) as e:
        raise ConfigError(f"Invalid profile for key '{profile_key}': {e}") from e


def list_profiles() -> list[Profile]:
    """保存済みプロファイル一覧を返す."""
    profiles: list[Profile] = []
    try:
        paths = sorted(DEFAULT_PROFILES_DIR.glob("*.json"))
    except FileNotFoundError:
        return []
    for path in paths:
        try:
            data = json.loads(read_text_utf8(path))
            profiles.append(Profile.model_validate(data))
        except (json.JSONDecodeError, ValueError):
            continue
    return profiles


def delete_profile_by_key(profile_key: str) -> None:
    """プロファイルを profile_key で削除する."""
    path = DEFAULT_PROFILES_DIR / _profile_filename(profile_key)
    path.unlink(missing_ok=True)


def resolve_profile(
    *,
    host: str | None = None,
    database: str | None = None,
    allow_insecure_http: bool = False,
) -> Profile:
    """接続文脈からプロファイルを解決する.

    --host + --database の明示指定が必須。
    """
    from fmcli.domain.models import validate_host_scheme

    if not host:
        raise ConfigError(
            "接続先が特定できません。--host と --database を指定してください。",
            error_code="no_profile",
        )

    # FMCLI_ALLOW_INSECURE_HTTP 環境変数によるフォールバック（セキュリティオプション）
    if not allow_insecure_http:
        allow_insecure_http = os.environ.get("FMCLI_ALLOW_INSECURE_HTTP", "").lower() in (
            "1",
            "true",
        )

    warning = validate_host_scheme(host, allow_insecure_http=allow_insecure_http)
    if warning:
        print(warning, file=sys.stderr)
    from fmcli.domain.models import make_profile_key

    key = make_profile_key(host, database or "")
    try:
        return load_profile_by_key(key)
    except NotFoundError:
        return Profile(host=host, database=database or "")
