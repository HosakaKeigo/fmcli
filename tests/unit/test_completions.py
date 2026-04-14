"""補完コールバックのテスト."""

from __future__ import annotations

import pytest

from fmcli.cli.completions import (
    complete_database,
    complete_host,
    complete_layout,
    load_layout_cache,
    load_layout_cache_for_profile,
    save_layout_cache,
)


@pytest.fixture(autouse=True)
def _isolate_config(tmp_path, monkeypatch):
    """設定ディレクトリを一時ディレクトリに隔離する."""
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    config_file = tmp_path / "config.json"
    monkeypatch.setattr("fmcli.core.config.DEFAULT_PROFILES_DIR", profiles_dir)
    monkeypatch.setattr("fmcli.core.config.DEFAULT_CONFIG_FILE", config_file)
    monkeypatch.setattr("fmcli.core.config.DEFAULT_CACHE_DIR", cache_dir)
    monkeypatch.setattr("fmcli.infra.profile_store.DEFAULT_PROFILES_DIR", profiles_dir)
    monkeypatch.setattr("fmcli.cli.completions.DEFAULT_CACHE_DIR", cache_dir)


@pytest.fixture()
def _with_profiles(tmp_path, monkeypatch):
    """テスト用プロファイルを用意する."""
    from fmcli.domain.models import Profile
    from fmcli.infra.profile_store import save_profile

    save_profile(Profile(host="https://host-a.example.com", database="DB_A"))
    save_profile(Profile(host="https://host-a.example.com", database="DB_B"))
    save_profile(Profile(host="https://host-b.example.com", database="DB_C"))


class TestCompleteHost:
    def test_empty_when_no_profiles(self):
        assert complete_host("") == []

    @pytest.mark.usefixtures("_with_profiles")
    def test_returns_unique_hosts(self):
        result = complete_host("")
        assert "https://host-a.example.com" in result
        assert "https://host-b.example.com" in result
        assert len(result) == 2

    @pytest.mark.usefixtures("_with_profiles")
    def test_filters_by_prefix(self):
        result = complete_host("https://host-a")
        assert result == ["https://host-a.example.com"]


class TestCompleteDatabase:
    def test_empty_when_no_profiles(self):
        assert complete_database("") == []

    @pytest.mark.usefixtures("_with_profiles")
    def test_returns_databases(self):
        result = complete_database("")
        assert set(result) == {"DB_A", "DB_B", "DB_C"}

    @pytest.mark.usefixtures("_with_profiles")
    def test_filters_by_prefix(self):
        result = complete_database("DB_A")
        assert result == ["DB_A"]


class TestLayoutCache:
    def test_save_and_load(self):
        save_layout_cache("key1", ["Layout_A", "Layout_B"])
        result = load_layout_cache()
        assert result == ["Layout_A", "Layout_B"]

    def test_multiple_profiles_merged(self):
        save_layout_cache("key1", ["Layout_A", "Layout_B"])
        save_layout_cache("key2", ["Layout_B", "Layout_C"])
        result = load_layout_cache()
        assert result == ["Layout_A", "Layout_B", "Layout_C"]

    def test_empty_when_no_cache(self):
        assert load_layout_cache() == []

    def test_load_for_specific_profile(self):
        save_layout_cache("key1", ["Layout_A", "Layout_B"])
        save_layout_cache("key2", ["Layout_C", "Layout_D"])
        assert load_layout_cache_for_profile("key1") == ["Layout_A", "Layout_B"]
        assert load_layout_cache_for_profile("key2") == ["Layout_C", "Layout_D"]

    def test_load_for_unknown_profile_returns_empty(self):
        save_layout_cache("key1", ["Layout_A"])
        assert load_layout_cache_for_profile("unknown") == []

    def test_load_for_profile_empty_cache(self):
        assert load_layout_cache_for_profile("key1") == []


