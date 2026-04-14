"""dry-run 機能のテスト."""

from fmcli.core.dry_run import build_dry_run


class TestDryRun:
    def test_build_dry_run(self) -> None:
        result = build_dry_run(
            method="POST",
            host="https://fm.example.com",
            path="/fmi/data/vLatest/databases/TestDB/layouts/TestLayout/_find",
            token="abc123token",
            body={"query": [{"Name": "Test"}]},
        )
        assert result.method == "POST"
        assert "fm.example.com" in result.url
        assert "TestLayout/_find" in result.url
        assert "********" in result.headers["Authorization"]
        assert result.body == {"query": [{"Name": "Test"}]}

    def test_token_masking(self) -> None:
        result = build_dry_run(
            method="GET",
            host="https://fm.example.com",
            path="/test",
            token="longtoken12345",
        )
        auth = result.headers["Authorization"]
        assert "longtoken" not in auth
        assert "2345" in auth

    def test_short_token_masking(self) -> None:
        result = build_dry_run(
            method="GET",
            host="https://fm.example.com",
            path="/test",
            token="ab",
        )
        auth = result.headers["Authorization"]
        assert "****" in auth
