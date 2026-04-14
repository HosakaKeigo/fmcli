"""query_utils のテスト."""

from __future__ import annotations

import json
from typing import Any

import pytest

from fmcli.services.query_utils import (
    build_portal_get_params,
    build_portal_post_body,
    parse_portal_params,
    parse_script_params,
    parse_sort,
    resolve_query,
)

# ===========================================================================
# parse_sort
# ===========================================================================


class TestParseSort:
    """parse_sort のテスト."""

    @pytest.mark.parametrize(
        "sort_str,expected",
        [
            (None, None),
            ("", None),
            ("Name", [{"fieldName": "Name", "sortOrder": "ascend"}]),
            ("Name:ascend", [{"fieldName": "Name", "sortOrder": "ascend"}]),
            ("Age:descend", [{"fieldName": "Age", "sortOrder": "descend"}]),
            (
                "Name:ascend,Age:descend",
                [
                    {"fieldName": "Name", "sortOrder": "ascend"},
                    {"fieldName": "Age", "sortOrder": "descend"},
                ],
            ),
            (
                "Name,Age:descend",
                [
                    {"fieldName": "Name", "sortOrder": "ascend"},
                    {"fieldName": "Age", "sortOrder": "descend"},
                ],
            ),
            # asc/desc エイリアス
            ("Name:asc", [{"fieldName": "Name", "sortOrder": "ascend"}]),
            ("Age:desc", [{"fieldName": "Age", "sortOrder": "descend"}]),
            (
                "Name:asc,Age:desc",
                [
                    {"fieldName": "Name", "sortOrder": "ascend"},
                    {"fieldName": "Age", "sortOrder": "descend"},
                ],
            ),
        ],
    )
    def test_ソート文字列のパース(self, sort_str: str | None, expected: list | None) -> None:
        assert parse_sort(sort_str) == expected

    def test_無効なソート順でValueError(self) -> None:
        with pytest.raises(ValueError, match="無効なソート順.*asc, desc"):
            parse_sort("Name:invalid")

    def test_パーツ前後のスペースはstripされる(self) -> None:
        result = parse_sort(" Name :ascend")
        assert result is not None
        assert result[0]["fieldName"] == "Name"
        assert result[0]["sortOrder"] == "ascend"


# ===========================================================================
# parse_portal_params
# ===========================================================================


class TestParsePortalParams:
    """parse_portal_params のテスト."""

    def test_Noneを渡すとNone(self) -> None:
        assert parse_portal_params(None) is None

    def test_空文字列を渡すとNone(self) -> None:
        assert parse_portal_params("") is None

    def test_単一ポータル名(self) -> None:
        result = parse_portal_params("Orders")
        assert result == {"portal": ["Orders"]}

    def test_複数ポータル名(self) -> None:
        result = parse_portal_params("Orders,Items")
        assert result is not None
        assert result["portal"] == ["Orders", "Items"]

    def test_ポータルにlimit指定(self) -> None:
        result = parse_portal_params("Orders:10")
        assert result is not None
        assert result["portal"] == ["Orders"]
        assert result["limit.Orders"] == "10"

    def test_ポータルにlimitとoffset指定(self) -> None:
        result = parse_portal_params("Orders:10:5")
        assert result is not None
        assert result["portal"] == ["Orders"]
        assert result["limit.Orders"] == "10"
        assert result["offset.Orders"] == "5"

    def test_複数ポータルに個別limit指定(self) -> None:
        result = parse_portal_params("Orders:10,Items:5:2")
        assert result is not None
        assert result["portal"] == ["Orders", "Items"]
        assert result["limit.Orders"] == "10"
        assert result["limit.Items"] == "5"
        assert result["offset.Items"] == "2"

    def test_空のパーツは無視(self) -> None:
        result = parse_portal_params("Orders,,Items")
        assert result is not None
        assert result["portal"] == ["Orders", "Items"]

    def test_全て空パーツだとNone(self) -> None:
        result = parse_portal_params(",,")
        assert result is None


