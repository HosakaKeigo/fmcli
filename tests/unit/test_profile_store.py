"""プロファイルストアのテスト."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from fmcli.core.errors import ConfigError, NotFoundError
from fmcli.domain.models import Profile
from fmcli.infra.profile_store import (
    delete_profile_by_key,
    list_profiles,
    load_profile_by_key,
    resolve_profile,
    save_profile,
)


@pytest.fixture()
def tmp_config(tmp_path, monkeypatch):
    """テスト用の一時設定ディレクトリ."""
    profiles_dir = tmp_path / "profiles"
    with patch("fmcli.infra.profile_store.DEFAULT_PROFILES_DIR", profiles_dir):
        yield tmp_path


class TestProfileStore:
    def test_save_and_load_by_key(self, tmp_config) -> None:
        profile = Profile(host="https://fm.example.com", database="TestDB")
        save_profile(profile)
        loaded = load_profile_by_key(profile.profile_key)
        assert loaded.host == "https://fm.example.com"
        assert loaded.database == "TestDB"

    def test_load_not_found(self, tmp_config) -> None:
        with pytest.raises(NotFoundError):
            load_profile_by_key("nonexistent")

    def test_list_profiles(self, tmp_config) -> None:
        save_profile(Profile(host="https://a.example.com", database="A"))
        save_profile(Profile(host="https://b.example.com", database="B"))
        profiles = list_profiles()
        assert len(profiles) == 2

    def test_list_empty(self, tmp_config) -> None:
        assert list_profiles() == []

    def test_delete_profile_by_key(self, tmp_config) -> None:
        p = Profile(host="https://del.example.com", database="Del")
        save_profile(p)
        delete_profile_by_key(p.profile_key)
        with pytest.raises(NotFoundError):
            load_profile_by_key(p.profile_key)

    def test_resolve_profile_with_host(self, tmp_config) -> None:
        p = Profile(host="https://fm.example.com", database="MyDB")
        save_profile(p)
        prof = resolve_profile(host="https://fm.example.com", database="MyDB")
        assert prof.host == "https://fm.example.com"
        assert prof.database == "MyDB"

    def test_resolve_profile_host_creates_new(self, tmp_config) -> None:
        """保存されていない host でも Profile を返す."""
        prof = resolve_profile(host="https://new.example.com", database="NewDB")
        assert prof.host == "https://new.example.com"
        assert prof.database == "NewDB"

    def test_resolve_profile_no_context(self, tmp_config) -> None:
        with pytest.raises(ConfigError):
            resolve_profile()

    def test_profile_key_auto_generation(self) -> None:
        p = Profile(host="https://fm.example.com/", database="MyDB")
        assert p.profile_key == "https://fm.example.com|MyDB"

    def test_profile_key_host_only(self) -> None:
        p = Profile(host="https://fm.example.com/")
        assert p.profile_key == "https://fm.example.com"

    def test_same_host_overwrites(self, tmp_config) -> None:
        """同一接続先の profile は上書きされる."""
        save_profile(Profile(host="https://fm.example.com", database="DB", username="old"))
        save_profile(Profile(host="https://fm.example.com", database="DB", username="new"))
        profiles = list_profiles()
        assert len(profiles) == 1
        assert profiles[0].username == "new"


class TestResolveProfileHttpsEnforcement:
    """resolve_profile での HTTPS 強制のテスト."""

    def test_http_host_rejected_in_resolve(self, tmp_config) -> None:
        """resolve_profile で http:// ホストが拒否される."""
        with pytest.raises(ConfigError, match="安全でない HTTP 接続はデフォルトで拒否されます"):
            resolve_profile(host="http://fm.example.com", database="TestDB")

    def test_http_host_accepted_with_flag(
        self,
        tmp_config,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """resolve_profile で --allow-insecure-http 付き http:// が受け入れられる."""
        prof = resolve_profile(
            host="http://fm.example.com",
            database="TestDB",
            allow_insecure_http=True,
        )
        assert prof.host == "http://fm.example.com"
        assert prof.database == "TestDB"
        assert "安全でない HTTP 接続を使用しています" in capsys.readouterr().err

    def test_https_host_accepted_in_resolve(self, tmp_config) -> None:
        """resolve_profile で https:// ホストは問題なく受け入れられる."""
        prof = resolve_profile(host="https://fm.example.com", database="TestDB")
        assert prof.host == "https://fm.example.com"

    @pytest.mark.parametrize("env_value", ["true", "1"])
    def test_allow_insecure_http_env_truthy(
        self,
        tmp_config,
        monkeypatch,
        capsys: pytest.CaptureFixture[str],
        env_value: str,
    ) -> None:
        """FMCLI_ALLOW_INSECURE_HTTP が truthy な値で http:// ホストが許可される."""
        monkeypatch.setenv("FMCLI_ALLOW_INSECURE_HTTP", env_value)
        prof = resolve_profile(host="http://insecure.example.com", database="DB")
        assert prof.host == "http://insecure.example.com"
        assert "安全でない HTTP 接続を使用しています" in capsys.readouterr().err

    def test_allow_insecure_http_env_false_rejects(self, tmp_config, monkeypatch) -> None:
        """FMCLI_ALLOW_INSECURE_HTTP=false では http:// が拒否される."""
        monkeypatch.setenv("FMCLI_ALLOW_INSECURE_HTTP", "false")
        with pytest.raises(ConfigError, match="安全でない HTTP 接続はデフォルトで拒否されます"):
            resolve_profile(host="http://insecure.example.com", database="DB")