class TestCompleteLayout:
    def test_empty_when_no_cache(self):
        assert complete_layout("") == []

    def test_returns_from_cache(self):
        save_layout_cache("key1", ["Contacts", "Invoices", "Products"])
        result = complete_layout("")
        assert result == ["Contacts", "Invoices", "Products"]

    def test_filters_by_prefix(self):
        save_layout_cache("key1", ["Contacts", "Invoices", "Products"])
        result = complete_layout("Co")
        assert result == ["Contacts"]

    def test_scoped_to_active_profile(self, monkeypatch):
        """アクティブプロファイルが解決できる場合、そのプロファイルのレイアウトのみ返す."""
        save_layout_cache("profile_a", ["Layout_A1", "Layout_A2"])
        save_layout_cache("profile_b", ["Layout_B1", "Layout_B2"])

        monkeypatch.setattr(
            "fmcli.cli.completions._resolve_active_profile_key",
            lambda host=None, database=None, allow_insecure_http=False: "profile_a",
        )
        result = complete_layout("")
        assert result == ["Layout_A1", "Layout_A2"]

    def test_fallback_to_all_when_profile_unresolved(self, monkeypatch):
        """プロファイルが解決できない場合、全レイアウトにフォールバックする."""
        save_layout_cache("profile_a", ["Layout_A"])
        save_layout_cache("profile_b", ["Layout_B"])

        monkeypatch.setattr(
            "fmcli.cli.completions._resolve_active_profile_key",
            lambda host=None, database=None, allow_insecure_http=False: None,
        )
        result = complete_layout("")
        assert result == ["Layout_A", "Layout_B"]

    def test_scoped_with_prefix_filter(self, monkeypatch):
        """プロファイルスコープとプレフィクスフィルタの組み合わせ."""
        save_layout_cache("profile_a", ["Contacts", "Calendar"])
        save_layout_cache("profile_b", ["Contracts", "Products"])

        monkeypatch.setattr(
            "fmcli.cli.completions._resolve_active_profile_key",
            lambda host=None, database=None, allow_insecure_http=False: "profile_a",
        )
        result = complete_layout("Co")
        assert result == ["Contacts"]

    def test_context_params_forwarded_to_resolve(self, monkeypatch):
        """--host / --database / --allow-insecure-http がコンテキストから resolve に渡される."""
        save_layout_cache("profile_a", ["Layout_A"])
        save_layout_cache("profile_b", ["Layout_B"])

        captured: dict[str, object] = {}

        def mock_resolve(host=None, database=None, allow_insecure_http=False):
            captured["host"] = host
            captured["database"] = database
            captured["allow_insecure_http"] = allow_insecure_http
            return "profile_b"

        monkeypatch.setattr("fmcli.cli.completions._resolve_active_profile_key", mock_resolve)
        monkeypatch.setattr(
            "fmcli.cli.completions._extract_context_params",
            lambda: ("https://other.example.com", "OtherDB", False),
        )
        result = complete_layout("")
        assert result == ["Layout_B"]
        assert captured["host"] == "https://other.example.com"
        assert captured["database"] == "OtherDB"
        assert captured["allow_insecure_http"] is False

    def test_context_allow_insecure_http_forwarded(self, monkeypatch):
        """--allow-insecure-http が補完コンテキストから resolve に渡される."""
        save_layout_cache("http_profile", ["Layout_HTTP"])

        captured: dict[str, object] = {}

        def mock_resolve(host=None, database=None, allow_insecure_http=False):
            captured["allow_insecure_http"] = allow_insecure_http
            return "http_profile"

        monkeypatch.setattr("fmcli.cli.completions._resolve_active_profile_key", mock_resolve)
        monkeypatch.setattr(
            "fmcli.cli.completions._extract_context_params",
            lambda: ("http://legacy.local", "DB", True),
        )
        result = complete_layout("")
        assert result == ["Layout_HTTP"]
        assert captured["allow_insecure_http"] is True