# ===========================================================================
# parse_script_params
# ===========================================================================


class TestParseScriptParams:
    """parse_script_params のテスト."""

    def test_全てNoneだとNone(self) -> None:
        assert parse_script_params(None) is None

    def test_全て空文字列だとNone(self) -> None:
        assert parse_script_params("", "", "") is None

    def test_メインスクリプトのみ(self) -> None:
        result = parse_script_params("MyScript")
        assert result == {"script": "MyScript"}

    def test_スクリプトにパラメータ付き(self) -> None:
        result = parse_script_params("MyScript:param1")
        assert result == {"script": "MyScript", "script.param": "param1"}

    def test_パラメータにコロンを含む場合(self) -> None:
        result = parse_script_params("MyScript:param:with:colons")
        assert result is not None
        assert result["script"] == "MyScript"
        assert result["script.param"] == "param:with:colons"

    def test_presortスクリプト(self) -> None:
        result = parse_script_params(None, "PreSort:param")
        assert result is not None
        assert result["script.presort"] == "PreSort"
        assert result["script.presort.param"] == "param"

    def test_prerequestスクリプト(self) -> None:
        result = parse_script_params(None, None, "PreReq")
        assert result is not None
        assert result["script.prerequest"] == "PreReq"

    def test_全種類のスクリプト指定(self) -> None:
        result = parse_script_params("Main:p1", "PreSort:p2", "PreReq:p3")
        assert result is not None
        assert result["script"] == "Main"
        assert result["script.param"] == "p1"
        assert result["script.presort"] == "PreSort"
        assert result["script.presort.param"] == "p2"
        assert result["script.prerequest"] == "PreReq"
        assert result["script.prerequest.param"] == "p3"

    def test_スクリプト名が空だとValueError(self) -> None:
        with pytest.raises(ValueError, match="スクリプト名が空です"):
            parse_script_params(":param")


# ===========================================================================
# resolve_query
# ===========================================================================


class TestResolveQuery:
    """resolve_query のテスト."""

    def test_JSONオブジェクト文字列をリストに変換(self) -> None:
        result = resolve_query('{"Name": "Alice"}', None)
        assert result == [{"Name": "Alice"}]

    def test_JSON配列文字列をそのまま返す(self) -> None:
        result = resolve_query('[{"Name": "Alice"}, {"Name": "Bob"}]', None)
        assert result == [{"Name": "Alice"}, {"Name": "Bob"}]

    def test_無効なJSONでValueError(self) -> None:
        with pytest.raises(ValueError):
            resolve_query("not-json", None)

    def test_JSONの型が不正だとValueError(self) -> None:
        with pytest.raises(ValueError, match="JSON object or array"):
            resolve_query('"just a string"', None)

    def test_queryもquery_fileもNoneだとValueError(self) -> None:
        with pytest.raises(ValueError, match="--query または --query-file"):
            resolve_query(None, None)

    def test_ファイルからクエリを読み込み(self, tmp_path: Any) -> None:
        query_file = tmp_path / "query.json"
        query_file.write_text('{"Name": "Alice"}')

        result = resolve_query(None, str(query_file))
        assert result == [{"Name": "Alice"}]

    def test_ファイルパスの先頭アットマークを除去(self, tmp_path: Any) -> None:
        query_file = tmp_path / "query.json"
        query_file.write_text('[{"Name": "Alice"}]')

        result = resolve_query(None, f"@{query_file}")
        assert result == [{"Name": "Alice"}]

    def test_json拡張子でないファイルはValueError(self, tmp_path: Any) -> None:
        query_file = tmp_path / "query.txt"
        query_file.write_text('{"Name": "Alice"}')

        with pytest.raises(ValueError, match=".json"):
            resolve_query(None, str(query_file))

    def test_存在しないファイルでValueError(self) -> None:
        with pytest.raises(ValueError, match="クエリファイルが見つかりません"):
            resolve_query(None, "/nonexistent/query.json")

    def test_query_fileが優先される(self, tmp_path: Any) -> None:
        """query と query_file が両方指定された場合、query_file が優先."""
        query_file = tmp_path / "query.json"
        query_file.write_text('{"from": "file"}')

        result = resolve_query('{"from": "string"}', str(query_file))
        assert result == [{"from": "file"}]

    def test_utf8ファイルを読み込める(self, tmp_path: Any) -> None:
        query_file = tmp_path / "query.json"
        query_file.write_text('{"Name": "田中太郎"}', encoding="utf-8")

        result = resolve_query(None, str(query_file))
        assert result == [{"Name": "田中太郎"}]

    def test_cp932ファイルにフォールバック(self, tmp_path: Any) -> None:
        """旧バージョンが CP932 で書いたファイルも読み込める."""
        query_file = tmp_path / "query.json"
        query_file.write_bytes('{"Name": "田中太郎"}'.encode("cp932"))

        result = resolve_query(None, str(query_file))
        assert result == [{"Name": "田中太郎"}]

    def test_bom付きutf8ファイルを読み込める(self, tmp_path: Any) -> None:
        """Windows メモ帳等が出力する BOM 付き UTF-8 も読み込める."""
        query_file = tmp_path / "query.json"
        query_file.write_bytes(b"\xef\xbb\xbf" + '{"Name": "田中太郎"}'.encode())

        result = resolve_query(None, str(query_file))
        assert result == [{"Name": "田中太郎"}]


