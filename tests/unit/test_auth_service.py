"""認証サービスのテスト."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fmcli.domain.envelopes import ApiInfo
from fmcli.domain.models import Profile
from fmcli.services import auth_service


def _profile(*, host: str = "https://fm.example.com", database: str = "MainDB") -> Profile:
    return Profile(host=host, database=database)


class TestAuthService:
    @patch("fmcli.services.auth_service.save_profile")
    @patch("fmcli.services.auth_service.create_api")
    @patch("fmcli.services.auth_service.cache_token")
    def test_login_can_store_host_scope(self, mock_cache, mock_create_api, mock_save) -> None:
        mock_api = MagicMock()
        mock_api.login.return_value = ("token123", ApiInfo(method="POST", url="/sessions"))
        mock_create_api.return_value = mock_api

        env = auth_service.login(_profile(), "admin", "secret", scope="host")

        assert env.ok is True
        assert env.data["auth_scope"] == "host"
        assert env.data["profile_key"] == "https://fm.example.com|MainDB"
        mock_cache.assert_called_once_with(_profile(), "token123", scope="host")
        # with api: calls __exit__
        mock_api.__exit__.assert_called()

    @patch(
        "fmcli.services.auth_service.resolve_cached_session",
        return_value=("token123", "host"),
    )
    @patch("fmcli.services.auth_service.create_api")
    def test_status_reports_resolved_scope(self, mock_create_api, mock_resolve) -> None:
        mock_api = MagicMock()
        mock_api.validate_session.return_value = (
            True,
            ApiInfo(method="GET", url="/validateSession"),
        )
        mock_create_api.return_value = mock_api

        env = auth_service.status(_profile())

        assert env.ok is True
        assert env.data["authenticated"] is True
        assert env.data["auth_scope"] == "host"
        assert env.data["host"] == "https://fm.example.com"
        assert env.data["profile_key"] == "https://fm.example.com|MainDB"

    @patch(
        "fmcli.services.auth_service.resolve_cached_session",
        return_value=("token123", "host"),
    )
    @patch("fmcli.services.auth_service.clear_cached_token")
    @patch("fmcli.services.auth_service.create_api")
    def test_logout_auto_clears_resolved_scope(
        self, mock_create_api, mock_clear, mock_resolve
    ) -> None:
        mock_api = MagicMock()
        mock_api.logout.return_value = ApiInfo(method="DELETE", url="/sessions/token123")
        mock_create_api.return_value = mock_api

        env = auth_service.logout(_profile())

        assert env.ok is True
        assert env.data["auth_scope"] == "host"
        mock_clear.assert_called_once_with(_profile(), scope="host")


class TestLoginCredentialWarning:
    """login 時の認証情報保存警告テスト."""

    @patch("fmcli.services.auth_service.save_profile")
    @patch("fmcli.services.auth_service.save_credential", return_value=False)
    @patch("fmcli.services.auth_service.create_api")
    @patch("fmcli.services.auth_service.cache_token")
    def test_login_warns_when_credential_persistence_fails(
        self, mock_cache, mock_create_api, mock_save_cred, mock_save_prof
    ) -> None:
        mock_api = MagicMock()
        mock_api.login.return_value = ("token123", ApiInfo(method="POST", url="/sessions"))
        mock_create_api.return_value = mock_api

        env = auth_service.login(_profile(), "admin", "secret")

        assert env.ok is True
        assert env.data["credential_persisted"] is False
        assert len(env.messages) == 1
        assert "keyring" in env.messages[0]
        assert "自動リフレッシュ" in env.messages[0]

    @patch("fmcli.services.auth_service.save_profile")
    @patch("fmcli.services.auth_service.save_credential", return_value=True)
    @patch("fmcli.services.auth_service.create_api")
    @patch("fmcli.services.auth_service.cache_token")
    def test_login_no_warning_when_credential_persistence_succeeds(
        self, mock_cache, mock_create_api, mock_save_cred, mock_save_prof
    ) -> None:
        mock_api = MagicMock()
        mock_api.login.return_value = ("token123", ApiInfo(method="POST", url="/sessions"))
        mock_create_api.return_value = mock_api

        env = auth_service.login(_profile(), "admin", "secret")

        assert env.ok is True
        assert env.data["credential_persisted"] is True
        assert len(env.messages) == 0


class TestStatusCredentialInfo:
    """auth status の認証情報永続化状態テスト."""

    @patch("fmcli.services.auth_service.load_credential", return_value=("u", "p"))
    @patch(
        "fmcli.services.auth_service.resolve_cached_session",
        return_value=("token123", "database"),
    )
    @patch("fmcli.services.auth_service.create_api")
    def test_status_shows_credential_persisted(
        self, mock_create_api, mock_resolve, mock_load_cred
    ) -> None:
        mock_api = MagicMock()
        mock_api.validate_session.return_value = (
            True,
            ApiInfo(method="GET", url="/validateSession"),
        )
        mock_create_api.return_value = mock_api

        env = auth_service.status(_profile())

        assert env.data["credential_persisted"] is True

    @patch("fmcli.services.auth_service.load_credential", return_value=None)
    @patch(
        "fmcli.services.auth_service.resolve_cached_session",
        return_value=("token123", "database"),
    )
    @patch("fmcli.services.auth_service.create_api")
    def test_status_shows_credential_not_persisted(
        self, mock_create_api, mock_resolve, mock_load_cred
    ) -> None:
        mock_api = MagicMock()
        mock_api.validate_session.return_value = (
            True,
            ApiInfo(method="GET", url="/validateSession"),
        )
        mock_create_api.return_value = mock_api

        env = auth_service.status(_profile())

        assert env.data["credential_persisted"] is False


class TestListSessions:
    """list_sessions のテスト."""

    @patch("fmcli.services.auth_service.load_credential")
    @patch("fmcli.services.auth_service.resolve_cached_session")
    @patch("fmcli.services.auth_service.list_profiles")
    def test_returns_profiles_with_session_status(
        self, mock_list, mock_resolve, mock_load_cred
    ) -> None:
        prof1 = _profile()
        prof2 = _profile(host="https://fm2.example.com", database="DB2")
        mock_list.return_value = [prof1, prof2]
        mock_resolve.side_effect = [
            ("token123", "database"),
            None,
        ]
        mock_load_cred.side_effect = [("u", "p"), None]

        env = auth_service.list_sessions()

        assert env.ok is True
        assert env.command == "auth list"
        assert len(env.data) == 2

        s1 = env.data[0]
        assert s1["profile_key"] == "https://fm.example.com|MainDB"
        assert s1["has_session"] is True
        assert s1["auth_scope"] == "database"
        assert s1["credential_persisted"] is True

        s2 = env.data[1]
        assert s2["profile_key"] == "https://fm2.example.com|DB2"
        assert s2["has_session"] is False
        assert s2["auth_scope"] is None
        assert s2["credential_persisted"] is False

    @patch("fmcli.services.auth_service.resolve_cached_session")
    @patch("fmcli.services.auth_service.list_profiles", return_value=[])
    def test_returns_empty_list_when_no_profiles(self, mock_list, mock_resolve) -> None:
        env = auth_service.list_sessions()

        assert env.ok is True
        assert env.data == []
        mock_resolve.assert_not_called()
