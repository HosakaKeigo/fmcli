"""出力モジュールのテスト."""

from __future__ import annotations

import json
from io import StringIO
from unittest.mock import patch

import pytest

from fmcli.core.output import (
    DEFAULT_TIMEOUT,
    OutputConfig,
    _flatten_record,
    _has_portal_data,
    get_format,
    get_timeout,
    is_verbose,
    print_json,
    print_output,
    render_json,
    set_format,
    set_output_config,
    set_verbose,
)
from fmcli.domain.envelopes import ApiInfo, Envelope
from fmcli.domain.models import Pagination


def _make_envelope(**kwargs: object) -> Envelope:
    defaults: dict[str, object] = {
        "ok": True,
        "command": "test command",
        "data": {"key": "value"},
    }
    defaults.update(kwargs)
    return Envelope(**defaults)  # type: ignore[arg-type]


# ===================================================================
# render_json
# ===================================================================


class TestRenderJson:
    """render_json のテスト."""

    def setup_method(self) -> None:
        """各テスト前に verbose / format をリセットする."""
        set_verbose(False)
        set_format("json")

    def test_basic_render(self) -> None:
        """基本的な Envelope を JSON 文字列にレンダリングする."""
        envelope = _make_envelope()
        result = render_json(envelope)
        parsed = json.loads(result)
        assert parsed["ok"] is True
        assert parsed["command"] == "test command"
        assert parsed["data"]["key"] == "value"

    def test_excludes_api_when_not_verbose(self) -> None:
        """非 verbose モードでは api フィールドが除外される."""
        envelope = _make_envelope(
            api=ApiInfo(method="GET", url="https://example.com/api", duration_ms=123.4)
        )
        result = render_json(envelope)
        parsed = json.loads(result)
        assert "api" not in parsed

    def test_includes_api_when_verbose(self) -> None:
        """verbose モードでは api フィールドが含まれる."""
        set_verbose(True)
        envelope = _make_envelope(
            api=ApiInfo(method="GET", url="https://example.com/api", duration_ms=123.4)
        )
        result = render_json(envelope)
        parsed = json.loads(result)
        assert "api" in parsed
        assert parsed["api"]["method"] == "GET"
        assert parsed["api"]["duration_ms"] == 123.4

    def test_excludes_pagination_when_not_verbose(self) -> None:
        """非 verbose モードでは pagination フィールドが除外される."""
        envelope = _make_envelope(
            pagination=Pagination(
                offset=1, limit=10, total_count=100, found_count=50, returned_count=10
            )
        )
        result = render_json(envelope)
        parsed = json.loads(result)
        assert "pagination" not in parsed

    def test_includes_pagination_when_verbose(self) -> None:
        """verbose モードでは pagination フィールドが含まれる."""
        set_verbose(True)
        envelope = _make_envelope(
            pagination=Pagination(
                offset=1, limit=10, total_count=100, found_count=50, returned_count=10
            )
        )
        result = render_json(envelope)
        parsed = json.loads(result)
        assert "pagination" in parsed
        assert parsed["pagination"]["total_count"] == 100

    def test_excludes_none_fields(self) -> None:
        """None のフィールドは出力に含まれない."""
        envelope = Envelope(ok=True, command="test")
        result = render_json(envelope)
        parsed = json.loads(result)
        assert "data" not in parsed
        assert "error" not in parsed
        assert "script_results" not in parsed

    def test_output_is_indented(self) -> None:
        """出力がインデントされている."""
        envelope = _make_envelope()
        result = render_json(envelope)
        # indent=2 なので改行とスペースが含まれる
        assert "\n" in result
        assert "  " in result


# ===================================================================
# print_json
# ===================================================================


