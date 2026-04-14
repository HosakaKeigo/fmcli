"""トークンマスキングのテスト."""

from __future__ import annotations

from fmcli.core.masking import mask_token_in_url


class TestMaskTokenInUrl:
    """mask_token_in_url のテスト."""

    def test_masks_token_in_logout_url(self) -> None:
        """logout URL 内のトークンがマスクされること."""
        token = "abc123def456xyz7890"
        url = f"https://example.com/fmi/data/vLatest/databases/MyDB/sessions/{token}"
        result = mask_token_in_url(url, token)
        assert token not in result
        assert "********...7890" in result
        assert (
            result == "https://example.com/fmi/data/vLatest/databases/MyDB/sessions/********...7890"
        )

    def test_short_token_uses_stars(self) -> None:
        """4文字以下のトークンは末尾が **** になること."""
        token = "abcd"
        url = f"https://example.com/sessions/{token}"
        result = mask_token_in_url(url, token)
        assert token not in result
        assert "********...****" in result

    def test_exactly_five_chars_shows_last_four(self) -> None:
        """5文字のトークンは末尾4文字が表示されること."""
        token = "abcde"
        url = f"https://example.com/sessions/{token}"
        result = mask_token_in_url(url, token)
        assert "********...bcde" in result

    def test_empty_token_returns_url_unchanged(self) -> None:
        """空トークンの場合は URL がそのまま返ること."""
        url = "https://example.com/sessions/"
        assert mask_token_in_url(url, "") == url

    def test_token_not_in_url_returns_unchanged(self) -> None:
        """URL にトークンが含まれない場合はそのまま返ること."""
        url = "https://example.com/sessions/other"
        result = mask_token_in_url(url, "notpresent")
        assert result == url

    def test_single_char_token(self) -> None:
        """1文字トークンでも正しくマスクされること."""
        token = "x"
        url = f"https://example.com/sessions/{token}"
        result = mask_token_in_url(url, token)
        assert "********...****" in result
        assert token not in result.split("...****")[0]  # token itself is replaced
