"""認証情報の保管 (keyring + ファイルフォールバック)."""

from __future__ import annotations

import contextlib
import csv
import io
import json
import logging
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import keyring
from keyring.errors import KeyringError, PasswordDeleteError

from fmcli.core.config import DEFAULT_CONFIG_DIR

SERVICE_NAME = "fmcli"
SESSION_PREFIX = "session"
CREDENTIAL_PREFIX = "credential"
_SESSIONS_DIR = DEFAULT_CONFIG_DIR / "sessions"
_SESSION_TTL_SECONDS = 24 * 60 * 60  # 24 hours

logger = logging.getLogger(__name__)


def save_session(session_key: str, token: str) -> None:
    """セッショントークンを保存する (keyring優先、ファイルフォールバック)."""
    account = _account_name(session_key)
    try:
        keyring.set_password(SERVICE_NAME, account, token)
        return
    except KeyringError:
        logger.debug("keyring unavailable, falling back to file storage")

    _save_to_file(session_key, token)


def load_session(session_key: str) -> str | None:
    """保存済みセッショントークンを読み込む (keyring優先、ファイルフォールバック)."""
    account = _account_name(session_key)
    try:
        token = keyring.get_password(SERVICE_NAME, account)
        if token is not None:
            return token
    except KeyringError:
        logger.debug("keyring unavailable, falling back to file storage")

    return _load_from_file(session_key)


def delete_session(session_key: str) -> None:
    """セッショントークンを削除する (keyring + ファイル両方)."""
    account = _account_name(session_key)
    with contextlib.suppress(KeyringError, PasswordDeleteError):
        keyring.delete_password(SERVICE_NAME, account)

    _delete_file(session_key)


# --- Credential helpers (keyring only, no file fallback) ---


def save_credential(credential_key: str, username: str, password: str) -> bool:
    """認証情報を keyring に保存する.

    credential_key は通常 profile_key (host|database) を使う。
    database list 等 host レベルの操作では host のみをキーにする。

    Returns:
        True if credential was saved successfully, False if keyring is unavailable.
    """
    account = f"{CREDENTIAL_PREFIX}:{credential_key}"
    value = json.dumps({"username": username, "password": password})
    try:
        keyring.set_password(SERVICE_NAME, account, value)
        return True
    except KeyringError:
        logger.debug("keyring unavailable, credential not saved")
        return False


def load_credential(credential_key: str) -> tuple[str, str] | None:
    """keyring から認証情報を読み込む.

    credential_key で見つからない場合、host 部分のみで再検索する (フォールバック)。
    """
    result = load_credential_exact(credential_key)
    if result:
        return result

    # host|database → host のみでフォールバック
    if "|" in credential_key:
        host = credential_key.split("|", 1)[0]
        return load_credential_exact(host)
    return None


def delete_credential(credential_key: str) -> None:
    """keyring から認証情報を削除する."""
    account = f"{CREDENTIAL_PREFIX}:{credential_key}"
    with contextlib.suppress(KeyringError, PasswordDeleteError):
        keyring.delete_password(SERVICE_NAME, account)


def load_credential_exact(credential_key: str) -> tuple[str, str] | None:
    """指定キーで認証情報を読み込む (フォールバックなし)."""
    account = f"{CREDENTIAL_PREFIX}:{credential_key}"
    try:
        value = keyring.get_password(SERVICE_NAME, account)
        if value is None:
            return None
        data = json.loads(value)
        return data["username"], data["password"]
    except (KeyringError, json.JSONDecodeError, KeyError):
        return None


# --- File fallback helpers ---


def _session_file_path(session_key: str) -> Path:
    """セッションキーに対応するファイルパスを返す."""
    safe_name = session_key.replace("/", "_").replace(":", "_").replace("|", "_")
    return _SESSIONS_DIR / f"{safe_name}.json"


