"""explain_service の追加テスト — explain_find / schema_find / schema_output."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fmcli.domain.envelopes import ApiInfo, Envelope
from fmcli.domain.models import Profile
from fmcli.services.explain_service import (
    explain_find,
    schema_find,
    schema_output,
)


def _profile() -> Profile:
    return Profile(name="test", host="https://fm.example.com", database="TestDB")


def _api_info() -> ApiInfo:
    return ApiInfo(method="GET", url="https://fm.example.com/fmi/data/vLatest/")


# ---------------------------------------------------------------------------
# explain_find
# ---------------------------------------------------------------------------
class TestExplainFindExtended:
    """explain_find の追加テスト."""

    def test_説明にターゲット情報が含まれる(self) -> None:
        env = explain_find(_profile(), "Contacts", query='{"Name": "田中"}')

        explanations = env.data["explanation"]
        assert any("Contacts" in e and "TestDB" in e for e in explanations)

    def test_説明にAPIエンドポイントが含まれる(self) -> None:
        env = explain_find(_profile(), "Contacts", query='{"Name": "田中"}')

        explanations = env.data["explanation"]
        assert any("POST" in e and "_find" in e for e in explanations)

    def test_条件のフィールド名と値が含まれる(self) -> None:
        env = explain_find(_profile(), "Contacts", query='{"Name": "田中", "Age": "30"}')

        explanations = env.data["explanation"]
        condition_lines = [e for e in explanations if "Condition" in e]
        assert len(condition_lines) == 1
        assert "Name" in condition_lines[0]
        assert "Age" in condition_lines[0]

    def test_複数条件でOR論理の説明が付く(self) -> None:
        env = explain_find(
            _profile(),
            "Contacts",
            query='[{"Name": "田中"}, {"Name": "鈴木"}, {"Name": "佐藤"}]',
        )

        explanations = env.data["explanation"]
        condition_lines = [e for e in explanations if "Condition" in e]
        assert len(condition_lines) == 3

        or_lines = [e for e in explanations if "OR" in e]
        assert len(or_lines) == 1
        assert "3" in or_lines[0]

    def test_単一条件ではOR説明がない(self) -> None:
        env = explain_find(_profile(), "Contacts", query='{"Name": "田中"}')

        explanations = env.data["explanation"]
        assert not any("OR" in e for e in explanations)

    def test_ソート指定時にソート説明が含まれる(self) -> None:
        env = explain_find(
            _profile(),
            "Contacts",
            query='{"Name": "田中"}',
            sort="Name:ascend,Age:descend",
        )

        explanations = env.data["explanation"]
        sort_lines = [e for e in explanations if "Sort" in e]
        assert len(sort_lines) == 1
        assert "Name" in sort_lines[0]
        assert "Age" in sort_lines[0]

    def test_ソート未指定時にソート説明がない(self) -> None:
        env = explain_find(_profile(), "Contacts", query='{"Name": "田中"}')

        explanations = env.data["explanation"]
        assert not any("Sort:" in e for e in explanations)

    def test_ページネーション情報が含まれる(self) -> None:
        env = explain_find(_profile(), "Contacts", query='{"Name": "田中"}', offset=10, limit=50)

        explanations = env.data["explanation"]
        pagination_lines = [e for e in explanations if "offset=10" in e and "limit=50" in e]
        assert len(pagination_lines) == 1

    def test_デフォルトページネーション値(self) -> None:
        env = explain_find(_profile(), "Contacts", query='{"Name": "田中"}')

        explanations = env.data["explanation"]
        assert any("offset=1" in e and "limit=100" in e for e in explanations)

    def test_dataにqueryが含まれる(self) -> None:
        env = explain_find(_profile(), "Contacts", query='{"Name": "田中"}')

        assert env.data["query"] == [{"Name": "田中"}]

    def test_envelope基本プロパティ(self) -> None:
        env = explain_find(_profile(), "Contacts", query='{"Name": "田中"}')

        assert env.ok is True
        assert env.command == "explain find"
        assert env.layout == "Contacts"
        assert env.database == "TestDB"


# ---------------------------------------------------------------------------
# schema_find
# ---------------------------------------------------------------------------
class TestSchemaFind:
    """schema_find のテスト."""

    @patch("fmcli.services.metadata_service.layout_describe")
    def test_フィールド一覧を返す(self, mock_describe: MagicMock) -> None:
        mock_describe.return_value = Envelope.from_profile(
            _profile(),
            command="layout describe",
            layout="Contacts",
            data={
                "fieldMetaData": [
                    {"name": "Name", "result": "text", "global": False},
                    {"name": "Age", "result": "number", "global": False},
                ],
                "portalMetaData": {},
                "valueLists": [],
            },
        )

        env = schema_find(_profile(), "Contacts")

        assert env.ok is True
        assert env.command == "schema find"
        assert len(env.data["findable_fields"]) == 2
        assert env.data["findable_fields"][0] == {
            "name": "Name",
            "type": "text",
            "global": False,
        }
        assert env.data["findable_fields"][1] == {
            "name": "Age",
            "type": "number",
            "global": False,
        }

    @patch("fmcli.services.metadata_service.layout_describe")
    def test_グローバルフィールドの情報が保持される(self, mock_describe: MagicMock) -> None:
        mock_describe.return_value = Envelope.from_profile(
            _profile(),
            command="layout describe",
            layout="Settings",
            data={
                "fieldMetaData": [
                    {"name": "gCompanyName", "result": "text", "global": True},
                ],
                "portalMetaData": {},
                "valueLists": [],
            },
        )

        env = schema_find(_profile(), "Settings")

        assert env.data["findable_fields"][0]["global"] is True

    @patch("fmcli.services.metadata_service.layout_describe")
    def test_ポータルフィールドが含まれる(self, mock_describe: MagicMock) -> None:
        mock_describe.return_value = Envelope.from_profile(
            _profile(),
            command="layout describe",
            layout="Contacts",
            data={
                "fieldMetaData": [{"name": "Name", "result": "text", "global": False}],
                "portalMetaData": {
                    "Orders": [
                        {"name": "Orders::OrderID", "result": "number"},
                        {"name": "Orders::Date", "result": "date"},
                    ]
                },
                "valueLists": [],
            },
        )

        env = schema_find(_profile(), "Contacts")

        assert len(env.data["portals"]) == 1
        portal = env.data["portals"][0]
        assert portal["portal"] == "Orders"
        assert len(portal["fields"]) == 2
        assert portal["fields"][0] == {"name": "Orders::OrderID", "type": "number"}
        assert portal["fields"][1] == {"name": "Orders::Date", "type": "date"}

    @patch("fmcli.services.metadata_service.layout_describe")
    def test_値リストが含まれる(self, mock_describe: MagicMock) -> None:
        vl = [{"name": "Status", "values": [{"value": "Active"}, {"value": "Inactive"}]}]
        mock_describe.return_value = Envelope.from_profile(
            _profile(),
            command="layout describe",
            layout="Contacts",
            data={
                "fieldMetaData": [],
                "portalMetaData": {},
                "valueLists": vl,
            },
        )

        env = schema_find(_profile(), "Contacts")

        assert env.data["value_lists"] == vl

    @patch("fmcli.services.metadata_service.layout_describe")
    def test_値リストの重複が除去される(self, mock_describe: MagicMock) -> None:
        vl_dup = [
            {"name": "Category", "values": [{"value": "Regular"}, {"value": "Associate"}]},
            {"name": "Category", "values": [{"value": "Regular"}, {"value": "Associate"}]},
            {"name": "Category", "values": [{"value": "Regular"}, {"value": "Associate"}]},
            {"name": "Status", "values": [{"value": "Active"}]},
            {"name": "Status", "values": [{"value": "Active"}]},
            {"name": "Region", "values": [{"value": "東京"}]},
        ]
        mock_describe.return_value = Envelope.from_profile(
            _profile(),
            command="layout describe",
            layout="Contacts",
            data={
                "fieldMetaData": [],
                "portalMetaData": {},
                "valueLists": vl_dup,
            },
        )

        env = schema_find(_profile(), "Contacts")

        assert len(env.data["value_lists"]) == 3
        names = [v["name"] for v in env.data["value_lists"]]
        assert names == ["Category", "Status", "Region"]

    @patch("fmcli.services.metadata_service.layout_describe")
    def test_フィールドの重複が除去される(self, mock_describe: MagicMock) -> None:
        mock_describe.return_value = Envelope.from_profile(
            _profile(),
            command="layout describe",
            layout="Events",
            data={
                "fieldMetaData": [
                    {"name": "date", "result": "date", "global": False},
                    {"name": "date", "result": "date", "global": False},
                    {"name": "date", "result": "date", "global": False},
                    {"name": "title", "result": "text", "global": False},
                    {"name": "title", "result": "text", "global": False},
                    {"name": "place", "result": "text", "global": False},
                ],
                "portalMetaData": {},
                "valueLists": [],
            },
        )

        env = schema_find(_profile(), "Events")

        assert len(env.data["findable_fields"]) == 3
        names = [f["name"] for f in env.data["findable_fields"]]
        assert names == ["date", "title", "place"]

    @patch("fmcli.services.metadata_service.layout_describe")
    def test_空のフィールド一覧(self, mock_describe: MagicMock) -> None:
        mock_describe.return_value = Envelope.from_profile(
            _profile(),
            command="layout describe",
            layout="Empty",
            data={
                "fieldMetaData": [],
                "portalMetaData": {},
                "valueLists": [],
            },
        )

        env = schema_find(_profile(), "Empty")

        assert env.ok is True
        assert env.data["findable_fields"] == []
        assert env.data["portals"] == []
        assert env.data["value_lists"] == []

    @patch("fmcli.services.metadata_service.layout_describe")
    def test_layout_describeがエラーの場合そのまま返す(self, mock_describe: MagicMock) -> None:
        error_envelope = Envelope(
            ok=False,
            command="layout describe",
            data=None,
        )
        mock_describe.return_value = error_envelope

        env = schema_find(_profile(), "NotFound")

        assert env.ok is False
        assert env is error_envelope

    @patch("fmcli.services.metadata_service.layout_describe")
    def test_様々なフィールド型を処理できる(self, mock_describe: MagicMock) -> None:
        fields = [
            {"name": "TextField", "result": "text", "global": False},
            {"name": "NumberField", "result": "number", "global": False},
            {"name": "DateField", "result": "date", "global": False},
            {"name": "TimeField", "result": "time", "global": False},
            {"name": "TimestampField", "result": "timeStamp", "global": False},
            {"name": "ContainerField", "result": "container", "global": False},
        ]
        mock_describe.return_value = Envelope.from_profile(
            _profile(),
            command="layout describe",
            layout="AllTypes",
            data={
                "fieldMetaData": fields,
                "portalMetaData": {},
                "valueLists": [],
            },
        )

        env = schema_find(_profile(), "AllTypes")

        assert len(env.data["findable_fields"]) == 6
        types = [f["type"] for f in env.data["findable_fields"]]
        assert types == ["text", "number", "date", "time", "timeStamp", "container"]

    @patch("fmcli.services.metadata_service.layout_describe")
    def test_フィールドにnameやresultがない場合は空文字(self, mock_describe: MagicMock) -> None:
        mock_describe.return_value = Envelope.from_profile(
            _profile(),
            command="layout describe",
            layout="Broken",
            data={
                "fieldMetaData": [{}],
                "portalMetaData": {},
                "valueLists": [],
            },
        )

        env = schema_find(_profile(), "Broken")

        assert env.data["findable_fields"][0] == {
            "name": "",
            "type": "",
            "global": False,
        }


# ---------------------------------------------------------------------------
# schema_output
# ---------------------------------------------------------------------------
class TestSchemaOutput:
    """schema_output のテスト."""

    @patch("fmcli.services.metadata_service.layout_describe")
    def test_フィールド名一覧を返す(self, mock_describe: MagicMock) -> None:
        mock_describe.return_value = Envelope.from_profile(
            _profile(),
            command="layout describe",
            layout="Contacts",
            data={
                "fieldMetaData": [
                    {"name": "Name"},
                    {"name": "Email"},
                    {"name": "Phone"},
                ],
                "portalMetaData": {},
                "valueLists": [],
            },
        )

        env = schema_output(_profile(), "Contacts")

        assert env.ok is True
        assert env.command == "schema output"
        assert env.data["fieldData_keys"] == ["Name", "Email", "Phone"]

    @patch("fmcli.services.metadata_service.layout_describe")
    def test_ポータル構造を返す(self, mock_describe: MagicMock) -> None:
        mock_describe.return_value = Envelope.from_profile(
            _profile(),
            command="layout describe",
            layout="Contacts",
            data={
                "fieldMetaData": [{"name": "Name"}],
                "portalMetaData": {
                    "Orders": [
                        {"name": "Orders::OrderID"},
                        {"name": "Orders::Amount"},
                    ],
                    "Addresses": [
                        {"name": "Addresses::City"},
                    ],
                },
                "valueLists": [],
            },
        )

        env = schema_output(_profile(), "Contacts")

        assert env.data["portalData"] == {
            "Orders": ["Orders::OrderID", "Orders::Amount"],
            "Addresses": ["Addresses::City"],
        }

    @patch("fmcli.services.metadata_service.layout_describe")
    def test_空のレイアウト(self, mock_describe: MagicMock) -> None:
        mock_describe.return_value = Envelope.from_profile(
            _profile(),
            command="layout describe",
            layout="Empty",
            data={
                "fieldMetaData": [],
                "portalMetaData": {},
                "valueLists": [],
            },
        )

        env = schema_output(_profile(), "Empty")

        assert env.data["fieldData_keys"] == []
        assert env.data["portalData"] == {}

    @patch("fmcli.services.metadata_service.layout_describe")
    def test_layout_describeがエラーの場合そのまま返す(self, mock_describe: MagicMock) -> None:
        error_envelope = Envelope(ok=False, command="layout describe", data=None)
        mock_describe.return_value = error_envelope

        env = schema_output(_profile(), "NotFound")

        assert env.ok is False
        assert env is error_envelope

    @patch("fmcli.services.metadata_service.layout_describe")
    def test_nameキーがないフィールドは空文字(self, mock_describe: MagicMock) -> None:
        mock_describe.return_value = Envelope.from_profile(
            _profile(),
            command="layout describe",
            layout="Broken",
            data={
                "fieldMetaData": [{"result": "text"}, {}],
                "portalMetaData": {},
                "valueLists": [],
            },
        )

        env = schema_output(_profile(), "Broken")

        assert env.data["fieldData_keys"] == ["", ""]

    @patch("fmcli.services.metadata_service.layout_describe")
    def test_ポータルフィールドにnameがない場合は空文字(self, mock_describe: MagicMock) -> None:
        mock_describe.return_value = Envelope.from_profile(
            _profile(),
            command="layout describe",
            layout="Broken",
            data={
                "fieldMetaData": [],
                "portalMetaData": {"P1": [{}]},
                "valueLists": [],
            },
        )

        env = schema_output(_profile(), "Broken")

        assert env.data["portalData"] == {"P1": [""]}
