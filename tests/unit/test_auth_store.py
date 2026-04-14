"""認証情報保管 (keyring + ファイルフォールバック) のテスト."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from unittest.mock import patch

import keyring.errors
import pytest

from fmcli.infra.auth_store import (
    _SESSION_TTL_SECONDS,
    _get_current_user_sid,
    _restrict_permissions,
    _save_to_file,
    _session_file_path,
    delete_credential,
    delete_session,
    load_credential,
    load_credential_exact,
    load_session,
    save_credential,
    save_session,
)


def _assert_owner_only(path: os.PathLike[str] | str) -> None:
    """ファイルがオーナーのみアクセス可能であることを検証する (クロスプラットフォーム)."""
    if sys.platform == "win32":
        result = subprocess.run(
            ["icacls", str(path)],
            capture_output=True,
            text=True,
            check=True,
        )
        output = result.stdout
        # 権限設定後、継承フラグ (I) が含まれていてはならない
        assert "(I)" not in output, f"ACL に継承された権限が残っています: {output}"
        # ACL エントリを抽出（: を含む行、ただし最初の行はファイルパスなので除外）
        lines = [ln.strip() for ln in output.splitlines() if ln.strip()]
        acl_lines = [ln for ln in lines[1:] if not ln.startswith("Successfully")]
        # 通常はユーザー自身のみ（SYSTEM/Administrators が含まれる場合もある）
        assert 1 <= len(acl_lines) <= 3, f"予期しない ACL エントリ数: {acl_lines}"
    else:
        file_stat = os.stat(path)
        assert stat.S_IMODE(file_stat.st_mode) == 0o600


class TestAuthStoreKeyring:
    """keyring 経由のトークン保存・読込・削除をテストする."""

    @patch("fmcli.infra.auth_store.keyring")
    def test_save_session(self, mock_keyring) -> None:
        save_session("https://fm.example.com|MainDB", "token123")
        mock_keyring.set_password.assert_called_once_with(
            "fmcli", "session:https://fm.example.com|MainDB", "token123"
        )

    @patch("fmcli.infra.auth_store.keyring")
    def test_load_session_found(self, mock_keyring) -> None:
        mock_keyring.get_password.return_value = "token123"
        result = load_session("https://fm.example.com|MainDB")
        assert result == "token123"
        mock_keyring.get_password.assert_called_once_with(
            "fmcli", "session:https://fm.example.com|MainDB"
        )

    @patch("fmcli.infra.auth_store.keyring")
    def test_load_session_not_found(self, mock_keyring) -> None:
        mock_keyring.get_password.return_value = None
        result = load_session("https://fm.example.com|MainDB")
        assert result is None

    @patch("fmcli.infra.auth_store.keyring")
    def test_delete_session(self, mock_keyring) -> None:
        delete_session("https://fm.example.com|MainDB")
        mock_keyring.delete_password.assert_called_once_with(
            "fmcli", "session:https://fm.example.com|MainDB"
        )

    @patch("fmcli.infra.auth_store.keyring.delete_password")
    def test_delete_session_not_found(self, mock_delete) -> None:
        mock_delete.side_effect = keyring.errors.PasswordDeleteError()
        delete_session("https://fm.example.com|MainDB")  # should not raise


class TestAuthStoreFileFallback:
    """keyring が利用できない場合のファイルフォールバックをテストする."""

    @patch("fmcli.infra.auth_store._session_file_path")
    @patch("fmcli.infra.auth_store.keyring")
    def test_save_falls_back_to_file(self, mock_keyring, mock_path, tmp_path) -> None:
        mock_keyring.set_password.side_effect = keyring.errors.KeyringError("no backend")
        file_path = tmp_path / "test_session.json"
        mock_path.return_value = file_path

        save_session("test_key", "fallback_token")

        assert file_path.exists()
        data = json.loads(file_path.read_text())
        assert data["token"] == "fallback_token"
        _assert_owner_only(file_path)

    @patch("fmcli.infra.auth_store._session_file_path")
    @patch("fmcli.infra.auth_store.keyring")
    def test_load_falls_back_to_file(self, mock_keyring, mock_path, tmp_path) -> None:
        import time

        mock_keyring.get_password.side_effect = keyring.errors.KeyringError("no backend")
        file_path = tmp_path / "test_session.json"
        file_path.write_text(json.dumps({"token": "file_token", "created_at": time.time()}))
        mock_path.return_value = file_path

        result = load_session("test_key")
        assert result == "file_token"

    @patch("fmcli.infra.auth_store._session_file_path")
    @patch("fmcli.infra.auth_store.keyring")
    def test_load_returns_none_when_no_file(self, mock_keyring, mock_path, tmp_path) -> None:
        mock_keyring.get_password.side_effect = keyring.errors.KeyringError("no backend")
        mock_path.return_value = tmp_path / "nonexistent.json"

        result = load_session("test_key")
        assert result is None

    @patch("fmcli.infra.auth_store._session_file_path")
    @patch("fmcli.infra.auth_store.keyring")
    def test_load_returns_none_on_corrupt_file(self, mock_keyring, mock_path, tmp_path) -> None:
        mock_keyring.get_password.side_effect = keyring.errors.KeyringError("no backend")
        file_path = tmp_path / "corrupt.json"
        file_path.write_text("not valid json")
        mock_path.return_value = file_path

        result = load_session("test_key")
        assert result is None

    @patch("fmcli.infra.auth_store._session_file_path")
    @patch("fmcli.infra.auth_store.keyring")
    def test_delete_cleans_up_file(self, mock_keyring, mock_path, tmp_path) -> None:
        file_path = tmp_path / "test_session.json"
        file_path.write_text(json.dumps({"token": "old_token"}))
        mock_path.return_value = file_path

        delete_session("test_key")
        assert not file_path.exists()

    @patch("fmcli.infra.auth_store._session_file_path")
    @patch("fmcli.infra.auth_store.keyring")
    def test_delete_no_file_no_error(self, mock_keyring, mock_path, tmp_path) -> None:
        """ファイルが存在しない場合もエラーにならない."""
        mock_path.return_value = tmp_path / "nonexistent_session.json"
        delete_session("test_key")  # should not raise


class TestSessionFileTTL:
    """セッションファイルの TTL テスト."""

    @patch("fmcli.infra.auth_store._session_file_path")
    @patch("fmcli.infra.auth_store.keyring")
    def test_save_includes_created_at(self, mock_keyring, mock_path, tmp_path) -> None:
        """保存時に created_at タイムスタンプが含まれる."""
        mock_keyring.set_password.side_effect = keyring.errors.KeyringError("no backend")
        file_path = tmp_path / "test_session.json"
        mock_path.return_value = file_path

        save_session("test_key", "token123")

        data = json.loads(file_path.read_text())
        assert "created_at" in data
        assert isinstance(data["created_at"], float)

    @patch("fmcli.infra.auth_store._session_file_path")
    @patch("fmcli.infra.auth_store.keyring")
    def test_load_valid_ttl(self, mock_keyring, mock_path, tmp_path) -> None:
        """TTL 内のトークンは正常に読み込める."""
        mock_keyring.get_password.side_effect = keyring.errors.KeyringError("no backend")
        file_path = tmp_path / "test_session.json"
        import time

        file_path.write_text(json.dumps({"token": "valid_token", "created_at": time.time()}))
        mock_path.return_value = file_path

        result = load_session("test_key")
        assert result == "valid_token"

    @patch("fmcli.infra.auth_store._session_file_path")
    @patch("fmcli.infra.auth_store.keyring")
    def test_load_expired_ttl(self, mock_keyring, mock_path, tmp_path) -> None:
        """TTL 超過のトークンは None を返しファイルを削除する."""
        mock_keyring.get_password.side_effect = keyring.errors.KeyringError("no backend")
        file_path = tmp_path / "test_session.json"
        import time

        expired_time = time.time() - _SESSION_TTL_SECONDS - 1
        file_path.write_text(json.dumps({"token": "expired_token", "created_at": expired_time}))
        mock_path.return_value = file_path

        result = load_session("test_key")
        assert result is None
        assert not file_path.exists()

    @patch("fmcli.infra.auth_store._session_file_path")
    @patch("fmcli.infra.auth_store.keyring")
    def test_load_missing_created_at_treated_as_expired(
        self, mock_keyring, mock_path, tmp_path
    ) -> None:
        """created_at が無いファイルは期限切れとして扱う."""
        mock_keyring.get_password.side_effect = keyring.errors.KeyringError("no backend")
        file_path = tmp_path / "test_session.json"
        file_path.write_text(json.dumps({"token": "old_token"}))
        mock_path.return_value = file_path

        result = load_session("test_key")
        assert result is None


class TestSessionFilePath:
    """_session_file_path のテスト."""

    def test_special_chars_sanitized(self) -> None:
        path = _session_file_path("https://fm.example.com|MainDB")
        assert "/" not in path.name.replace(".json", "")
        assert "|" not in path.name
        assert ":" not in path.name


class TestSaveCredential:
    """save_credential のテスト."""

    @patch("fmcli.infra.auth_store.keyring")
    def test_saves_json_to_keyring(self, mock_keyring) -> None:
        result = save_credential("https://fm.example.com|DB1", "admin", "secret")
        assert result is True
        mock_keyring.set_password.assert_called_once_with(
            "fmcli",
            "credential:https://fm.example.com|DB1",
            json.dumps({"username": "admin", "password": "secret"}),
        )

    @patch("fmcli.infra.auth_store.keyring")
    def test_returns_false_when_keyring_fails(self, mock_keyring) -> None:
        mock_keyring.set_password.side_effect = keyring.errors.KeyringError("no backend")
        result = save_credential("key", "u", "p")
        assert result is False


class TestLoadCredentialExact:
    """load_credential_exact のテスト."""

    @patch("fmcli.infra.auth_store.keyring")
    def test_returns_tuple_on_found(self, mock_keyring) -> None:
        mock_keyring.get_password.return_value = json.dumps(
            {"username": "admin", "password": "secret"}
        )
        result = load_credential_exact("https://fm.example.com|DB1")
        assert result == ("admin", "secret")
        mock_keyring.get_password.assert_called_once_with(
            "fmcli", "credential:https://fm.example.com|DB1"
        )

    @patch("fmcli.infra.auth_store.keyring")
    def test_returns_none_when_not_found(self, mock_keyring) -> None:
        mock_keyring.get_password.return_value = None
        result = load_credential_exact("https://fm.example.com|DB1")
        assert result is None

    @patch("fmcli.infra.auth_store.keyring")
    def test_returns_none_on_keyring_error(self, mock_keyring) -> None:
        mock_keyring.get_password.side_effect = keyring.errors.KeyringError("fail")
        result = load_credential_exact("key")
        assert result is None

    @patch("fmcli.infra.auth_store.keyring")
    def test_returns_none_on_corrupt_json(self, mock_keyring) -> None:
        mock_keyring.get_password.return_value = "not valid json"
        result = load_credential_exact("key")
        assert result is None

    @patch("fmcli.infra.auth_store.keyring")
    def test_returns_none_on_missing_key(self, mock_keyring) -> None:
        mock_keyring.get_password.return_value = json.dumps({"username": "admin"})
        result = load_credential_exact("key")
        assert result is None


class TestLoadCredential:
    """load_credential のテスト (フォールバック付き)."""

    @patch("fmcli.infra.auth_store.keyring")
    def test_exact_match_returned(self, mock_keyring) -> None:
        mock_keyring.get_password.return_value = json.dumps({"username": "u", "password": "p"})
        result = load_credential("https://host|DB1")
        assert result == ("u", "p")
        mock_keyring.get_password.assert_called_once_with("fmcli", "credential:https://host|DB1")

    @patch("fmcli.infra.auth_store.keyring")
    def test_fallback_to_host_only(self, mock_keyring) -> None:
        """host|database で見つからない場合、host のみで再検索する."""
        host_cred = json.dumps({"username": "u", "password": "p"})
        mock_keyring.get_password.side_effect = [None, host_cred]
        result = load_credential("https://host|DB1")
        assert result == ("u", "p")
        calls = mock_keyring.get_password.call_args_list
        assert calls[0].args == ("fmcli", "credential:https://host|DB1")
        assert calls[1].args == ("fmcli", "credential:https://host")

    @patch("fmcli.infra.auth_store.keyring")
    def test_no_fallback_without_pipe(self, mock_keyring) -> None:
        """credential_key に | が含まれない場合はフォールバックしない."""
        mock_keyring.get_password.return_value = None
        result = load_credential("https://host")
        assert result is None
        mock_keyring.get_password.assert_called_once_with("fmcli", "credential:https://host")

    @patch("fmcli.infra.auth_store.keyring")
    def test_returns_none_when_both_miss(self, mock_keyring) -> None:
        mock_keyring.get_password.return_value = None
        result = load_credential("https://host|DB1")
        assert result is None


class TestDeleteCredential:
    """delete_credential のテスト."""

    @patch("fmcli.infra.auth_store.keyring")
    def test_deletes_from_keyring(self, mock_keyring) -> None:
        delete_credential("https://fm.example.com|DB1")
        mock_keyring.delete_password.assert_called_once_with(
            "fmcli", "credential:https://fm.example.com|DB1"
        )

    @patch("fmcli.infra.auth_store.keyring.delete_password")
    def test_not_found_suppressed(self, mock_delete) -> None:
        mock_delete.side_effect = keyring.errors.PasswordDeleteError()
        delete_credential("key")  # should not raise


class TestSecureFileWrite:
    """セッションファイルの安全な書き込みをテストする."""

    @patch("fmcli.infra.auth_store._session_file_path")
    def test_file_created_with_owner_only(self, mock_path, tmp_path) -> None:
        """ファイルがオーナーのみアクセス可能なパーミッションで作成される."""
        file_path = tmp_path / "secure_session.json"
        mock_path.return_value = file_path

        _save_to_file("test_key", "secure_token")

        assert file_path.exists()
        _assert_owner_only(file_path)

    @patch("fmcli.infra.auth_store._session_file_path")
    def test_content_written_correctly(self, mock_path, tmp_path) -> None:
        """トークンが正しく書き込まれる."""
        file_path = tmp_path / "content_session.json"
        mock_path.return_value = file_path

        _save_to_file("test_key", "my_token_123")

        data = json.loads(file_path.read_text())
        assert data["token"] == "my_token_123"
        assert "created_at" in data
        assert isinstance(data["created_at"], float)

    @patch("fmcli.infra.auth_store._session_file_path")
    def test_overwrite_is_atomic(self, mock_path, tmp_path) -> None:
        """既存ファイルの上書きが atomic に行われる (中間状態で空にならない)."""
        file_path = tmp_path / "atomic_session.json"
        mock_path.return_value = file_path

        _save_to_file("test_key", "first_token")
        assert json.loads(file_path.read_text())["token"] == "first_token"

        _save_to_file("test_key", "second_token")
        data = json.loads(file_path.read_text())
        assert data["token"] == "second_token"
        _assert_owner_only(file_path)

    @patch("fmcli.infra.auth_store._session_file_path")
    def test_symlink_target_refused_on_save(self, mock_path, tmp_path) -> None:
        """シンボリックリンク先への書き込みを拒否する."""
        real_file = tmp_path / "real_session.json"
        real_file.write_text("original")
        symlink_path = tmp_path / "symlink_session.json"
        try:
            symlink_path.symlink_to(real_file)
        except OSError:
            pytest.skip("symlink creation requires elevated privileges on this platform")
        mock_path.return_value = symlink_path

        with pytest.raises(OSError, match="シンボリックリンク"):
            _save_to_file("test_key", "malicious_token")

        assert real_file.read_text() == "original"

    @patch("fmcli.infra.auth_store._session_file_path")
    @patch("fmcli.infra.auth_store.keyring")
    def test_symlink_target_refused_on_load(self, mock_keyring, mock_path, tmp_path) -> None:
        """シンボリックリンク先からの読み込みを拒否する."""
        import time as time_mod

        mock_keyring.get_password.side_effect = keyring.errors.KeyringError("no backend")
        real_file = tmp_path / "real_session.json"
        real_file.write_text(json.dumps({"token": "stolen_token", "created_at": time_mod.time()}))
        symlink_path = tmp_path / "symlink_session.json"
        try:
            symlink_path.symlink_to(real_file)
        except OSError:
            pytest.skip("symlink creation requires elevated privileges on this platform")
        mock_path.return_value = symlink_path

        result = load_session("test_key")
        assert result is None

    @patch("fmcli.infra.auth_store._session_file_path")
    def test_no_temp_file_left_on_success(self, mock_path, tmp_path) -> None:
        """書き込み成功後に一時ファイルが残らない."""
        file_path = tmp_path / "clean_session.json"
        mock_path.return_value = file_path

        _save_to_file("test_key", "token")

        files = list(tmp_path.iterdir())
        assert len(files) == 1
        assert files[0].name == "clean_session.json"

    @patch("fmcli.infra.auth_store._restrict_permissions")
    @patch("fmcli.infra.auth_store._session_file_path")
    def test_permission_failure_leaves_no_file(self, mock_path, mock_restrict, tmp_path) -> None:
        """パーミッション設定失敗時にファイルが残らない (fail-close)."""
        file_path = tmp_path / "should_not_exist.json"
        mock_path.return_value = file_path
        mock_restrict.side_effect = OSError("permission denied")

        with pytest.raises(OSError, match="permission denied"):
            _save_to_file("test_key", "secret_token")

        assert not file_path.exists()
        remaining = [f for f in tmp_path.iterdir() if f.name.startswith(".tmp_session_")]
        assert remaining == []


class TestRestrictPermissions:
    """_restrict_permissions のクロスプラットフォームテスト."""

    def test_restricts_file_permissions(self, tmp_path) -> None:
        """ファイルパーミッションがオーナーのみに制限される."""
        file_path = tmp_path / "restricted.txt"
        file_path.write_text("secret")

        _restrict_permissions(file_path)

        _assert_owner_only(file_path)

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific test")
    @patch("fmcli.infra.auth_store._get_current_user_sid")
    def test_raises_on_sid_failure(self, mock_sid, tmp_path) -> None:
        """SID 取得失敗時に OSError を送出する."""
        mock_sid.return_value = None
        file_path = tmp_path / "test.txt"
        file_path.write_text("secret")

        with pytest.raises(OSError, match="SID"):
            _restrict_permissions(file_path)

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific test")
    @patch("fmcli.infra.auth_store.subprocess.run")
    @patch("fmcli.infra.auth_store._get_current_user_sid")
    def test_icacls_called_with_sid(self, mock_sid, mock_run, tmp_path) -> None:
        """icacls が SID ベースで呼び出される."""
        mock_sid.return_value = "S-1-5-21-123456789-0-0-1000"
        file_path = tmp_path / "test.txt"
        file_path.write_text("secret")

        _restrict_permissions(file_path)

        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "icacls"
        assert "*S-1-5-21-123456789-0-0-1000:(R,W)" in args

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific test")
    @patch("fmcli.infra.auth_store.subprocess.run")
    @patch("fmcli.infra.auth_store._get_current_user_sid")
    def test_icacls_failure_raises(self, mock_sid, mock_run, tmp_path) -> None:
        """icacls 失敗時に OSError を送出する."""
        mock_sid.return_value = "S-1-5-21-123456789-0-0-1000"
        mock_run.side_effect = subprocess.CalledProcessError(1, "icacls")
        file_path = tmp_path / "test.txt"
        file_path.write_text("secret")

        with pytest.raises(OSError, match="icacls"):
            _restrict_permissions(file_path)

    @pytest.mark.skipif(sys.platform == "win32", reason="POSIX-specific test")
    def test_posix_chmod(self, tmp_path) -> None:
        """POSIX 環境では chmod 0o600 が適用される."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("secret")

        _restrict_permissions(file_path)

        assert stat.S_IMODE(os.stat(file_path).st_mode) == 0o600


class TestGetCurrentUserSid:
    """_get_current_user_sid のテスト."""

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific test")
    def test_returns_sid_on_windows(self) -> None:
        """Windows 環境で SID を取得できる."""
        sid = _get_current_user_sid()
        assert sid is not None
        assert sid.startswith("S-1-")

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific test")
    @patch("fmcli.infra.auth_store.subprocess.run")
    def test_returns_none_on_failure(self, mock_run) -> None:
        """subprocess 失敗時に None を返す."""
        mock_run.side_effect = subprocess.CalledProcessError(1, "whoami")
        assert _get_current_user_sid() is None
