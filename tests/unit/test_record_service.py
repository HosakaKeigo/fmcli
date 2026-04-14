"""record_service の全機能テスト."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from fmcli.core.errors import ApiError
from fmcli.domain.envelopes import Envelope
from fmcli.services import record_service
from fmcli.services.record_service import (
    _attach_script_results,
    _extract_records,
    _extract_script_results,
    _filter_record_fields,
    _parse_fields,
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

_RECORD_ALICE_PORTAL = {
    "fieldData": {"Name": "Alice"},
    "portalData": {"Orders": []},
    "recordId": "1",
    "modId": "0",
}


# ===========================================================================
# _extract_records
# ===========================================================================


class TestExtractRecords:
    """_extract_records のテスト."""

    def test_正常なレスポンスからデータとページネーションを抽出(self) -> None:
        body = _fm_response()
        data, pagination = _extract_records(body)

        assert len(data) == 2
        assert data[0]["fieldData"]["Name"] == "Alice"
        assert pagination.total_count == 100
        assert pagination.found_count == 50
        assert pagination.returned_count == 2

    def test_空のデータ(self) -> None:
        body = _fm_response(
            data=[],
            data_info={"totalRecordCount": 0, "foundCount": 0, "returnedCount": 0},
        )
        data, pagination = _extract_records(body)

        assert data == []
        assert pagination.total_count == 0
        assert pagination.found_count == 0
        assert pagination.returned_count == 0

    def test_dataInfoが存在しない場合のデフォルト値(self) -> None:
        body = {"response": {"data": [{"fieldData": {"X": "1"}}]}}
        data, pagination = _extract_records(body)

        assert len(data) == 1
        assert pagination.total_count == 0
        assert pagination.found_count == 0
        # returned_count は len(data) がデフォルト
        assert pagination.returned_count == 1

    def test_responseキー自体が存在しない場合(self) -> None:
        body: dict[str, Any] = {}
        data, pagination = _extract_records(body)

        assert data == []
        assert pagination.total_count == 0
        assert pagination.returned_count == 0


# ===========================================================================
# _extract_script_results
# ===========================================================================


class TestExtractScriptResults:
    """_extract_script_results のテスト."""

    def test_スクリプト結果あり(self) -> None:
        body = _fm_response(
            extra_response={
                "scriptResult": "OK",
                "scriptError": "0",
            },
        )
        result = _extract_script_results(body)

        assert result is not None
        assert result["scriptResult"] == "OK"
        assert result["scriptError"] == "0"

    def test_スクリプト結果なし(self) -> None:
        body = _fm_response()
        result = _extract_script_results(body)

        assert result is None

    def test_presortスクリプト結果(self) -> None:
        body = _fm_response(
            extra_response={
                "scriptResult.presort": "presort-ok",
                "scriptError.presort": "0",
            },
        )
        result = _extract_script_results(body)

        assert result is not None
        assert result["scriptResult.presort"] == "presort-ok"
        assert result["scriptError.presort"] == "0"

    def test_prerequestスクリプト結果(self) -> None:
        body = _fm_response(
            extra_response={
                "scriptResult.prerequest": "prereq-result",
                "scriptError.prerequest": "100",
            },
        )
        result = _extract_script_results(body)

        assert result is not None
        assert result["scriptResult.prerequest"] == "prereq-result"
        assert result["scriptError.prerequest"] == "100"

    def test_全種類のスクリプト結果(self) -> None:
        body = _fm_response(
            extra_response={
                "scriptResult": "main",
                "scriptError": "0",
                "scriptResult.presort": "pre",
                "scriptError.presort": "0",
                "scriptResult.prerequest": "req",
                "scriptError.prerequest": "0",
            },
        )
        result = _extract_script_results(body)

        assert result is not None
        assert len(result) == 6


# ===========================================================================
# _attach_script_results
# ===========================================================================


class TestAttachScriptResults:
    """_attach_script_results のテスト."""

    def _envelope(self) -> Envelope:
        return Envelope(command="test", profile="test", database="TestDB")

    def test_scriptErrorがゼロならメッセージなし(self) -> None:
        env = self._envelope()
        _attach_script_results(env, {"scriptError": "0", "scriptResult": "OK"})

        assert env.script_results is not None
        assert env.messages == []

    def test_scriptErrorが非ゼロならエラーメッセージ追加(self) -> None:
        env = self._envelope()
        _attach_script_results(env, {"scriptError": "401", "scriptResult": ""})

        assert len(env.messages) == 1
        assert "スクリプトエラー" in env.messages[0]
        assert "401" in env.messages[0]

    def test_presortエラー(self) -> None:
        env = self._envelope()
        _attach_script_results(env, {"scriptError.presort": "500"})

        assert len(env.messages) == 1
        assert "scriptError.presort" in env.messages[0]

    def test_複数のスクリプトエラー(self) -> None:
        env = self._envelope()
        _attach_script_results(
            env,
            {
                "scriptError": "100",
                "scriptError.presort": "200",
                "scriptError.prerequest": "300",
            },
        )

        assert len(env.messages) == 3

    def test_Noneを渡しても問題なし(self) -> None:
        env = self._envelope()
        _attach_script_results(env, None)

        assert env.script_results is None
        assert env.messages == []

    def test_空dictを渡しても問題なし(self) -> None:
        env = self._envelope()
        _attach_script_results(env, {})

        # 空 dict は falsy なので何もしない
        assert env.script_results is None
        assert env.messages == []


# ===========================================================================
# _parse_fields
# ===========================================================================


class TestParseFields:
    """_parse_fields のテスト."""

    def test_Noneを渡すとNone(self) -> None:
        assert _parse_fields(None) is None

    def test_カンマ区切りをリスト変換(self) -> None:
        assert _parse_fields("Name,Email") == ["Name", "Email"]

    def test_空文字列はNone(self) -> None:
        assert _parse_fields("") is None

    def test_スペースを含む入力のトリミング(self) -> None:
        assert _parse_fields("Name , Email ") == ["Name", "Email"]

    def test_単一フィールド(self) -> None:
        assert _parse_fields("Name") == ["Name"]

    def test_末尾カンマの空要素を除外(self) -> None:
        assert _parse_fields("Name,Email,") == ["Name", "Email"]


# ===========================================================================
# _filter_record_fields
# ===========================================================================


class TestFilterRecordFields:
    """_filter_record_fields のテスト."""

    RECORDS = [
        {
            "fieldData": {"Name": "Alice", "Age": "30", "Email": "alice@example.com"},
            "portalData": {"Orders": [{"OrderID": "1"}]},
            "recordId": "1",
            "modId": "0",
        },
        {
            "fieldData": {"Name": "Bob", "Age": "25", "Email": "bob@example.com"},
            "portalData": {},
            "recordId": "2",
            "modId": "1",
        },
    ]

    def test_fieldsがNoneならレコードそのまま(self) -> None:
        result = _filter_record_fields(self.RECORDS, None)
        assert result is self.RECORDS

    def test_指定フィールドのみに絞る(self) -> None:
        result = _filter_record_fields(self.RECORDS, ["Name"])

        assert result[0]["fieldData"] == {"Name": "Alice"}
        assert result[1]["fieldData"] == {"Name": "Bob"}

    def test_portalDataとrecordIdとmodIdは維持(self) -> None:
        result = _filter_record_fields(self.RECORDS, ["Name"])

        assert result[0]["portalData"] == {"Orders": [{"OrderID": "1"}]}
        assert result[0]["recordId"] == "1"
        assert result[0]["modId"] == "0"

    def test_複数フィールド指定(self) -> None:
        result = _filter_record_fields(self.RECORDS, ["Name", "Email"])

        assert result[0]["fieldData"] == {"Name": "Alice", "Email": "alice@example.com"}

    def test_fieldDataがdictでないレコードはそのまま(self) -> None:
        records: list[Any] = [{"fieldData": "not-a-dict", "recordId": "1"}]
        result = _filter_record_fields(records, ["Name"])

        assert result[0]["fieldData"] == "not-a-dict"

    def test_レコードがdictでない場合はそのまま(self) -> None:
        records: list[Any] = ["not-a-dict-record"]
        result = _filter_record_fields(records, ["Name"])

        assert result == ["not-a-dict-record"]

    def test_空リスト(self) -> None:
        result = _filter_record_fields([], ["Name"])
        assert result == []

    def test_存在しないフィールドを指定するとfieldDataが空になる(self) -> None:
        result = _filter_record_fields(self.RECORDS, ["NonExistent"])

        assert result[0]["fieldData"] == {}


# ===========================================================================
# get_record
# ===========================================================================


class TestGetRecord:
    """get_record のテスト."""

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_正常取得(self, mock_call: Any) -> None:
        mock_call.return_value = (
            _fm_response(
                data=[
                    {
                        "fieldData": {"Name": "Alice"},
                        "portalData": {},
                        "recordId": "1",
                        "modId": "0",
                    }
                ],
            ),
            _api_info(),
        )

        envelope = record_service.get_record(_profile(), "Contacts", 1)

        assert envelope.command == "record get"
        assert envelope.data["fieldData"]["Name"] == "Alice"
        assert envelope.database == "TestDB"

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_dataが空の場合Noneを返す(self, mock_call: Any) -> None:
        mock_call.return_value = (
            _fm_response(
                data=[],
                data_info={"totalRecordCount": 0, "foundCount": 0, "returnedCount": 0},
            ),
            _api_info(),
        )

        envelope = record_service.get_record(_profile(), "Contacts", 999)

        assert envelope.data is None

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_ポータル指定あり(self, mock_call: Any) -> None:
        mock_call.return_value = (
            _fm_response(
                data=[_RECORD_ALICE_PORTAL],
            ),
            _api_info(),
        )

        envelope = record_service.get_record(_profile(), "Contacts", 1, portal="Orders:10")

        assert envelope.data is not None
        # call_with_refresh が呼ばれたことを確認
        mock_call.assert_called_once()

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_スクリプト指定あり(self, mock_call: Any) -> None:
        mock_call.return_value = (
            _fm_response(
                data=[_RECORD_ALICE],
                extra_response={"scriptResult": "done", "scriptError": "0"},
            ),
            _api_info(),
        )

        envelope = record_service.get_record(_profile(), "Contacts", 1, script="MyScript:param1")

        assert envelope.script_results is not None
        assert envelope.script_results["scriptResult"] == "done"
        assert envelope.messages == []

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_スクリプトエラーがある場合(self, mock_call: Any) -> None:
        mock_call.return_value = (
            _fm_response(
                data=[_RECORD_ALICE],
                extra_response={"scriptResult": "", "scriptError": "100"},
            ),
            _api_info(),
        )

        envelope = record_service.get_record(_profile(), "Contacts", 1, script="FailScript")

        assert len(envelope.messages) == 1
        assert "100" in envelope.messages[0]

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_fields指定(self, mock_call: Any) -> None:
        """fields は response_fields として API に渡される."""
        mock_call.return_value = (
            _fm_response(
                data=[_RECORD_ALICE],
            ),
            _api_info(),
        )

        record_service.get_record(_profile(), "Contacts", 1, fields="Name,Email")

        # call_with_refresh に渡されたコールバック関数を検証
        mock_call.assert_called_once()

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_profileのprofile_keyが反映される(self, mock_call: Any) -> None:
        mock_call.return_value = (
            _fm_response(
                data=[_RECORD_ALICE],
            ),
            _api_info(),
        )

        envelope = record_service.get_record(_profile(), "Contacts", 1)

        assert envelope.profile == "https://fm.example.com|TestDB"


# ===========================================================================
# list_records
# ===========================================================================


class TestListRecords:
    """list_records のテスト."""

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_正常取得(self, mock_call: Any) -> None:
        mock_call.return_value = (_fm_response(), _api_info())

        envelope = record_service.list_records(_profile(), "Contacts")

        assert envelope.command == "record list"
        assert len(envelope.data) == 2
        assert envelope.pagination is not None
        assert envelope.pagination.total_count == 100
        assert envelope.pagination.found_count == 50
        assert envelope.pagination.returned_count == 2

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_offset_limitがpaginationに反映(self, mock_call: Any) -> None:
        mock_call.return_value = (_fm_response(), _api_info())

        envelope = record_service.list_records(_profile(), "Contacts", offset=10, limit=25)

        assert envelope.pagination is not None
        assert envelope.pagination.offset == 10
        assert envelope.pagination.limit == 25

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_sort指定あり(self, mock_call: Any) -> None:
        mock_call.return_value = (_fm_response(), _api_info())

        envelope = record_service.list_records(_profile(), "Contacts", sort="Name:ascend")

        assert envelope.command == "record list"
        mock_call.assert_called_once()

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_ポータル指定あり(self, mock_call: Any) -> None:
        mock_call.return_value = (_fm_response(), _api_info())

        envelope = record_service.list_records(_profile(), "Contacts", portal="Orders:10:2")

        assert envelope.data is not None
        mock_call.assert_called_once()

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_スクリプト指定あり(self, mock_call: Any) -> None:
        mock_call.return_value = (
            _fm_response(
                extra_response={"scriptResult": "listed", "scriptError": "0"},
            ),
            _api_info(),
        )

        envelope = record_service.list_records(_profile(), "Contacts", script="ListScript")

        assert envelope.script_results is not None
        assert envelope.script_results["scriptResult"] == "listed"

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_空レコード(self, mock_call: Any) -> None:
        mock_call.return_value = (
            _fm_response(
                data=[],
                data_info={"totalRecordCount": 0, "foundCount": 0, "returnedCount": 0},
            ),
            _api_info(),
        )

        envelope = record_service.list_records(_profile(), "Contacts")

        assert envelope.data == []
        assert envelope.pagination is not None
        assert envelope.pagination.total_count == 0

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_0件レコードのenvelopeとpagination(self, mock_call: Any) -> None:
        """API が 0 件を返した場合、data は空リストで pagination.returned_count が 0."""
        mock_call.return_value = (
            _fm_response(
                data=[],
                data_info={"totalRecordCount": 50, "foundCount": 0, "returnedCount": 0},
            ),
            _api_info(),
        )

        envelope = record_service.list_records(_profile(), "Contacts")

        assert envelope.ok is True
        assert envelope.command == "record list"
        assert envelope.data == []
        assert envelope.pagination is not None
        assert envelope.pagination.returned_count == 0
        assert envelope.pagination.found_count == 0
        assert envelope.pagination.total_count == 50

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_デフォルトのoffset_limit(self, mock_call: Any) -> None:
        mock_call.return_value = (_fm_response(), _api_info())

        envelope = record_service.list_records(_profile(), "Contacts")

        assert envelope.pagination is not None
        assert envelope.pagination.offset == 1
        assert envelope.pagination.limit == 100

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_layoutがenvelopeに反映(self, mock_call: Any) -> None:
        mock_call.return_value = (_fm_response(), _api_info())

        envelope = record_service.list_records(_profile(), "日本語レイアウト")

        assert envelope.layout == "日本語レイアウト"


# ===========================================================================
# find_records
# ===========================================================================


class TestFindRecords:
    """find_records のテスト."""

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_正常検索(self, mock_call: Any) -> None:
        mock_call.return_value = (_fm_response(), _api_info(method="POST"))

        envelope = record_service.find_records(_profile(), "Contacts", query='{"Name": "Alice"}')

        assert envelope.command == "record find"
        assert len(envelope.data) == 2

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_count_onlyモード(self, mock_call: Any) -> None:
        mock_call.return_value = (
            _fm_response(
                data_info={"totalRecordCount": 100, "foundCount": 42, "returnedCount": 2},
            ),
            _api_info(method="POST"),
        )

        envelope = record_service.find_records(
            _profile(), "Contacts", query='{"Name": "Alice"}', count_only=True
        )

        assert envelope.command == "record find --count"
        assert envelope.data == {"found_count": 42}
        assert envelope.pagination is not None
        assert envelope.pagination.found_count == 42

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_fields指定でクライアント側フィルタ(self, mock_call: Any) -> None:
        mock_call.return_value = (_fm_response(), _api_info(method="POST"))

        envelope = record_service.find_records(
            _profile(), "Contacts", query='{"Name": "Alice"}', fields="Name"
        )

        # fieldData が Name のみに絞られている
        assert envelope.data[0]["fieldData"] == {"Name": "Alice"}
        assert envelope.data[1]["fieldData"] == {"Name": "Bob"}

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_ポータル指定あり(self, mock_call: Any) -> None:
        """find は POST なので build_portal_post_body が使われる."""
        mock_call.return_value = (_fm_response(), _api_info(method="POST"))

        envelope = record_service.find_records(
            _profile(), "Contacts", query='{"Name": "Alice"}', portal="Orders:5"
        )

        assert envelope.data is not None
        mock_call.assert_called_once()

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_スクリプト実行結果のattach(self, mock_call: Any) -> None:
        mock_call.return_value = (
            _fm_response(
                extra_response={"scriptResult": "found", "scriptError": "0"},
            ),
            _api_info(method="POST"),
        )

        envelope = record_service.find_records(
            _profile(), "Contacts", query='{"Name": "Alice"}', script="FindScript:param"
        )

        assert envelope.script_results is not None
        assert envelope.script_results["scriptResult"] == "found"
        assert envelope.messages == []

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_スクリプトエラー時のメッセージ(self, mock_call: Any) -> None:
        mock_call.return_value = (
            _fm_response(
                extra_response={"scriptResult": "", "scriptError": "500"},
            ),
            _api_info(method="POST"),
        )

        envelope = record_service.find_records(
            _profile(), "Contacts", query='{"Name": "Alice"}', script="FailScript"
        )

        assert len(envelope.messages) == 1
        assert "500" in envelope.messages[0]

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_offset_limitがpaginationに反映(self, mock_call: Any) -> None:
        mock_call.return_value = (_fm_response(), _api_info(method="POST"))

        envelope = record_service.find_records(
            _profile(), "Contacts", query='{"Name": "Alice"}', offset=5, limit=10
        )

        assert envelope.pagination is not None
        assert envelope.pagination.offset == 5
        assert envelope.pagination.limit == 10

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_sort指定あり(self, mock_call: Any) -> None:
        mock_call.return_value = (_fm_response(), _api_info(method="POST"))

        envelope = record_service.find_records(
            _profile(), "Contacts", query='{"Name": "Alice"}', sort="Name:descend"
        )

        assert envelope.command == "record find"
        mock_call.assert_called_once()

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_count_onlyでもスクリプト結果がattachされる(self, mock_call: Any) -> None:
        mock_call.return_value = (
            _fm_response(
                data_info={"totalRecordCount": 10, "foundCount": 3, "returnedCount": 2},
                extra_response={"scriptResult": "counted", "scriptError": "0"},
            ),
            _api_info(method="POST"),
        )

        envelope = record_service.find_records(
            _profile(), "Contacts", query='{"Name": "Alice"}', count_only=True, script="CountScript"
        )

        assert envelope.data == {"found_count": 3}
        assert envelope.script_results is not None
        assert envelope.script_results["scriptResult"] == "counted"

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_presortとprerequestスクリプト(self, mock_call: Any) -> None:
        mock_call.return_value = (
            _fm_response(
                extra_response={
                    "scriptResult": "main",
                    "scriptError": "0",
                    "scriptResult.presort": "pre",
                    "scriptError.presort": "0",
                    "scriptResult.prerequest": "req",
                    "scriptError.prerequest": "0",
                },
            ),
            _api_info(method="POST"),
        )

        envelope = record_service.find_records(
            _profile(),
            "Contacts",
            query='{"Name": "Alice"}',
            script="MainScript",
            script_presort="PreSort",
            script_prerequest="PreReq",
        )

        assert envelope.script_results is not None
        assert len(envelope.script_results) == 6
        assert envelope.messages == []

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_api_code_402で空配列を返す(self, mock_call: Any) -> None:
        """FileMaker api_code 402 (レコードなし) を ok=True, data=[] に正規化."""
        mock_call.side_effect = ApiError(
            "No records match the request",
            http_status=500,
            api_code=402,
        )

        envelope = record_service.find_records(
            _profile(), "Contacts", query='{"Name": "存在しない"}'
        )

        assert envelope.ok is True
        assert envelope.data == []
        assert envelope.pagination is not None
        assert envelope.pagination.found_count == 0
        assert envelope.pagination.returned_count == 0
        assert len(envelope.messages) == 1
        assert "402" in envelope.messages[0]

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_api_code_402_count_onlyで0件を返す(self, mock_call: Any) -> None:
        """api_code 402 + --count で found_count: 0 を返す."""
        mock_call.side_effect = ApiError(
            "No records match the request",
            http_status=500,
            api_code=402,
        )

        envelope = record_service.find_records(
            _profile(), "Contacts", query='{"Name": "存在しない"}', count_only=True
        )

        assert envelope.ok is True
        assert envelope.data == {"found_count": 0}
        assert envelope.command == "record find --count"
        assert envelope.pagination is not None
        assert envelope.pagination.found_count == 0

    @patch("fmcli.services.record_service.call_with_refresh")
    def test_api_code_402以外のApiErrorは再送出(self, mock_call: Any) -> None:
        """api_code 402 以外の ApiError はそのまま raise される."""
        mock_call.side_effect = ApiError(
            "Field not found",
            http_status=500,
            api_code=401,
        )

        import pytest

        with pytest.raises(ApiError) as exc_info:
            record_service.find_records(_profile(), "Contacts", query='{"BadField": "x"}')
        assert exc_info.value.api_code == 401
