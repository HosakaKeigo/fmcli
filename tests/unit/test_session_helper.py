"""セッションヘルパーのテスト."""

from __future__ import annotations

from unittest.mock import MagicMock, Mock, patch

import pytest

from fmcli.core.errors import ApiError, AuthError
from fmcli.domain.envelopes import ApiInfo
from fmcli.domain.models import Profile
from fmcli.services.session_helper import _auto_login, _get_api, call_with_refresh

# FileMakerAPI now supports context manager (__enter__/__exit__),
# so mock_api must be MagicMock (not Mock) wherever used as `with api:`.


def _profile(*, host: str = "https://fm.example.com", database: str = "DB1") -> Profile:
    return Profile(name="test", host=host, database=database)


class TestGetApi:
    """_get_api のテスト."""

    @pytest.mark.parametrize("auth_scope", ["database", "host"])
    def test_returns_api_with_cached_token_preserving_scope(self, auth_scope) -> None:
        with (
            patch("fmcli.services.session_helper.create_api") as mock_create_api,
            patch(
                "fmcli.services.session_helper.resolve_cached_session",
                return_value=("cached_token", auth_scope),
            ),
        ):
            mock_api = MagicMock()
            mock_create_api.return_value = mock_api

            api, scope = _get_api(_profile())

            assert api is mock_api
            assert scope == auth_scope
            mock_api.set_token.assert_called_once_with("cached_token")

    @patch("fmcli.services.session_helper.create_api")
    @patch("fmcli.services.session_helper._auto_login", return_value="new_token")
    @patch("fmcli.services.session_helper.resolve_cached_session", return_value=None)
    def test_auto_logins_when_no_cached_token(
        self, mock_resolve, mock_auto_login, mock_create_api
    ) -> None:
        mock_api = MagicMock()
        mock_create_api.return_value = mock_api

        result_api, scope = _get_api(_profile())

        assert result_api is mock_api
        assert scope == "database"
        mock_auto_login.assert_called_once_with(_profile(), scope="database")
        mock_api.set_token.assert_called_once_with("new_token")


class TestAutoLogin:
    """_auto_login のテスト."""

    @patch("fmcli.services.session_helper.cache_token")
    @patch("fmcli.services.session_helper.create_api")
    @patch(
        "fmcli.services.session_helper.load_credential",
        return_value=("admin", "secret"),
    )
    def test_logs_in_and_caches_token_default_scope(
        self, mock_load_cred, mock_create_api, mock_cache
    ) -> None:
        mock_api = MagicMock()
        mock_api.login.return_value = ("new_token", ApiInfo(method="POST", url="/sessions"))
        mock_create_api.return_value = mock_api

        prof = _profile()
        token = _auto_login(prof)

        assert token == "new_token"
        mock_load_cred.assert_called_once_with(prof.profile_key)
        mock_api.login.assert_called_once_with("admin", "secret")
        mock_cache.assert_called_once_with(prof, "new_token", scope="database")
        # with api: calls __exit__
        mock_api.__exit__.assert_called()

    @patch("fmcli.services.session_helper.cache_token")
    @patch("fmcli.services.session_helper.create_api")
    @patch(
        "fmcli.services.session_helper.load_credential",
        return_value=("admin", "secret"),
    )
    def test_logs_in_and_caches_token_host_scope(
        self, mock_load_cred, mock_create_api, mock_cache
    ) -> None:
        mock_api = MagicMock()
        mock_api.login.return_value = ("new_token", ApiInfo(method="POST", url="/sessions"))
        mock_create_api.return_value = mock_api

        prof = _profile()
        token = _auto_login(prof, scope="host")

        assert token == "new_token"
        mock_load_cred.assert_called_once_with(prof.profile_key)
        mock_api.login.assert_called_once_with("admin", "secret")
        mock_cache.assert_called_once_with(prof, "new_token", scope="host")
        mock_api.__exit__.assert_called()

    @patch("fmcli.services.session_helper.load_credential", return_value=None)
    def test_raises_auth_error_when_no_credential(self, mock_load_cred) -> None:
        with pytest.raises(AuthError, match="セッション切れ"):
            _auto_login(_profile())

    @patch("fmcli.services.session_helper.create_api")
    @patch(
        "fmcli.services.session_helper.load_credential",
        return_value=("admin", "secret"),
    )
    def test_raises_auth_error_on_login_failure(self, mock_load_cred, mock_create_api) -> None:
        mock_api = MagicMock()
        mock_api.login.side_effect = Exception("connection refused")
        mock_create_api.return_value = mock_api

        with pytest.raises(AuthError, match="自動リフレッシュに失敗"):
            _auto_login(_profile())

    @patch("fmcli.services.session_helper.create_api")
    @patch(
        "fmcli.services.session_helper.load_credential",
        return_value=("admin", "secret"),
    )
    def test_closes_api_on_login_failure(self, mock_load_cred, mock_create_api) -> None:
        mock_api = MagicMock()
        mock_api.login.side_effect = Exception("connection refused")
        mock_create_api.return_value = mock_api

        with pytest.raises(AuthError):
            _auto_login(_profile())

        mock_api.__exit__.assert_called()