class TestPrintJson:
    """print_json のテスト."""

    def setup_method(self) -> None:
        set_verbose(False)
        set_format("json")

    def test_print_json_writes_to_stdout(self) -> None:
        """print_json は標準出力に JSON を出力する."""
        envelope = _make_envelope()
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            print_json(envelope)
            output = mock_stdout.getvalue()

        parsed = json.loads(output.strip())
        assert parsed["ok"] is True

    def test_print_json_ends_with_newline(self) -> None:
        """出力が改行で終わる."""
        envelope = _make_envelope()
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            print_json(envelope)
            output = mock_stdout.getvalue()

        assert output.endswith("\n")


# ===================================================================
# print_output (json mode)
# ===================================================================


class TestPrintOutputJson:
    """print_output の json モードのテスト."""

    def setup_method(self) -> None:
        set_verbose(False)
        set_format("json")

    def test_json_format_outputs_json(self) -> None:
        """json モードでは JSON を出力する."""
        envelope = _make_envelope(data=[{"name": "item1"}])
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            print_output(envelope)
            output = mock_stdout.getvalue()

        parsed = json.loads(output.strip())
        assert parsed["ok"] is True
        assert parsed["data"][0]["name"] == "item1"

    def test_json_format_with_non_list_data(self) -> None:
        """json モードでは非リストデータも JSON 出力する."""
        envelope = _make_envelope(data={"single": "value"})
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            print_output(envelope)
            output = mock_stdout.getvalue()

        parsed = json.loads(output.strip())
        assert parsed["data"]["single"] == "value"


# ===================================================================
# print_output (table mode)
# ===================================================================


class TestPrintOutputTable:
    """print_output の table モードのテスト."""

    def setup_method(self) -> None:
        set_verbose(False)
        set_format("table")

    def teardown_method(self) -> None:
        set_format("json")

    def test_table_format_with_list_of_dicts(self) -> None:
        """table モードでリスト of dict はテーブル表示する."""
        envelope = _make_envelope(data=[{"name": "A", "type": "1"}, {"name": "B", "type": "2"}])
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            print_output(envelope)
            output = mock_stdout.getvalue()

        # rich テーブル出力にデータが含まれる
        assert "A" in output
        assert "B" in output

    def test_table_format_with_empty_list_falls_back_to_json(self) -> None:
        """table モードで空リストの場合は JSON にフォールバックする."""
        envelope = _make_envelope(data=[])
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            print_output(envelope)
            output = mock_stdout.getvalue()

        # 空リストの場合は JSON 出力される (_print_table 内で print_json にフォールバック)
        parsed = json.loads(output.strip())
        assert parsed["ok"] is True

    def test_table_format_with_non_list_falls_back_to_json(self) -> None:
        """table モードで非リストデータの場合は JSON にフォールバックする."""
        envelope = _make_envelope(data={"key": "value"})
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            print_output(envelope)
            output = mock_stdout.getvalue()

        parsed = json.loads(output.strip())
        assert parsed["data"]["key"] == "value"

    def test_table_format_with_error_envelope_falls_back_to_json(self) -> None:
        """table モードでエラー envelope の場合は JSON にフォールバックする."""
        envelope = Envelope(ok=False, command="test", data=None)
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            print_output(envelope)
            output = mock_stdout.getvalue()

        parsed = json.loads(output.strip())
        assert parsed["ok"] is False

    def test_table_format_with_non_dict_items_falls_back_to_json(self) -> None:
        """table モードでリスト内が dict でない場合は JSON にフォールバックする."""
        envelope = _make_envelope(data=["item1", "item2"])
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            print_output(envelope)
            output = mock_stdout.getvalue()

        parsed = json.loads(output.strip())
        assert parsed["data"] == ["item1", "item2"]

    def test_table_format_flattens_filemaker_records(self) -> None:
        """table モードで FileMaker レコード構造を展開してテーブル表示する."""
        data = [
            {
                "fieldData": {"Name": "田中", "Age": "30"},
                "recordId": "1",
                "modId": "1",
                "portalData": {},
            },
            {
                "fieldData": {"Name": "鈴木", "Age": "25"},
                "recordId": "2",
                "modId": "2",
                "portalData": {},
            },
        ]
        envelope = _make_envelope(data=data)
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            print_output(envelope)
            output = mock_stdout.getvalue()

        # フラット化された fieldData の値がテーブルに表示される
        assert "田中" in output
        assert "鈴木" in output
        assert "recordId" in output

    def test_table_format_with_portal_data_falls_back_to_json(self) -> None:
        """table モードで portalData を含むレコードは JSON にフォールバックする."""
        data = [
            {
                "fieldData": {"Name": "田中"},
                "recordId": "1",
                "modId": "1",
                "portalData": {"Portal1": [{"fieldData": {"Item": "A"}, "recordId": "101"}]},
            },
        ]
        envelope = _make_envelope(data=data)
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            print_output(envelope)
            output = mock_stdout.getvalue()

        # portalData がある場合は JSON にフォールバック
        parsed = json.loads(output.strip())
        assert parsed["ok"] is True
        assert parsed["data"][0]["portalData"]["Portal1"][0]["fieldData"]["Item"] == "A"


