"""record find クエリ・ソートバリエーションの parametrize テスト."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from fmcli.main import app
from tests.unit.helpers import make_envelope, make_profile

runner = CliRunner()


# ===================================================================
# クエリバリエーション
# ===================================================================

_QUERY_VARIATIONS = [
    ('{"Name":"田中"}', "単一条件"),
    ('[{"Name":"田中"},{"Name":"鈴木"}]', "複数条件 OR"),
    ('{"Age":">=30"}', "比較演算子"),
    ('{"Name":"田中*"}', "ワイルドカード"),
    ('{"Name":"==田中"}', "完全一致"),
    ('{"Name":"田中","City":"東京"}', "AND条件（同一リクエスト内）"),
    ("{}", "空オブジェクト"),
    ("[{}]", "空配列要素"),
]


class TestFindQueryVariations:
    """record find の検索条件バリエーションテスト."""

    @pytest.mark.parametrize(("query", "description"), _QUERY_VARIATIONS)
    @patch("fmcli.cli.record.record_service")
    @patch("fmcli.cli.record.get_profile")
    def test_query_variation(
        self,
        mock_resolve: MagicMock,
        mock_svc: MagicMock,
        query: str,
        description: str,
    ) -> None:
        """クエリ '{description}' で find が正常に呼ばれる."""
        mock_resolve.return_value = make_profile()
        mock_svc.find_records.return_value = make_envelope("record find")

        result = runner.invoke(app, ["record", "find", "-l", "Layout", "-q", query])

        assert result.exit_code == 0, (
            f"[{description}] exit_code={result.exit_code}: {result.output}"
        )
        mock_svc.find_records.assert_called_once()
        call_kwargs = mock_svc.find_records.call_args.kwargs
        assert call_kwargs.get("query") == query


# ===================================================================
# ソートバリエーション
# ===================================================================

_SORT_VARIATIONS = [
    ("Name:ascend", "昇順"),
    ("Name:descend", "降順"),
    ("Name:ascend,Age:descend", "複数フィールド"),
    ("Name", "方向指定なし（デフォルト）"),
]


class TestFindSortVariations:
    """record find のソート指定バリエーションテスト."""

    @pytest.mark.parametrize(("sort_value", "description"), _SORT_VARIATIONS)
    @patch("fmcli.cli.record.record_service")
    @patch("fmcli.cli.record.get_profile")
    def test_sort_variation(
        self,
        mock_resolve: MagicMock,
        mock_svc: MagicMock,
        sort_value: str,
        description: str,
    ) -> None:
        """ソート '{description}' で find が正常に呼ばれ、値がサービスに渡される."""
        mock_resolve.return_value = make_profile()
        mock_svc.find_records.return_value = make_envelope("record find")

        result = runner.invoke(
            app,
            ["record", "find", "-l", "Layout", "-q", '{"a":"b"}', "--sort", sort_value],
        )

        assert result.exit_code == 0, (
            f"[{description}] exit_code={result.exit_code}: {result.output}"
        )
        mock_svc.find_records.assert_called_once()
        call_kwargs = mock_svc.find_records.call_args.kwargs
        assert call_kwargs.get("sort") == sort_value


# ===================================================================
# ページネーションバリエーション
# ===================================================================

_PAGINATION_VARIATIONS = [
    (["--limit", "1"], {"limit": 1}, "limit のみ"),
    (["--limit", "500", "--offset", "100"], {"limit": 500, "offset": 100}, "limit + offset"),
    (["--first"], {"limit": 1}, "--first は limit=1 に変換"),
]


class TestFindLimitOffsetVariations:
    """record find のページネーションバリエーションテスト."""

    @pytest.mark.parametrize(("cli_args", "expected_kwargs", "description"), _PAGINATION_VARIATIONS)
    @patch("fmcli.cli.record.record_service")
    @patch("fmcli.cli.record.get_profile")
    def test_pagination_variation(
        self,
        mock_resolve: MagicMock,
        mock_svc: MagicMock,
        cli_args: list[str],
        expected_kwargs: dict[str, object],
        description: str,
    ) -> None:
        """ページネーション '{description}' で正しい kwargs がサービスに渡される."""
        mock_resolve.return_value = make_profile()
        mock_svc.find_records.return_value = make_envelope("record find")

        result = runner.invoke(
            app,
            ["record", "find", "-l", "Layout", "-q", '{"a":"b"}', *cli_args],
        )

        assert result.exit_code == 0, (
            f"[{description}] exit_code={result.exit_code}: {result.output}"
        )
        mock_svc.find_records.assert_called_once()
        call_kwargs = mock_svc.find_records.call_args.kwargs
        for key, value in expected_kwargs.items():
            assert call_kwargs.get(key) == value, (
                f"[{description}] expected {key}={value}, got {call_kwargs.get(key)}"
            )
