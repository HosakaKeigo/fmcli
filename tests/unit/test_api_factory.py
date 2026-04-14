"""api_factory のテスト."""

from __future__ import annotations

from unittest.mock import patch

from fmcli.core.output import DEFAULT_TIMEOUT, OutputConfig, set_output_config
from fmcli.domain.models import Profile
from fmcli.services.api_factory import create_api


def _make_profile(**kwargs: object) -> Profile:
    defaults: dict[str, object] = {
        "host": "https://example.com",
        "database": "TestDB",
        "user": "admin",
        "verify_ssl": True,
    }
    defaults.update(kwargs)
    return Profile(**defaults)  # type: ignore[arg-type]


class TestCreateApi:
    """create_api のテスト."""

    def setup_method(self) -> None:
        set_output_config(OutputConfig())

    def teardown_method(self) -> None:
        set_output_config(OutputConfig())

    @patch("fmcli.services.api_factory.HttpClient")
    def test_デフォルトtimeoutがHttpClientに渡される(self, mock_http_client_cls) -> None:  # noqa: ANN001
        """timeout 未指定時はデフォルト値が HttpClient に渡される."""
        profile = _make_profile()
        create_api(profile)
        mock_http_client_cls.assert_called_once_with(
            profile.host, verify_ssl=True, timeout=DEFAULT_TIMEOUT
        )

    @patch("fmcli.services.api_factory.HttpClient")
    def test_カスタムtimeoutがHttpClientに渡される(self, mock_http_client_cls) -> None:  # noqa: ANN001
        """OutputConfig で指定した timeout が HttpClient に渡される."""
        set_output_config(OutputConfig(timeout=120))
        profile = _make_profile()
        create_api(profile)
        mock_http_client_cls.assert_called_once_with(profile.host, verify_ssl=True, timeout=120)

    @patch("fmcli.services.api_factory.HttpClient")
    def test_verify_sslがprofileから渡される(self, mock_http_client_cls) -> None:  # noqa: ANN001
        """Profile の verify_ssl が HttpClient に渡される."""
        profile = _make_profile(verify_ssl=False)
        create_api(profile)
        mock_http_client_cls.assert_called_once_with(
            profile.host, verify_ssl=False, timeout=DEFAULT_TIMEOUT
        )