# ===========================================================================
# build_portal_get_params
# ===========================================================================


class TestBuildPortalGetParams:
    """build_portal_get_params のテスト."""

    def test_ポータル名のみ(self) -> None:
        portal_params: dict[str, Any] = {"portal": ["Orders"]}
        result = build_portal_get_params(portal_params)

        assert result["portal"] == json.dumps(["Orders"])
        assert len(result) == 1

    def test_limitとoffset付き(self) -> None:
        portal_params: dict[str, Any] = {
            "portal": ["Orders"],
            "limit.Orders": "10",
            "offset.Orders": "5",
        }
        result = build_portal_get_params(portal_params)

        assert result["portal"] == json.dumps(["Orders"])
        assert result["_limit.Orders"] == "10"
        assert result["_offset.Orders"] == "5"

    def test_複数ポータル(self) -> None:
        portal_params: dict[str, Any] = {
            "portal": ["Orders", "Items"],
            "limit.Orders": "10",
            "limit.Items": "5",
        }
        result = build_portal_get_params(portal_params)

        assert result["portal"] == json.dumps(["Orders", "Items"])
        assert result["_limit.Orders"] == "10"
        assert result["_limit.Items"] == "5"


# ===========================================================================
# build_portal_post_body
# ===========================================================================


class TestBuildPortalPostBody:
    """build_portal_post_body のテスト."""

    def test_ポータル名のみ(self) -> None:
        portal_params: dict[str, Any] = {"portal": ["Orders"]}
        result = build_portal_post_body(portal_params)

        assert result["portal"] == ["Orders"]
        assert len(result) == 1

    def test_limitとoffsetがintに変換される(self) -> None:
        portal_params: dict[str, Any] = {
            "portal": ["Orders"],
            "limit.Orders": "10",
            "offset.Orders": "5",
        }
        result = build_portal_post_body(portal_params)

        assert result["portal"] == ["Orders"]
        assert result["limit.Orders"] == 10
        assert result["offset.Orders"] == 5
        assert isinstance(result["limit.Orders"], int)
        assert isinstance(result["offset.Orders"], int)

    def test_複数ポータルのlimit(self) -> None:
        portal_params: dict[str, Any] = {
            "portal": ["Orders", "Items"],
            "limit.Orders": "10",
            "limit.Items": "20",
        }
        result = build_portal_post_body(portal_params)

        assert result["portal"] == ["Orders", "Items"]
        assert result["limit.Orders"] == 10
        assert result["limit.Items"] == 20