def _save_to_file(session_key: str, token: str) -> None:
    """トークンをファイルに安全に保存する (atomic write + パーミッション制限).

    セキュリティ対策:
    - シンボリックリンクの場合は書き込みを拒否する
    - 一時ファイルに書き込み後、パーミッション制限を適用してから atomic rename する
    - パーミッション制限に失敗した場合はファイルを残さない (fail-close)
    """
    path = _session_file_path(session_key)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

    # シンボリックリンクを拒否する
    if path.is_symlink():
        logger.warning("セッションファイルがシンボリックリンクです。書き込みを拒否します: %s", path)
        msg = f"セッションファイルがシンボリックリンクのため書き込みを拒否しました: {path}"
        raise OSError(msg)

    content = json.dumps({"token": token, "created_at": time.time()})

    # 同じディレクトリに一時ファイルを作成し、atomic rename する
    fd = -1
    tmp_path: str | None = None
    try:
        fd, tmp_path = tempfile.mkstemp(dir=path.parent, prefix=".tmp_session_", suffix=".json")
        os.write(fd, content.encode())
        os.close(fd)
        fd = -1  # close 済みマーク
        # パーミッション制限を rename 前に適用 (fail-close: 失敗時はファイルを残さない)
        _restrict_permissions(tmp_path)
        os.replace(tmp_path, path)
        tmp_path = None  # rename 成功
    finally:
        if fd >= 0:
            os.close(fd)
        if tmp_path is not None:
            with contextlib.suppress(OSError):
                os.unlink(tmp_path)


def _get_current_user_sid() -> str | None:
    """Windows で現在のユーザーの SID を取得する."""
    try:
        result = subprocess.run(
            ["whoami", "/user", "/fo", "csv", "/nh"],
            capture_output=True,
            text=True,
            check=True,
        )
        row = next(csv.reader(io.StringIO(result.stdout)))
        return row[1]
    except (subprocess.CalledProcessError, FileNotFoundError, StopIteration, IndexError) as e:
        logger.debug("failed to get current user SID: %s", e)
        return None


def _restrict_permissions(path: str | Path) -> None:
    """ファイルパーミッションをオーナーのみに制限する.

    POSIX: chmod 0o600
    Windows: icacls で継承を除去し、現在のユーザー SID にのみ読み書き権限を付与する

    Raises:
        OSError: パーミッション設定に失敗した場合
    """
    if sys.platform == "win32":
        sid = _get_current_user_sid()
        if not sid:
            msg = "Windows ユーザー SID を取得できませんでした"
            raise OSError(msg)
        try:
            subprocess.run(
                ["icacls", str(path), "/inheritance:r", "/grant:r", f"*{sid}:(R,W)"],
                capture_output=True,
                text=True,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            msg = f"icacls によるパーミッション設定に失敗しました: {e}"
            raise OSError(msg) from e
    else:
        os.chmod(path, 0o600)


def _load_from_file(session_key: str) -> str | None:
    """ファイルからトークンを読み込む."""
    path = _session_file_path(session_key)
    if path.is_symlink():
        logger.warning("セッションファイルがシンボリックリンクです。読み込みを拒否します: %s", path)
        return None
    try:
        from fmcli.core.compat import read_text_utf8

        data: dict[str, object] = json.loads(read_text_utf8(path))
        raw_ts = data.get("created_at", 0)
        created_at = float(raw_ts) if isinstance(raw_ts, int | float) else 0.0
        if time.time() - created_at > _SESSION_TTL_SECONDS:
            logger.debug("session expired (TTL): %s", path)
            path.unlink(missing_ok=True)
            return None
        token = data.get("token")
        return str(token) if token is not None else None
    except (json.JSONDecodeError, OSError) as e:
        logger.debug("failed to load session from %s: %s", path, e)
        return None


def _delete_file(session_key: str) -> None:
    """セッションファイルを削除する."""
    path = _session_file_path(session_key)
    with contextlib.suppress(FileNotFoundError):
        path.unlink()


def _account_name(session_key: str) -> str:
    return f"{SESSION_PREFIX}:{session_key}"
