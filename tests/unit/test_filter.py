"""filter_by_keywords / filter_layouts_by_keywords のテスト."""

from __future__ import annotations

import pytest

from fmcli.cli.common import filter_by_keywords, filter_layouts_by_keywords

# ── filter_by_keywords (既存の汎用フィルタ) ──


class TestFilterByKeywords:
    def test_empty_keywords_returns_all(self) -> None:
        items: list[dict[str, object]] = [{"name": "A"}, {"name": "B"}]
        assert filter_by_keywords(items, "name", "") == items

    def test_single_keyword(self) -> None:
        items: list[dict[str, object]] = [{"name": "alpha"}, {"name": "beta"}, {"name": "gamma"}]
        result = filter_by_keywords(items, "name", "bet")
        assert result == [{"name": "beta"}]

    def test_multiple_keywords_or(self) -> None:
        items: list[dict[str, object]] = [{"name": "alpha"}, {"name": "beta"}, {"name": "gamma"}]
        result = filter_by_keywords(items, "name", "alp,gam")
        assert len(result) == 2
        assert {"name": "alpha"} in result
        assert {"name": "gamma"} in result

    def test_case_insensitive(self) -> None:
        items: list[dict[str, object]] = [{"name": "Alpha"}]
        assert filter_by_keywords(items, "name", "ALPHA") == [{"name": "Alpha"}]

    def test_skips_non_dict(self) -> None:
        items: list[dict[str, object]] = [{"name": "ok"}, "not a dict"]  # type: ignore[list-item]
        result = filter_by_keywords(items, "name", "ok")
        assert result == [{"name": "ok"}]


# ── filter_layouts_by_keywords (フォルダ対応) ──


def _layout(name: str) -> dict[str, object]:
    """通常レイアウトを作る."""
    return {"name": name, "table": "T"}


def _folder(name: str, children: list[str]) -> dict[str, object]:
    """フォルダレイアウトを作る."""
    return {
        "name": name,
        "isFolder": True,
        "folderLayoutNames": [{"name": c, "table": "T"} for c in children],
    }


class TestFilterLayoutsByKeywords:
    def test_empty_keywords_returns_all(self) -> None:
        items: list[dict[str, object]] = [_layout("A"), _layout("B")]
        assert filter_layouts_by_keywords(items, "") == items

    def test_plain_layout_match(self) -> None:
        items: list[dict[str, object]] = [
            _layout("report-A"),
            _layout("report-B"),
            _layout("other"),
        ]
        result = filter_layouts_by_keywords(items, "report")
        assert len(result) == 2

    def test_plain_layout_no_match(self) -> None:
        items: list[dict[str, object]] = [_layout("alpha"), _layout("beta")]
        result = filter_layouts_by_keywords(items, "xyz")
        assert result == []

    def test_folder_name_match_keeps_all_children(self) -> None:
        """フォルダ名がマッチしたらフォルダごと (子全体) 残す."""
        folder = _folder("reports", ["child-A", "child-B", "child-C"])
        result = filter_layouts_by_keywords([folder], "reports")
        assert len(result) == 1
        assert len(result[0]["folderLayoutNames"]) == 3  # type: ignore[arg-type]

    def test_child_layout_match_flattens(self) -> None:
        """フォルダ名はマッチしないが子レイアウトがマッチ → マッチした子をフラット展開."""
        folder = _folder("group-100", ["101-detail", "102-summary", "103-detail"])
        result = filter_layouts_by_keywords([folder], "detail")
        assert len(result) == 2
        assert {r["name"] for r in result} == {"101-detail", "103-detail"}
        # フラット展開なので folderLayoutNames を持たない
        assert all("folderLayoutNames" not in r for r in result)

    def test_child_match_does_not_mutate_original(self) -> None:
        """子フィルタでオリジナルが変更されないこと."""
        folder = _folder("group", ["match-A", "no-B"])
        original_children = list(folder["folderLayoutNames"])  # type: ignore[arg-type]
        filter_layouts_by_keywords([folder], "match")
        assert folder["folderLayoutNames"] == original_children

    def test_no_child_match_excludes_folder(self) -> None:
        """フォルダ名も子レイアウト名もマッチしなければ除外."""
        folder = _folder("group-100", ["child-A", "child-B"])
        result = filter_layouts_by_keywords([folder], "xyz")
        assert result == []

    def test_mixed_layouts_and_folders(self) -> None:
        """通常レイアウトとフォルダが混在するケース."""
        items: list[dict[str, object]] = [
            _layout("standalone-report"),
            _folder("summaries", ["summary-Q1", "summary-Q2", "detail-Q1"]),
            _layout("unrelated"),
        ]
        result = filter_layouts_by_keywords(items, "report,summary")
        # standalone-report + summary-Q1 + summary-Q2 = 3件 (フラット展開)
        assert len(result) == 3
        assert result[0]["name"] == "standalone-report"
        assert {r["name"] for r in result[1:]} == {"summary-Q1", "summary-Q2"}

    def test_multiple_keywords_match_children(self) -> None:
        """複数キーワード (OR) で子レイアウトにマッチ → フラット展開."""
        folder = _folder("group", ["alpha-1", "beta-2", "gamma-3"])
        result = filter_layouts_by_keywords([folder], "alpha,gamma")
        assert len(result) == 2
        assert {r["name"] for r in result} == {"alpha-1", "gamma-3"}

    def test_case_insensitive(self) -> None:
        folder = _folder("Group", ["Report-A", "other"])
        result = filter_layouts_by_keywords([folder], "REPORT")
        assert len(result) == 1
        assert result[0]["name"] == "Report-A"

    @pytest.mark.parametrize(
        "keywords_csv",
        [" ", ",", " , , "],
    )
    def test_whitespace_only_keywords_returns_all(self, keywords_csv: str) -> None:
        items: list[dict[str, object]] = [_layout("A"), _folder("F", ["B"])]
        assert filter_layouts_by_keywords(items, keywords_csv) == items