# ===================================================================
# verbose / format 設定
# ===================================================================


class TestOutputSettings:
    """verbose / format / timeout 設定のテスト."""

    def setup_method(self) -> None:
        set_output_config(OutputConfig())

    def teardown_method(self) -> None:
        set_output_config(OutputConfig())

    def test_set_verbose_true(self) -> None:
        """set_verbose(True) で verbose モードになる."""
        set_verbose(True)
        assert is_verbose() is True

    def test_set_verbose_false(self) -> None:
        """set_verbose(False) で verbose モードが解除される."""
        set_verbose(True)
        set_verbose(False)
        assert is_verbose() is False

    def test_set_format_json(self) -> None:
        """set_format('json') で JSON モードになる."""
        set_format("json")
        assert get_format() == "json"

    def test_set_format_table(self) -> None:
        """set_format('table') で table モードになる."""
        set_format("table")
        assert get_format() == "table"

    def test_get_timeout_default(self) -> None:
        """デフォルトの timeout は DEFAULT_TIMEOUT（60秒）."""
        assert get_timeout() == DEFAULT_TIMEOUT
        assert get_timeout() == 60

    def test_set_output_config_with_custom_timeout(self) -> None:
        """OutputConfig で timeout をカスタム指定できる."""
        set_output_config(OutputConfig(timeout=120))
        assert get_timeout() == 120

    def test_set_verbose_preserves_timeout(self) -> None:
        """set_verbose() は timeout を保持する."""
        set_output_config(OutputConfig(timeout=30))
        set_verbose(True)
        assert get_timeout() == 30
        assert is_verbose() is True

    def test_set_format_preserves_timeout(self) -> None:
        """set_format() は timeout を保持する."""
        set_output_config(OutputConfig(timeout=90))
        set_format("table")
        assert get_timeout() == 90
        assert get_format() == "table"

    def test_set_verbose_preserves_format_and_timeout(self) -> None:
        """set_verbose() は format と timeout の両方を保持する."""
        set_output_config(OutputConfig(format="table", timeout=45))
        set_verbose(True)
        assert is_verbose() is True
        assert get_format() == "table"
        assert get_timeout() == 45


# ===================================================================
# _flatten_record
# ===================================================================


