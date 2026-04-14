"""ドメインモデルのエッジケーステスト."""

from __future__ import annotations

import pytest

from fmcli.core.errors import ConfigError
from fmcli.domain.models import (
    Pagination,
    Profile,
    make_profile_key,
    validate_host_scheme,
)


class TestProfileEdgeCases:
    """Profile モデルのエッジケース."""

    def test_empty_database(self) -> None:
        p = Profile(host="https://fm.example.com")
        assert p.database == ""
        assert p.name == ""
        assert p.username == ""

    def test_empty_string_name(self) -> None:
        p = Profile(name="", host="https://fm.example.com", database="DB")
        assert p.name == ""

    def test_special_characters_in_database(self) -> None:
        """FileMaker では全角スペースを含む DB 名が使われることがある."""
        p = Profile(host="https://fm.example.com", database="Sales\u3000Inventory")
        assert p.database == "Sales\u3000Inventory"
        assert "Sales\u3000Inventory" in p.profile_key

    def test_special_characters_in_host(self) -> None:
        p = Profile(host="https://fm-server.example.com:8443", database="DB")
        assert p.host == "https://fm-server.example.com:8443"

    def test_unicode_in_database(self) -> None:
        p = Profile(host="https://fm.example.com", database="テスト用DB")
        assert p.database == "テスト用DB"

    def test_verify_ssl_default_true(self) -> None:
        p = Profile(host="https://fm.example.com")
        assert p.verify_ssl is True

    def test_verify_ssl_false(self) -> None:
        p = Profile(host="https://fm.example.com", verify_ssl=False)
        assert p.verify_ssl is False


class TestCanonicalHost:
    """canonical_host プロパティのテスト."""

    @pytest.mark.parametrize(
        "host,expected",
        [
            ("https://fm.example.com", "https://fm.example.com"),
            ("https://fm.example.com/", "https://fm.example.com"),
            ("https://fm.example.com///", "https://fm.example.com"),
            ("https://fm.example.com:443/", "https://fm.example.com:443"),
            ("https://fm.example.com/fmi/", "https://fm.example.com/fmi"),
        ],
    )
    def test_末尾スラッシュの除去(self, host: str, expected: str) -> None:
        p = Profile(host=host)
        assert p.canonical_host == expected


class TestMakeProfileKey:
    """make_profile_key 関数のテスト."""

    @pytest.mark.parametrize(
        "host,database,expected",
        [
            ("https://fm.example.com", "MyDB", "https://fm.example.com|MyDB"),
            ("https://fm.example.com", "", "https://fm.example.com"),
            ("https://fm.example.com/", "MyDB", "https://fm.example.com|MyDB"),
            ("https://fm.example.com///", "DB", "https://fm.example.com|DB"),
            ("https://fm.example.com", "顧客管理", "https://fm.example.com|顧客管理"),
            ("https://fm.example.com", "A|B", "https://fm.example.com|A|B"),
            ("", "", ""),
        ],
    )
    def test_プロファイルキーの生成(self, host: str, database: str, expected: str) -> None:
        assert make_profile_key(host, database) == expected

    def test_ProfileのprofileKeyと一致する(self) -> None:
        """make_profile_key と Profile.profile_key が同じ結果を返す."""
        p = Profile(host="https://fm.example.com/", database="DB")
        assert p.profile_key == make_profile_key("https://fm.example.com/", "DB")


class TestValidateHostScheme:
    """validate_host_scheme 関数のテスト."""

    @pytest.mark.parametrize(
        "host",
        [
            "https://fm.example.com",
            "HTTPS://fm.example.com",
            "Https://fm.example.com",
            "  https://fm.example.com  ",
            "https://",
        ],
    )
    def test_httpsは受け入れられる(self, host: str) -> None:
        validate_host_scheme(host)  # 例外なし

    @pytest.mark.parametrize(
        "host",
        [
            "http://fm.example.com",
            "HTTP://fm.example.com",
        ],
    )
    def test_httpはデフォルトで拒否される(self, host: str) -> None:
        with pytest.raises(ConfigError, match="安全でない HTTP 接続"):
            validate_host_scheme(host)

    @pytest.mark.parametrize(
        "host,match",
        [
            ("fm.example.com", "無効なホスト URL"),
            ("ftp://fm.example.com", "無効なホスト URL"),
            ("", "無効なホスト URL"),
        ],
    )
    def test_無効なスキームは拒否される(self, host: str, match: str) -> None:
        with pytest.raises(ConfigError, match=match):
            validate_host_scheme(host)

    def test_httpはallow_insecure_httpで許可される(self) -> None:
        warning = validate_host_scheme("http://fm.example.com", allow_insecure_http=True)
        assert warning is not None
        assert "WARNING" in warning
        assert "安全でない HTTP 接続を使用しています" in warning

    def test_httpsでは警告が出ない(self) -> None:
        warning = validate_host_scheme("https://fm.example.com")
        assert warning is None


class TestPaginationEdgeCases:
    """Pagination のエッジケース."""

    def test_defaults(self) -> None:
        p = Pagination()
        assert p.offset == 1
        assert p.limit == 100
        assert p.total_count == 0
        assert p.found_count == 0
        assert p.returned_count == 0

    def test_zero_values(self) -> None:
        p = Pagination(offset=0, limit=0, total_count=0)
        assert p.offset == 0
        assert p.limit == 0

    def test_negative_values(self) -> None:
        """Pydantic は負値をそのまま受け入れる（API 側でバリデーション）."""
        p = Pagination(offset=-1, limit=-10)
        assert p.offset == -1
        assert p.limit == -10

    def test_large_values(self) -> None:
        p = Pagination(
            offset=1,
            limit=1_000_000,
            total_count=10_000_000,
            found_count=5_000_000,
            returned_count=1_000_000,
        )
        assert p.limit == 1_000_000
        assert p.total_count == 10_000_000

    def test_model_dump(self) -> None:
        p = Pagination(offset=1, limit=50, total_count=200, found_count=100, returned_count=50)
        dumped = p.model_dump()
        assert dumped == {
            "offset": 1,
            "limit": 50,
            "total_count": 200,
            "found_count": 100,
            "returned_count": 50,
        }

    def test_returned_exceeds_found(self) -> None:
        """returned_count > found_count も型レベルでは許容される."""
        p = Pagination(found_count=5, returned_count=10)
        assert p.returned_count == 10
