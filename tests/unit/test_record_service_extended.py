"""record_service の拡張テスト.

get_record / list_records / find_records の追加シナリオをカバーする。
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from fmcli.services import record_service
from fmcli.services.record_service import (
    _extract_records,
    _extract_script_results,
    _filter_record_fields,
)
from tests.unit.helpers import make_api_info as _api_info
from tests.unit.helpers import make_fm_response as _fm_response
from tests.unit.helpers import make_profile as _profile

# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------


_RECORD_ALICE = {
    "fieldData": {"Name": "Alice"},
    "portalData": {},
    "recordId": "1",
    "modId": "0",
}

_RECORD_WITH_PORTAL = {
    "fieldData": {"Name": "Alice", "Age": "30"},
    "portalData": {
        "Orders": [
            {"OrderID": "101", "Product": "Piano"},
            {"OrderID": "102", "Product": "Guitar"},
        ],
        "Addresses": [
            {"City": "Tokyo", "Zip": "100-0001"},
        ],
    },
    "recordId": "1",
    "modId": "0",
}


# ===========================================================================
# get_record 拡張テスト
# ===========================================================================


class TestGetRecordExtended:
    """get_record の追加シナリオ."""

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_fields指定がresponse_fieldsとして使われる(self, mock_call: Any) -> None:
        """fields を渡すと内部で response_fields が API に渡る."""
        mock_call.return_value = (
            _fm_response(
                data=[
                    {
                        "fieldData": {"Name": "Alice", "Email": "alice@example.com"},
                        "portalData": {},
                        "recordId": "1",
                        "modId": "0",
                    }
                ],
            ),
            _api_info(),
        )

        envelope = record_service.get_record(_profile(), "Contacts", 1, fields="Name,Email")

        assert envelope.data is not None
        assert envelope.data["fieldData"]["Name"] == "Alice"
        mock_call.assert_called_once()

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_ポータルデータを含むレコードの取得(self, mock_call: Any) -> None:
        """ポータルデータが含まれるレスポンスを正しく返す."""
        mock_call.return_value = (
            _fm_response(data=[_RECORD_WITH_PORTAL]),
            _api_info(),
        )

        envelope = record_service.get_record(_profile(), "Contacts", 1, portal="Orders:10")

        assert envelope.data is not None
        assert "Orders" in envelope.data["portalData"]
        assert len(envelope.data["portalData"]["Orders"]) == 2
        assert envelope.data["portalData"]["Orders"][0]["Product"] == "Piano"

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_presortスクリプト指定(self, mock_call: Any) -> None:
        mock_call.return_value = (
            _fm_response(
                data=[_RECORD_ALICE],
                extra_response={
                    "scriptResult.presort": "presort-done",
                    "scriptError.presort": "0",
                },
            ),
            _api_info(),
        )

        envelope = record_service.get_record(
            _profile(), "Contacts", 1, script_presort="PreSortScript:param"
        )

        assert envelope.script_results is not None
        assert envelope.script_results["scriptResult.presort"] == "presort-done"
        assert envelope.messages == []

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_prerequestスクリプト指定(self, mock_call: Any) -> None:
        mock_call.return_value = (
            _fm_response(
                data=[_RECORD_ALICE],
                extra_response={
                    "scriptResult.prerequest": "prereq-done",
                    "scriptError.prerequest": "0",
                },
            ),
            _api_info(),
        )

        envelope = record_service.get_record(
            _profile(), "Contacts", 1, script_prerequest="PreReqScript"
        )

        assert envelope.script_results is not None
        assert envelope.script_results["scriptResult.prerequest"] == "prereq-done"

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_全スクリプトパラメータを同時指定(self, mock_call: Any) -> None:
        mock_call.return_value = (
            _fm_response(
                data=[_RECORD_ALICE],
                extra_response={
                    "scriptResult": "main-ok",
                    "scriptError": "0",
                    "scriptResult.presort": "pre-ok",
                    "scriptError.presort": "0",
                    "scriptResult.prerequest": "req-ok",
                    "scriptError.prerequest": "0",
                },
            ),
            _api_info(),
        )

        envelope = record_service.get_record(
            _profile(),
            "Contacts",
            1,
            script="MainScript",
            script_presort="PreSort",
            script_prerequest="PreReq",
        )

        assert envelope.script_results is not None
        assert len(envelope.script_results) == 6
        assert envelope.messages == []

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_layoutがenvelopeに設定される(self, mock_call: Any) -> None:
        mock_call.return_value = (
            _fm_response(
                data=[_RECORD_ALICE],
            ),
            _api_info(),
        )

        envelope = record_service.get_record(_profile(), "日本語レイアウト", 1)

        assert envelope.layout == "日本語レイアウト"


# ===========================================================================
# list_records 拡張テスト
# ===========================================================================


class TestListRecordsExtended:
    """list_records の追加シナリオ."""

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_大きなoffsetとlimit(self, mock_call: Any) -> None:
        mock_call.return_value = (
            _fm_response(
                data_info={"totalRecordCount": 10000, "foundCount": 10000, "returnedCount": 2},
            ),
            _api_info(),
        )

        envelope = record_service.list_records(_profile(), "Contacts", offset=5000, limit=500)

        assert envelope.pagination is not None
        assert envelope.pagination.offset == 5000
        assert envelope.pagination.limit == 500
        assert envelope.pagination.total_count == 10000

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_複数フィールドのsort(self, mock_call: Any) -> None:
        """sort="Name:ascend,Age:descend" を渡すと call_with_refresh が呼ばれる."""
        mock_call.return_value = (_fm_response(), _api_info())

        envelope = record_service.list_records(
            _profile(), "Contacts", sort="Name:ascend,Age:descend"
        )

        assert envelope.command == "record list"
        mock_call.assert_called_once()

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_fields指定でクライアント側フィルタが適用される(self, mock_call: Any) -> None:
        """list_records では fields はクライアント側フィルタとして適用される."""
        mock_call.return_value = (_fm_response(), _api_info())

        envelope = record_service.list_records(_profile(), "Contacts", fields="Name")

        # fieldData が Name のみに絞られている
        assert envelope.data[0]["fieldData"] == {"Name": "Alice"}
        assert envelope.data[1]["fieldData"] == {"Name": "Bob"}

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_fields指定で複数フィールドのクライアント側フィルタ(self, mock_call: Any) -> None:
        """list_records で複数フィールドを指定した場合のクライアント側フィルタ."""
        mock_call.return_value = (_fm_response(), _api_info())

        envelope = record_service.list_records(_profile(), "Contacts", fields="Name,Email")

        assert envelope.data[0]["fieldData"] == {"Name": "Alice", "Email": "alice@example.com"}
        assert "Age" not in envelope.data[0]["fieldData"]

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_fields未指定で全フィールドが返る(self, mock_call: Any) -> None:
        """list_records で fields を指定しない場合は全フィールドが返る."""
        mock_call.return_value = (_fm_response(), _api_info())

        envelope = record_service.list_records(_profile(), "Contacts")

        assert envelope.data[0]["fieldData"]["Email"] == "alice@example.com"
        assert envelope.data[0]["fieldData"]["Name"] == "Alice"
        assert envelope.data[0]["fieldData"]["Age"] == "30"

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_ポータルとスクリプトを同時に指定(self, mock_call: Any) -> None:
        mock_call.return_value = (
            _fm_response(
                extra_response={"scriptResult": "combo", "scriptError": "0"},
            ),
            _api_info(),
        )

        envelope = record_service.list_records(
            _profile(),
            "Contacts",
            portal="Orders:5:1",
            script="ComboScript:param",
        )

        assert envelope.script_results is not None
        assert envelope.script_results["scriptResult"] == "combo"

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_スクリプトエラー時のメッセージ(self, mock_call: Any) -> None:
        mock_call.return_value = (
            _fm_response(
                extra_response={"scriptResult": "", "scriptError": "212"},
            ),
            _api_info(),
        )

        envelope = record_service.list_records(_profile(), "Contacts", script="ErrorScript")

        assert len(envelope.messages) == 1
        assert "212" in envelope.messages[0]

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_presortとprerequestスクリプト指定(self, mock_call: Any) -> None:
        mock_call.return_value = (
            _fm_response(
                extra_response={
                    "scriptResult": "main",
                    "scriptError": "0",
                    "scriptResult.presort": "presort-ok",
                    "scriptError.presort": "0",
                    "scriptResult.prerequest": "prereq-ok",
                    "scriptError.prerequest": "0",
                },
            ),
            _api_info(),
        )

        envelope = record_service.list_records(
            _profile(),
            "Contacts",
            script="Main",
            script_presort="PreSort",
            script_prerequest="PreReq",
        )

        assert envelope.script_results is not None
        assert len(envelope.script_results) == 6


# ===========================================================================
# find_records 拡張テスト
# ===========================================================================


class TestFindRecordsExtended:
    """find_records の追加シナリオ."""

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_JSON配列クエリでOR検索(self, mock_call: Any) -> None:
        """query が JSON 配列（OR 条件）の場合も正しく動作する."""
        mock_call.return_value = (_fm_response(), _api_info(method="POST"))

        envelope = record_service.find_records(
            _profile(),
            "Contacts",
            query='[{"Name": "Alice"}, {"Name": "Bob"}]',
        )

        assert envelope.command == "record find"
        assert len(envelope.data) == 2
        # OR クエリが call_with_refresh に渡されたことを検証
        mock_call.assert_called_once()

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_count_onlyモードでpagination情報が含まれる(self, mock_call: Any) -> None:
        mock_call.return_value = (
            _fm_response(
                data_info={"totalRecordCount": 1000, "foundCount": 123, "returnedCount": 2},
            ),
            _api_info(method="POST"),
        )

        envelope = record_service.find_records(
            _profile(),
            "Contacts",
            query='{"Status": "Active"}',
            count_only=True,
        )

        assert envelope.command == "record find --count"
        assert envelope.data == {"found_count": 123}
        assert envelope.pagination is not None
        assert envelope.pagination.total_count == 1000
        assert envelope.pagination.found_count == 123

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_count_onlyでもoffset_limitが反映される(self, mock_call: Any) -> None:
        mock_call.return_value = (
            _fm_response(
                data_info={"totalRecordCount": 500, "foundCount": 50, "returnedCount": 10},
            ),
            _api_info(method="POST"),
        )

        envelope = record_service.find_records(
            _profile(),
            "Contacts",
            query='{"Status": "Active"}',
            count_only=True,
            offset=20,
            limit=10,
        )

        assert envelope.pagination is not None
        assert envelope.pagination.offset == 20
        assert envelope.pagination.limit == 10

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_存在しないフィールドを指定するとfieldDataが空(self, mock_call: Any) -> None:
        mock_call.return_value = (_fm_response(), _api_info(method="POST"))

        envelope = record_service.find_records(
            _profile(),
            "Contacts",
            query='{"Name": "Alice"}',
            fields="NonExistent,AlsoMissing",
        )

        assert envelope.data[0]["fieldData"] == {}
        assert envelope.data[1]["fieldData"] == {}

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_複数フィールドのfields指定(self, mock_call: Any) -> None:
        mock_call.return_value = (_fm_response(), _api_info(method="POST"))

        envelope = record_service.find_records(
            _profile(),
            "Contacts",
            query='{"Name": "Alice"}',
            fields="Name,Age",
        )

        assert envelope.data[0]["fieldData"] == {"Name": "Alice", "Age": "30"}
        # Email は除外されている
        assert "Email" not in envelope.data[0]["fieldData"]

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_ポータルデータはfields指定に影響されない(self, mock_call: Any) -> None:
        """fields でフィルタしても portalData はそのまま残る."""
        mock_call.return_value = (
            _fm_response(
                data=[_RECORD_WITH_PORTAL],
            ),
            _api_info(method="POST"),
        )

        envelope = record_service.find_records(
            _profile(),
            "Contacts",
            query='{"Name": "Alice"}',
            fields="Name",
        )

        assert envelope.data[0]["fieldData"] == {"Name": "Alice"}
        # portalData は維持される
        assert "Orders" in envelope.data[0]["portalData"]
        assert len(envelope.data[0]["portalData"]["Orders"]) == 2

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_queryFileによる検索(self, mock_call: Any, tmp_path: Any) -> None:
        """query_file パラメータでファイルからクエリを読み込む."""
        query_file = tmp_path / "query.json"
        query_file.write_text('{"Name": "Alice"}')

        mock_call.return_value = (_fm_response(), _api_info(method="POST"))

        envelope = record_service.find_records(
            _profile(),
            "Contacts",
            query_file=str(query_file),
        )

        assert envelope.command == "record find"
        mock_call.assert_called_once()

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_複数のスクリプトエラーが全てメッセージに含まれる(self, mock_call: Any) -> None:
        mock_call.return_value = (
            _fm_response(
                extra_response={
                    "scriptResult": "",
                    "scriptError": "100",
                    "scriptResult.presort": "",
                    "scriptError.presort": "200",
                    "scriptResult.prerequest": "",
                    "scriptError.prerequest": "300",
                },
            ),
            _api_info(method="POST"),
        )

        envelope = record_service.find_records(
            _profile(),
            "Contacts",
            query='{"Name": "Alice"}',
            script="Main",
            script_presort="PreSort",
            script_prerequest="PreReq",
        )

        assert len(envelope.messages) == 3
        assert any("100" in m for m in envelope.messages)
        assert any("200" in m for m in envelope.messages)
        assert any("300" in m for m in envelope.messages)


# ===========================================================================
# _filter_record_fields エッジケース
# ===========================================================================


class TestFilterRecordFieldsEdgeCases:
    """_filter_record_fields の追加エッジケーステスト."""

    def test_空のfieldsリストはフィルタなし扱い(self) -> None:
        """空リスト [] は falsy なので `if not fields` ガードでフィルタされない."""
        records = [
            {
                "fieldData": {"Name": "Alice", "Age": "30"},
                "portalData": {},
                "recordId": "1",
                "modId": "0",
            }
        ]
        result = _filter_record_fields(records, [])

        # 空リストは falsy なのでフィルタされず、レコードがそのまま返る
        assert result is records

    def test_部分一致するフィールドのみ残る(self) -> None:
        """指定したフィールドのうち存在するものだけ残る."""
        records = [
            {
                "fieldData": {"Name": "Alice", "Age": "30", "Email": "alice@example.com"},
                "portalData": {},
                "recordId": "1",
                "modId": "0",
            }
        ]
        result = _filter_record_fields(records, ["Name", "Phone"])

        assert result[0]["fieldData"] == {"Name": "Alice"}

    def test_元のレコードが変更されない(self) -> None:
        """フィルタは元のレコードを変更しないことを確認."""
        records = [
            {
                "fieldData": {"Name": "Alice", "Age": "30"},
                "portalData": {},
                "recordId": "1",
                "modId": "0",
            }
        ]
        _filter_record_fields(records, ["Name"])

        # 元のレコードは変更されていない
        assert "Age" in records[0]["fieldData"]


# ===========================================================================
# _extract_records エッジケース
# ===========================================================================


class TestExtractRecordsEdgeCases:
    """_extract_records の追加エッジケーステスト."""

    def test_dataInfoにtotalRecordCountのみ(self) -> None:
        body = {
            "response": {
                "data": [{"fieldData": {"X": "1"}}],
                "dataInfo": {"totalRecordCount": 50},
            }
        }
        data, pagination = _extract_records(body)

        assert pagination.total_count == 50
        assert pagination.found_count == 0
        assert pagination.returned_count == 1  # len(data) がデフォルト

    def test_大量レコードのページネーション(self) -> None:
        body = _fm_response(
            data_info={
                "totalRecordCount": 50000,
                "foundCount": 12345,
                "returnedCount": 100,
            },
        )
        data, pagination = _extract_records(body)

        assert pagination.total_count == 50000
        assert pagination.found_count == 12345
        assert pagination.returned_count == 100


# ===========================================================================
# _extract_script_results エッジケース
# ===========================================================================


class TestExtractScriptResultsEdgeCases:
    """_extract_script_results の追加テスト."""

    def test_scriptResultのみでscriptErrorなし(self) -> None:
        body = _fm_response(
            extra_response={"scriptResult": "some-value"},
        )
        result = _extract_script_results(body)

        assert result is not None
        assert result["scriptResult"] == "some-value"
        assert "scriptError" not in result

    def test_scriptErrorのみでscriptResultなし(self) -> None:
        body = _fm_response(
            extra_response={"scriptError": "100"},
        )
        result = _extract_script_results(body)

        assert result is not None
        assert result["scriptError"] == "100"
        assert "scriptResult" not in result

    def test_responseが空dictの場合(self) -> None:
        body: dict[str, Any] = {"response": {}}
        result = _extract_script_results(body)

        assert result is None


# ===========================================================================
# エラーケーステスト
# ===========================================================================


class TestRecordServiceErrors:
    """record_service のエラー系テスト."""

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_find_recordsでqueryもquery_fileもなしはエラー(self, mock_call: Any) -> None:
        """query と query_file が両方 None の場合は ValueError."""
        with pytest.raises(ValueError, match="--query または --query-file"):
            record_service.find_records(_profile(), "Contacts")

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_find_recordsで不正なJSON(self, mock_call: Any) -> None:
        """不正な JSON 文字列を渡すと ValueError."""
        with pytest.raises(ValueError):
            record_service.find_records(_profile(), "Contacts", query="invalid-json")