class TestFlattenRecord:
    """_flatten_record のテスト."""

    def test_fieldDataありのレコードをフラット化(self) -> None:
        """fieldData を展開し recordId / modId を先頭に含める."""
        row = {
            "fieldData": {"Name": "田中", "Age": "30"},
            "recordId": "1",
            "modId": "2",
            "portalData": {},
        }
        result = _flatten_record(row)

        assert result["recordId"] == "1"
        assert result["modId"] == "2"
        assert result["Name"] == "田中"
        assert result["Age"] == "30"
        # portalData や fieldData キーは含まれない
        assert "fieldData" not in result
        assert "portalData" not in result

    def test_fieldDataなしのレコードはそのまま返す(self) -> None:
        """fieldData キーがなければ元の dict をそのまま返す."""
        row = {"name": "simple", "value": 42}
        result = _flatten_record(row)

        assert result is row
        assert result == {"name": "simple", "value": 42}

    def test_recordIdなしでもfieldDataは展開される(self) -> None:
        """recordId / modId がなくても fieldData は展開される."""
        row = {"fieldData": {"X": "1"}}
        result = _flatten_record(row)

        assert result == {"X": "1"}
        assert "recordId" not in result

    def test_fieldDataがdictでない場合は空dictにfieldData以外が残る(self) -> None:
        """fieldData が dict でない場合、update されず recordId 等のみ残る."""
        row = {"fieldData": "not-a-dict", "recordId": "5"}
        result = _flatten_record(row)

        assert result == {"recordId": "5"}


# ===================================================================
# _has_portal_data
# ===================================================================


class TestHasPortalData:
    """_has_portal_data のテスト."""

    def test_portalDataが非空ならTrue(self) -> None:
        rows = [
            {
                "fieldData": {"Name": "A"},
                "portalData": {"Orders": [{"fieldData": {"Item": "X"}, "recordId": "1"}]},
            },
        ]
        assert _has_portal_data(rows) is True

    def test_portalDataが空dictならFalse(self) -> None:
        rows = [
            {"fieldData": {"Name": "A"}, "portalData": {}},
            {"fieldData": {"Name": "B"}, "portalData": {}},
        ]
        assert _has_portal_data(rows) is False

    def test_portalDataキーなしはFalse(self) -> None:
        rows = [{"fieldData": {"Name": "A"}}]
        assert _has_portal_data(rows) is False

    def test_空リストはFalse(self) -> None:
        assert _has_portal_data([]) is False

    def test_一部だけportalDataありならTrue(self) -> None:
        rows = [
            {"fieldData": {"Name": "A"}, "portalData": {}},
            {"fieldData": {"Name": "B"}, "portalData": {"Portal1": []}},
        ]
        # Portal1 は空リストだが truthy (list は空でも portalData dict は非空)
        assert _has_portal_data(rows) is True


# ===================================================================
# print_output (table mode - additional tests)
# ===================================================================


class TestPrintOutputTableAdditional:
    """print_output の table モード追加テスト."""

    def setup_method(self) -> None:
        set_verbose(False)
        set_format("table")

    def teardown_method(self) -> None:
        set_format("json")

    def test_table_with_list_data_renders_table(self, capsys: pytest.CaptureFixture[str]) -> None:
        """format=table でリストデータを渡すとテーブルが出力される."""
        envelope = _make_envelope(data=[{"col1": "val1", "col2": "val2"}])
        print_output(envelope)
        output = capsys.readouterr().out

        # テーブルのカラム名とデータが含まれる
        assert "col1" in output
        assert "val1" in output
        assert "col2" in output
        assert "val2" in output

    def test_table_with_portal_data_falls_back_to_json(self) -> None:
        """format=table で portalData ありのレコードは JSON にフォールバック."""
        data = [
            {
                "fieldData": {"Name": "A"},
                "recordId": "1",
                "modId": "1",
                "portalData": {"P1": [{"recordId": "100", "fieldData": {"X": "1"}}]},
            },
        ]
        envelope = _make_envelope(data=data)
        with patch("sys.stdout", new_callable=StringIO) as mock_stdout:
            print_output(envelope)
            output = mock_stdout.getvalue()

        # JSON にフォールバックされているので parse できる
        parsed = json.loads(output.strip())
        assert parsed["ok"] is True
        assert parsed["data"][0]["portalData"]["P1"][0]["fieldData"]["X"] == "1"
