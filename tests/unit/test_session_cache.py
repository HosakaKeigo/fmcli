"""セッションキャッシュのテスト."""

from __future__ import annotations

from unittest.mock import patch

from fmcli.domain.models import Profile
from fmcli.infra.session_cache import (
    cache_token,
    clear_cached_token,
    get_cached_token,
    resolve_cached_session,
)


def _profile(*, host: str = "https://fm.example.com", database: str = "DB1") -> Profile:
    return Profile(name="test", host=host, database=database)


class TestSessionCache:
    @patch("fmcli.infra.session_cache.load_session", return_value="token123")
    def test_get_cached_token_prefers_database_scope(self, mock_load) -> None:
        result = get_cached_token(_profile())
        assert result == "token123"
        mock_load.assert_called_once_with("https://fm.example.com|DB1")

    @patch("fmcli.infra.session_cache.save_session")
    def test_cache_token_normalizes_trailing_slash(self, mock_save) -> None:
        cache_token(_profile(host="https://fm.example.com/"), "token123")
        mock_save.assert_called_once_with("https://fm.example.com|DB1", "token123")

    @patch("fmcli.infra.session_cache.delete_session")
    def test_clear_cached_token_uses_database_in_key(self, mock_delete) -> None:
        clear_cached_token(_profile(database="DB2"), scope="database")
        mock_delete.assert_called_once_with("https://fm.example.com|DB2")

    @patch("fmcli.infra.session_cache.save_session")
    def test_cache_token_can_store_host_scope(self, mock_save) -> None:
        cache_token(_profile(database="DB2"), "token123", scope="host")
        mock_save.assert_called_once_with("https://fm.example.com", "token123")

    @patch("fmcli.infra.session_cache.load_session")
    def test_resolve_cached_session_falls_back_to_host_scope(self, mock_load) -> None:
        mock_load.side_effect = [None, "hosttoken"]
        result = resolve_cached_session(_profile(database="DB2"))
        assert result == ("hosttoken", "host")
        assert mock_load.call_args_list[0].args == ("https://fm.example.com|DB2",)
        assert mock_load.call_args_list[1].args == ("https://fm.example.com",)

    @patch("fmcli.infra.session_cache.load_session")
    def test_resolve_cached_session_can_target_specific_scope(self, mock_load) -> None:
        mock_load.return_value = "hosttoken"
        result = resolve_cached_session(_profile(database="DB2"), scope="host")
        assert result == ("hosttoken", "host")
        mock_load.assert_called_once_with("https://fm.example.com")
