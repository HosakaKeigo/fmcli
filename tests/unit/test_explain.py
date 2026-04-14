"""explain サービスのテスト."""

from __future__ import annotations

from unittest.mock import patch

from fmcli.domain.models import Profile
from fmcli.services.explain_service import (
    dry_run_find,
    dry_run_record_list,
    explain_find,
)


def _profile() -> Profile:
    return Profile(name="test", host="https://fm.example.com", database="TestDB")


class TestDryRunFind:
    @patch("fmcli.services.explain_service.get_cached_token", return_value="testtoken123")
    def test_basic(self, mock_token) -> None:
        env = dry_run_find(
            _profile(),
            "MyLayout",
            query='[{"Name": "Test"}]',
        )
        assert env.ok is True
        assert env.command == "record find --dry-run"
        assert env.data["method"] == "POST"
        assert "MyLayout/_find" in env.data["url"]
        assert env.data["body"]["query"] == [{"Name": "Test"}]
        assert "Dry run" in env.messages[0]

    @patch("fmcli.services.explain_service.get_cached_token", return_value="testtoken123")
    def test_fields_are_not_sent_to_find_api(self, mock_token) -> None:
        env = dry_run_find(
            _profile(),
            "MyLayout",
            query='{"Name": "Test"}',
            fields="Name,Email",
        )

        assert "response.fields" not in env.data["body"]
        assert any("client-side" in message for message in env.messages)


class TestDryRunRecordList:
    @patch("fmcli.services.explain_service.get_cached_token", return_value="testtoken123")
    def test_basic(self, mock_token) -> None:
        env = dry_run_record_list(_profile(), "MyLayout", offset=1, limit=50)
        assert env.ok is True
        assert env.data["method"] == "GET"
        assert "_limit=50" in env.data["url"]


class TestExplainFind:
    def test_single_condition(self) -> None:
        env = explain_find(_profile(), "MyLayout", query='{"Name": "Test"}')
        assert env.ok is True
        assert env.command == "explain find"
        explanations = env.data["explanation"]
        assert any("Condition 1" in e for e in explanations)

    def test_multiple_conditions(self) -> None:
        env = explain_find(
            _profile(),
            "MyLayout",
            query='[{"Name": "A"}, {"Name": "B"}]',
        )
        explanations = env.data["explanation"]
        assert any("OR" in e for e in explanations)

    def test_with_sort(self) -> None:
        env = explain_find(
            _profile(),
            "MyLayout",
            query='{"Name": "Test"}',
            sort="Name:ascend",
        )
        explanations = env.data["explanation"]
        assert any("Sort" in e for e in explanations)