class TestCallWithRefresh:
    """call_with_refresh のテスト."""

    @patch("fmcli.services.session_helper._get_api")
    def test_returns_result_on_success(self, mock__get_api) -> None:
        mock_api = MagicMock()
        mock__get_api.return_value = (mock_api, "database")
        expected = ({"data": "ok"}, ApiInfo(method="GET", url="/test"))

        fn = Mock(return_value=expected)
        result = call_with_refresh(_profile(), fn)

        assert result == expected
        fn.assert_called_once_with(mock_api)
        mock_api.close.assert_called_once()

    @patch("fmcli.services.session_helper.create_api")
    @patch("fmcli.services.session_helper._auto_login", return_value="refreshed_token")
    @patch("fmcli.services.session_helper._get_api")
    def test_retries_on_401_preserves_database_scope(
        self, mock__get_api, mock_auto_login, mock_create_api
    ) -> None:
        mock_api_first = MagicMock()
        mock__get_api.return_value = (mock_api_first, "database")

        mock_api_second = MagicMock()
        mock_create_api.return_value = mock_api_second

        expected = ({"data": "ok"}, ApiInfo(method="GET", url="/test"))
        fn = Mock(
            side_effect=[
                AuthError("Unauthorized", error_type="auth_expired", retryable=True),
                expected,
            ]
        )

        result = call_with_refresh(_profile(), fn)

        assert result == expected
        assert fn.call_count == 2
        fn.assert_any_call(mock_api_first)
        fn.assert_any_call(mock_api_second)
        mock_auto_login.assert_called_once_with(_profile(), scope="database")
        mock_api_second.set_token.assert_called_once_with("refreshed_token")

    @patch("fmcli.services.session_helper.create_api")
    @patch("fmcli.services.session_helper._auto_login", return_value="refreshed_token")
    @patch("fmcli.services.session_helper._get_api")
    def test_retries_on_401_preserves_host_scope(
        self, mock__get_api, mock_auto_login, mock_create_api
    ) -> None:
        """host scope セッションのリフレッシュ後も host scope が維持される."""
        mock_api_first = MagicMock()
        mock__get_api.return_value = (mock_api_first, "host")

        mock_api_second = MagicMock()
        mock_create_api.return_value = mock_api_second

        expected = ({"data": "ok"}, ApiInfo(method="GET", url="/test"))
        fn = Mock(
            side_effect=[
                AuthError("Unauthorized", error_type="auth_expired", retryable=True),
                expected,
            ]
        )

        result = call_with_refresh(_profile(), fn)

        assert result == expected
        mock_auto_login.assert_called_once_with(_profile(), scope="host")

    @patch("fmcli.services.session_helper.create_api")
    @patch("fmcli.services.session_helper._auto_login", return_value="refreshed_token")
    @patch("fmcli.services.session_helper._get_api")
    def test_retries_on_api_code_952(self, mock__get_api, mock_auto_login, mock_create_api) -> None:
        mock_api_first = MagicMock()
        mock__get_api.return_value = (mock_api_first, "database")

        mock_api_second = MagicMock()
        mock_create_api.return_value = mock_api_second

        expected = ({"data": "ok"}, ApiInfo(method="GET", url="/test"))
        fn = Mock(
            side_effect=[
                ApiError("Invalid token", api_code=952),
                expected,
            ]
        )

        result = call_with_refresh(_profile(), fn)

        assert result == expected
        mock_auto_login.assert_called_once_with(_profile(), scope="database")

    @patch("fmcli.services.session_helper._get_api")
    def test_reraises_non_401_api_error(self, mock__get_api) -> None:
        mock_api = MagicMock()
        mock__get_api.return_value = (mock_api, "database")

        fn = Mock(side_effect=ApiError("Not Found", http_status=404))

        with pytest.raises(ApiError, match="Not Found"):
            call_with_refresh(_profile(), fn)

        mock_api.close.assert_called_once()

    @patch("fmcli.services.session_helper.create_api")
    @patch("fmcli.services.session_helper._auto_login", return_value="refreshed_token")
    @patch("fmcli.services.session_helper._get_api")
    def test_retry_fails_propagates_second_error(
        self, mock__get_api, mock_auto_login, mock_create_api
    ) -> None:
        """952→自動ログイン成功→リトライも失敗 → 2回目の例外が伝播."""
        mock_api_first = MagicMock()
        mock__get_api.return_value = (mock_api_first, "database")

        mock_api_second = MagicMock()
        mock_create_api.return_value = mock_api_second

        fn = Mock(
            side_effect=[
                ApiError("Invalid token", api_code=952),
                ApiError("Server error", http_status=500),
            ]
        )

        with pytest.raises(ApiError, match="Server error"):
            call_with_refresh(_profile(), fn)

        assert fn.call_count == 2
        mock_auto_login.assert_called_once()
        # First api closed after session expired, second api closed in except + finally
        mock_api_first.close.assert_called_once()
        assert mock_api_second.close.call_count == 2

    @patch("fmcli.services.session_helper.create_api")
    @patch("fmcli.services.session_helper._auto_login", return_value="refreshed_token")
    @patch("fmcli.services.session_helper._get_api")
    def test_retry_fails_with_auth_error_propagates(
        self, mock__get_api, mock_auto_login, mock_create_api
    ) -> None:
        """952→自動ログイン成功→リトライでも952 → 2回目の例外が伝播（無限リトライしない）."""
        mock_api_first = MagicMock()
        mock__get_api.return_value = (mock_api_first, "database")

        mock_api_second = MagicMock()
        mock_create_api.return_value = mock_api_second

        fn = Mock(
            side_effect=[
                ApiError("Invalid token", api_code=952),
                ApiError("Invalid token again", api_code=952),
            ]
        )

        with pytest.raises(ApiError, match="Invalid token again"):
            call_with_refresh(_profile(), fn)

        assert fn.call_count == 2
        # Only one auto-login attempt (no infinite retry loop)
        mock_auto_login.assert_called_once()

    @patch("fmcli.services.session_helper._get_api")
    def test_non_retryable_api_error_not_retried(self, mock__get_api) -> None:
        """api_code が 952 以外の ApiError はリトライせず即座に伝播."""
        mock_api = MagicMock()
        mock__get_api.return_value = (mock_api, "database")

        fn = Mock(side_effect=ApiError("Field not found", api_code=102))

        with pytest.raises(ApiError, match="Field not found") as exc_info:
            call_with_refresh(_profile(), fn)

        assert exc_info.value.api_code == 102
        fn.assert_called_once()
        mock_api.close.assert_called_once()

    @patch("fmcli.services.session_helper._get_api")
    def test_non_retryable_auth_error_not_retried(self, mock__get_api) -> None:
        """retryable=False の AuthError はリトライせず即座に伝播."""
        mock_api = MagicMock()
        mock__get_api.return_value = (mock_api, "database")

        fn = Mock(
            side_effect=AuthError("Bad credentials", error_type="auth_invalid", retryable=False)
        )

        with pytest.raises(AuthError, match="Bad credentials"):
            call_with_refresh(_profile(), fn)

        fn.assert_called_once()
        mock_api.close.assert_called_once()

    @patch("fmcli.services.session_helper._get_api")
    def test_reraises_non_api_error(self, mock__get_api) -> None:
        mock_api = MagicMock()
        mock__get_api.return_value = (mock_api, "database")

        fn = Mock(side_effect=ValueError("bad value"))

        with pytest.raises(ValueError, match="bad value"):
            call_with_refresh(_profile(), fn)
